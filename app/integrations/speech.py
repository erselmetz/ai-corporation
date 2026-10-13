"""Backend-neutral, bounded speech input contracts."""
from dataclasses import dataclass, field
import re
from typing import Protocol
import threading
import wave
from io import BytesIO


MAX_SPEECH_SECONDS = 10
SPEECH_SAMPLE_RATE = 16_000
SPEECH_CHANNELS = 1
SPEECH_SAMPLE_WIDTH_BYTES = 2
MAX_SPEECH_PCM_BYTES = MAX_SPEECH_SECONDS * SPEECH_SAMPLE_RATE * SPEECH_CHANNELS * SPEECH_SAMPLE_WIDTH_BYTES
MAX_SPEECH_WAV_BYTES = MAX_SPEECH_PCM_BYTES + 44
MAX_TRANSCRIPT_CHARS = 8_192


class SpeechInputError(ValueError):
    """Safe validation error for bounded audio or transcript inputs."""


@dataclass
class SpeechInputRequest:
    audio: bytearray = field(repr=False)
    language: str

    def __post_init__(self):
        if isinstance(self.audio, bytes):
            self.audio = bytearray(self.audio)
        if not isinstance(self.audio, bytearray) or not 44 <= len(self.audio) <= MAX_SPEECH_WAV_BYTES:
            raise SpeechInputError("Speech audio must be a bounded PCM WAV recording")
        if (not isinstance(self.language, str) or len(self.language) > 16
                or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Z0-9]{2,8})?", self.language)):
            raise SpeechInputError("A valid speech language tag is required")
        try:
            with wave.open(BytesIO(self.audio), "rb") as wav:
                valid = (wav.getcomptype() == "NONE" and wav.getnchannels() == SPEECH_CHANNELS
                         and wav.getsampwidth() == SPEECH_SAMPLE_WIDTH_BYTES
                         and wav.getframerate() == SPEECH_SAMPLE_RATE
                         and 0 < wav.getnframes() <= MAX_SPEECH_PCM_BYTES // SPEECH_SAMPLE_WIDTH_BYTES)
                expected_bytes = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
                valid = valid and expected_bytes + 44 <= MAX_SPEECH_WAV_BYTES
        except (wave.Error, EOFError):
            valid = False
        if not valid:
            raise SpeechInputError("Speech audio must be mono 16 kHz 16-bit PCM and at most 10 seconds")

    def close(self):
        """Clear the request's owned audio buffer after use or cancellation."""
        self.audio[:] = b"\0" * len(self.audio)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


@dataclass(frozen=True)
class SpeechTranscript:
    text: str = field(repr=False)
    backend: str
    language: str

    def __post_init__(self):
        if (not isinstance(self.text, str) or not self.text.strip()
                or len(self.text) > MAX_TRANSCRIPT_CHARS):
            raise SpeechInputError("Speech recognition returned no bounded transcript")
        if self.backend not in {"local", "online"}:
            raise SpeechInputError("Speech recognition backend must be local or online")


class SpeechToTextProvider(Protocol):
    """Explicit provider; callers clear the request in finally and check cancellation."""

    backend: str

    def availability(self, *, language: str) -> str: ...

    def transcribe(self, request: SpeechInputRequest, *, cancelled: threading.Event) -> SpeechTranscript: ...
