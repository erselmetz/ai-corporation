from io import BytesIO
import wave

import pytest

from app.integrations.speech import (
    MAX_SPEECH_SECONDS,
    MAX_SPEECH_WAV_BYTES,
    SPEECH_SAMPLE_RATE,
    SpeechInputError,
    SpeechInputRequest,
    SpeechTranscript,
)


def pcm_wav(seconds=1, *, rate=SPEECH_SAMPLE_RATE, channels=1, sample_width=2):
    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(rate)
        wav.writeframes(b"\0" * rate * seconds * channels * sample_width)
    return output.getvalue()


def test_speech_input_contract_accepts_bounded_pcm_without_exposing_audio_in_repr():
    audio = pcm_wav(MAX_SPEECH_SECONDS)
    request = SpeechInputRequest(audio=audio, language="en-US")
    assert len(audio) == MAX_SPEECH_WAV_BYTES
    assert "audio" not in repr(request)
    assert request.language == "en-US"
    request.close()
    assert not any(request.audio)


@pytest.mark.parametrize("audio,language", [
    (b"not-a-wave", "en-US"),
    (pcm_wav(11), "en-US"),
    (pcm_wav(1, rate=8_000), "en-US"),
    (pcm_wav(1, channels=2), "en-US"),
    (pcm_wav(1, sample_width=1), "en-US"),
    (pcm_wav(1), "../../private"),
], ids=["not-wav", "over-ten-seconds", "wrong-rate", "stereo", "wrong-sample-width", "bad-language"])
def test_speech_input_contract_rejects_oversize_malformed_or_unsafe_inputs(audio, language):
    with pytest.raises(SpeechInputError):
        SpeechInputRequest(audio=audio, language=language)


def test_transcript_is_bounded_and_marks_backend_without_logging_text():
    transcript = SpeechTranscript(text="A private phrase", backend="local", language="en-US")
    assert "private phrase" not in repr(transcript)
    with pytest.raises(SpeechInputError):
        SpeechTranscript(text="x" * 8_193, backend="online", language="en-US")
    with pytest.raises(SpeechInputError):
        SpeechTranscript(text="text", backend="fallback", language="en-US")
