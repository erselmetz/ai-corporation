from __future__ import annotations

from io import BytesIO
import wave

import httpx
import pytest

from app.integrations.gemini_voice import (
    ENDPOINT,
    MAX_AUDIO_BYTES,
    GeminiTranscriber,
    VoiceRequestError,
    VoiceSpendBudget,
    validate_wav,
)

KEY = "AIza" + "S" * 35


def make_wav(seconds=1, *, rate=16_000, channels=1, width=2):
    buffer = BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(width)
        output.setframerate(rate)
        output.writeframes(b"\0" * (seconds * rate * channels * width))
    return buffer.getvalue()


class Connection:
    def __init__(self):
        self.active = False
        self.calls = 0

    def begin_voice_call(self):
        assert not self.active
        self.active = True
        self.calls += 1
        return KEY

    def end_voice_call(self):
        self.active = False


def test_wav_requires_bounded_mono_16khz_pcm_and_exact_container():
    validate_wav(make_wav(10))
    with pytest.raises(VoiceRequestError, match="10-second"):
        validate_wav(make_wav(11))
    with pytest.raises(VoiceRequestError, match="mono 16 kHz"):
        validate_wav(make_wav(1, rate=48_000))
    with pytest.raises(VoiceRequestError, match="mono 16 kHz"):
        validate_wav(make_wav(1, channels=2))
    with pytest.raises(VoiceRequestError, match="container"):
        validate_wav(make_wav(1) + b"trailing payload")
    with pytest.raises(VoiceRequestError, match="10-second"):
        validate_wav(b"x" * (MAX_AUDIO_BYTES + 1))


def test_cloud_voice_must_have_an_explicit_bounded_run_budget():
    budget = VoiceSpendBudget()
    with pytest.raises(VoiceRequestError, match="Set a cloud voice ceiling"):
        budget.reserve()
    with pytest.raises(VoiceRequestError, match="1 to 100 cents"):
        budget.configure(0)
    assert budget.configure(2)["remaining_cents"] == 2
    assert budget.reserve()["remaining_cents"] == 1
    assert budget.reserve()["remaining_cents"] == 0
    with pytest.raises(VoiceRequestError, match="exhausted"):
        budget.reserve()
    assert budget.snapshot()["reset"] == "app_restart"


def test_transcription_is_inline_bounded_and_never_retains_or_returns_key(monkeypatch):
    connection = Connection()
    budget = VoiceSpendBudget()
    budget.configure(2)
    observed = []
    real_client = httpx.Client

    def handler(request):
        observed.append(request)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "  hello there  "}]}}]})

    def client_factory(**options):
        assert options == {"timeout": 15.0, "follow_redirects": False, "trust_env": False}
        return real_client(transport=httpx.MockTransport(handler), **options)

    result = GeminiTranscriber(connection, budget, client_factory=client_factory).transcribe(make_wav())
    assert result.transcript == "hello there"
    assert result.reserved_cents == 1
    assert result.remaining_cents == 1
    assert connection.active is False
    assert len(observed) == 1
    assert str(observed[0].url) == ENDPOINT
    assert observed[0].headers["x-goog-api-key"] == KEY
    assert "hello there" not in observed[0].content.decode()
    assert KEY not in repr(result)
    assert budget.snapshot()["reserved_cents"] == 1


def test_failure_keeps_conservative_reservation_and_does_not_retry(monkeypatch):
    connection = Connection()
    budget = VoiceSpendBudget()
    budget.configure(2)
    requests = []
    real_client = httpx.Client

    def handler(request):
        requests.append(request)
        return httpx.Response(503, text=f"secret {KEY}")

    def client_factory(**options):
        return real_client(transport=httpx.MockTransport(handler), **options)

    with pytest.raises(VoiceRequestError, match="outcome may be unknown"):
        GeminiTranscriber(connection, budget, client_factory=client_factory).transcribe(make_wav())
    assert len(requests) == 1
    assert budget.snapshot()["reserved_cents"] == 1
    assert connection.active is False


def test_budget_exhaustion_prevents_the_provider_call():
    connection = Connection()
    budget = VoiceSpendBudget()
    budget.configure(1)
    budget.reserve()
    with pytest.raises(VoiceRequestError, match="exhausted"):
        GeminiTranscriber(connection, budget).transcribe(make_wav())
    assert connection.calls == 1
    assert connection.active is False


def test_unavailable_cloud_connection_does_not_consume_cloud_budget():
    class MissingConnection:
        def begin_voice_call(self):
            raise RuntimeError("not connected")

        def end_voice_call(self):
            raise AssertionError("no call was reserved")

    budget = VoiceSpendBudget()
    budget.configure(1)
    with pytest.raises(RuntimeError, match="not connected"):
        GeminiTranscriber(MissingConnection(), budget).transcribe(make_wav())
    assert budget.snapshot()["reserved_cents"] == 0




def test_cloud_voice_requires_a_live_explicit_gemini_coordinator_connection(monkeypatch):
    from datetime import datetime, timezone
    from app.integrations.gemini_catalog import (
        GeminiCatalogAuditEvent, GeminiCatalogAuditStatus, GeminiModel,
        GeminiModelCapability, GeminiModelCatalogResult,
    )
    from app.integrations.gemini_chat import GeminiConnectionError, GeminiConnectionManager

    checked = datetime.now(timezone.utc)
    catalog = GeminiModelCatalogResult(
        (GeminiModel("gemini-tested", (GeminiModelCapability.GENERATE_CONTENT,)),),
        False, checked,
        GeminiCatalogAuditEvent("gemini", "list_models", GeminiCatalogAuditStatus.SUCCEEDED,
                                checked, 1, 1, False, None),
    )
    monkeypatch.setattr("app.integrations.gemini_chat.GeminiModelCatalogAdapter.list_models",
                        lambda _self: catalog)
    manager = GeminiConnectionManager()
    manager.discover(KEY)
    with pytest.raises(GeminiConnectionError, match="Connect Gemini"):
        manager.begin_voice_call()
    manager.select_model("coordinator", "CEO", "ollama", "llama3.2:3b", "gemini-tested")
    assert manager.begin_voice_call() == KEY
    assert manager.selected("coordinator") == (
        "coordinator", "CEO", "ollama", "llama3.2:3b", "gemini-tested")
    with pytest.raises(GeminiConnectionError, match="already active"):
        manager.begin_voice_call()
    manager.end_voice_call()
    assert manager.begin_voice_call() == KEY
    manager.end_voice_call()
