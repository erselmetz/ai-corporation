from dataclasses import dataclass
from threading import Event
from unittest.mock import MagicMock
from io import BytesIO
import wave

from fastapi.testclient import TestClient

from app.integrations.speech import SpeechTranscript
from app.local import create_local_app


PASSWORD = "local-speech-api-test-password"
ORIGIN = "http://127.0.0.1:8000"


def wav():
    data = BytesIO()
    with wave.open(data, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(b"\0" * 32_000)
    return data.getvalue()


@dataclass
class Status:
    runtime: str = "available"
    selected_model: str | None = "tiny-en"
    available_models: tuple[str, ...] = ("tiny-en",)
    state: str = "ready"


class LocalSpeechFake:
    def __init__(self):
        self.request = None
        self.transcriptions = 0

    def status(self):
        return Status()

    def select_model(self, model_id):
        if model_id != "tiny-en":
            raise ValueError("Selected local speech model is not available")
        return Status()

    def transcribe(self, request, *, cancelled: Event):
        self.request = request
        self.transcriptions += 1
        assert not cancelled.is_set()
        return SpeechTranscript("local draft", backend="local", language=request.language)


def signed_in(client):
    login = client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})
    assert login.status_code == 200
    session = client.get("/api/local/session").json()
    return {"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]}


def test_local_speech_status_selection_and_transcription_are_protected_and_ephemeral():
    provider = LocalSpeechFake()
    app = create_local_app(password=PASSWORD, application_service=MagicMock(),
                           local_speech_provider=provider)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50151)) as client:
        assert client.get("/api/local/voice").status_code == 401
        headers = signed_in(client)
        status = client.get("/api/local/voice")
        assert status.status_code == 200
        assert status.json()["local_speech"]["state"] == "ready"
        assert client.post("/api/local/voice/local-model", headers=headers,
                           json={"model_id": "../../private"}).status_code == 422
        selected = client.post("/api/local/voice/local-model", headers=headers,
                               json={"model_id": "tiny-en"})
        assert selected.status_code == 200

        response = client.post("/api/local/voice/transcribe-local?language=en-US",
                               headers={**headers, "Content-Type": "audio/wav"}, content=wav())
        assert response.status_code == 200
        assert response.json() == {"transcript": "local draft", "backend": "local",
                                   "language": "en-US", "audio_retained": False}
        assert provider.transcriptions == 1
        assert not any(provider.request.audio)


def test_emergency_stop_rejects_new_local_transcription():
    provider = LocalSpeechFake()
    app = create_local_app(password=PASSWORD, application_service=MagicMock(),
                           local_speech_provider=provider)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50152)) as client:
        headers = signed_in(client)
        stop = client.post("/api/local/emergency-stop/stop", headers=headers, json={})
        assert stop.status_code == 200
        response = client.post("/api/local/voice/transcribe-local?language=en-US",
                               headers={**headers, "Content-Type": "audio/wav"}, content=wav())
        assert response.status_code == 423
        assert provider.transcriptions == 0
