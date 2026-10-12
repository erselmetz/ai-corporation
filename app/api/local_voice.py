"""Explicit local-owner speech controls and bounded Gemini transcription."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.integrations.gemini_chat import GeminiCallLimit, GeminiConnectionError
from app.integrations.gemini_voice import (
    MAX_AUDIO_BYTES,
    GeminiTranscriber,
    VoiceRequestError,
    VoiceSpendBudget,
)
from .security import require_permission


class CloudBudgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ceiling_cents: int = Field(ge=1, le=100, strict=True)


def create_local_voice_router(connection_manager, budget: VoiceSpendBudget | None = None):
    router = APIRouter(prefix="/api/local/voice")
    budget = budget or VoiceSpendBudget()
    transcriber = GeminiTranscriber(connection_manager, budget)

    @router.get("")
    def status(_principal=Depends(require_permission("chat:send"))):
        return {
            "local_processing": "on_device_web_speech_only",
            "cloud_provider": "gemini",
            "cloud_budget": budget.snapshot(),
            "audio_retention": "none_by_application",
        }

    @router.post("/cloud-budget")
    async def configure_budget(request: Request,
                               _principal=Depends(require_permission("chat:send"))):
        from app.api.chat import bounded_body
        payload = await bounded_body(request)
        try:
            body = CloudBudgetRequest.model_validate_json(payload)
            return budget.configure(body.ceiling_cents)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @router.post("/transcribe")
    async def transcribe(request: Request,
                         _principal=Depends(require_permission("chat:send"))):
        if request.headers.get("x-cloud-consent") != "true":
            raise HTTPException(403, "Explicit per-use consent to send this recording to Google Gemini is required")
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "audio/wav":
            raise HTTPException(415, "Voice transcription accepts only bounded 16 kHz PCM WAV audio")
        audio = bytearray()
        async for chunk in request.stream():
            if len(audio) + len(chunk) > MAX_AUDIO_BYTES:
                audio[:] = b"\0" * len(audio)
                raise HTTPException(413, "Voice recording exceeds the 10-second limit")
            audio.extend(chunk)
        try:
            result = transcriber.transcribe(bytes(audio))
        except VoiceRequestError as error:
            status_code = 422 if "Audio" in str(error) else 409
            raise HTTPException(status_code, str(error)) from None
        except GeminiCallLimit as error:
            raise HTTPException(429, str(error)) from None
        except GeminiConnectionError as error:
            raise HTTPException(409, str(error)) from None
        except Exception:
            raise HTTPException(502, "Gemini transcription failed or timed out. The outcome may be unknown; do not retry automatically.") from None
        finally:
            audio[:] = b"\0" * len(audio)
        return {
            "transcript": result.transcript,
            "reserved_cents": result.reserved_cents,
            "remaining_cents": result.remaining_cents,
            "audio_retained": False,
        }

    return router
