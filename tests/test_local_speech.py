from pathlib import Path
from threading import Event
from types import SimpleNamespace
import wave
from io import BytesIO

import pytest

from app.integrations.local_speech import FasterWhisperLocalProvider, LocalSpeechUnavailable, RUNTIME_MODULES
from app.integrations.speech import SpeechInputRequest


def add_model(root: Path, name="tiny-en"):
    model = root / name
    model.mkdir(parents=True)
    for filename in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
        (model / filename).write_bytes(b"fixture")
    return model


def request():
    data = BytesIO()
    with wave.open(data, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(b"\0" * 32_000)
    return SpeechInputRequest(bytearray(data.getvalue()), "en-US")


def test_optional_local_speech_reports_missing_runtime_and_model_without_loading(tmp_path):
    provider = FasterWhisperLocalProvider(tmp_path / "models", runtime_available=False,
                                          model_loader=lambda _path: pytest.fail("must not load"))
    assert provider.status().runtime == "unavailable"
    assert provider.status().state == "runtime-unavailable"
    with pytest.raises(LocalSpeechUnavailable, match="runtime is not installed"):
        provider.select_model("tiny-en")


def test_runtime_is_unavailable_when_an_optional_native_dependency_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.integrations.local_speech.importlib.util.find_spec",
        lambda name: None if name == "ctranslate2" else object(),
    )
    provider = FasterWhisperLocalProvider(tmp_path / "models")
    assert provider.status().runtime == "unavailable"
    assert provider.status().state == "runtime-unavailable"
    assert all(name in RUNTIME_MODULES for name in ("faster_whisper", "ctranslate2"))


def test_only_explicitly_selected_installed_models_load_and_transcribe_locally(tmp_path):
    add_model(tmp_path / "models")
    loaded = []
    calls = []

    class Model:
        def transcribe(self, samples, **options):
            calls.append((samples, options))
            return iter([SimpleNamespace(text=" hello local")]), SimpleNamespace()

    provider = FasterWhisperLocalProvider(
        tmp_path / "models", runtime_available=True,
        model_loader=lambda path: loaded.append(path) or Model(),
        audio_decoder=lambda audio: ("decoded", len(audio)),
    )
    assert provider.available_models() == ("tiny-en",)
    assert loaded == []
    assert provider.status().state == "model-not-selected"
    with pytest.raises(LocalSpeechUnavailable, match="Select an available"):
        provider.transcribe(request(), cancelled=Event())
    provider.select_model("tiny-en")
    assert loaded == []
    result = provider.transcribe(request(), cancelled=Event())
    assert result.text == "hello local"
    assert result.backend == "local"
    assert len(loaded) == 1 and loaded[0].name == "tiny-en"
    assert calls[0][1] == {
        "language": "en", "beam_size": 1, "vad_filter": False,
        "condition_on_previous_text": False,
    }


def test_missing_or_untrusted_model_ids_fail_closed_and_cancellation_avoids_loading(tmp_path):
    add_model(tmp_path / "models")
    loaded = []
    provider = FasterWhisperLocalProvider(tmp_path / "models", runtime_available=True,
                                          model_loader=lambda path: loaded.append(path))
    with pytest.raises(LocalSpeechUnavailable, match="valid local speech model identifier"):
        provider.select_model("../../secret")
    provider.select_model("tiny-en")
    cancelled = Event()
    cancelled.set()
    with pytest.raises(LocalSpeechUnavailable, match="cancelled"):
        provider.transcribe(request(), cancelled=cancelled)
    assert loaded == []


def test_catalog_rejects_incomplete_model_folders(tmp_path):
    root = tmp_path / "models"
    add_model(root, "complete")
    incomplete = root / "incomplete"
    incomplete.mkdir()
    (incomplete / "model.bin").write_bytes(b"fixture")
    provider = FasterWhisperLocalProvider(root, runtime_available=True)
    assert provider.available_models() == ("complete",)


def test_decoded_audio_array_is_cleared_after_transcription(tmp_path):
    add_model(tmp_path / "models")

    class Samples:
        cleared = False

        def fill(self, value):
            assert value == 0
            self.cleared = True

    samples = Samples()

    class Model:
        def transcribe(self, decoded, **_options):
            assert decoded is samples and not samples.cleared
            return iter([SimpleNamespace(text="spoken")]), SimpleNamespace()

    provider = FasterWhisperLocalProvider(
        tmp_path / "models", runtime_available=True,
        model_loader=lambda _path: Model(), audio_decoder=lambda _audio: samples,
    )
    provider.select_model("tiny-en")
    assert provider.transcribe(request(), cancelled=Event()).text == "spoken"
    assert samples.cleared
