"""Explicit local-owner speech controls and bounded Gemini transcription."""

import asyncio
import threading
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

from app.integrations.gemini_chat import GeminiCallLimit, GeminiConnectionError
from app.integrations.gemini_voice import (
    MAX_AUDIO_BYTES,
    GeminiTranscriber,
    VoiceRequestError,
    VoiceSpendBudget,
)
from app.integrations.local_speech import LocalSpeechUnavailable
from app.integrations.local_speech_model import LocalSpeechModelCatalog
from app.integrations.speech import MAX_SPEECH_WAV_BYTES, SpeechInputError, SpeechInputRequest
from .security import require_permission


class CloudBudgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ceiling_cents: int = Field(ge=1, le=100, strict=True)


class LocalSpeechModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: StrictStr = Field(min_length=1, max_length=64)


class LocalSpeechModelInstall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: StrictBool
    manifest_digest: StrictStr = Field(min_length=64, max_length=64)


def create_local_voice_router(connection_manager, budget: VoiceSpendBudget | None = None,
                              local_speech=None, speech_model_catalog=None,
                              media_packs=None, local_output=None):
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
            "local_speech": local_speech.status().__dict__ if local_speech is not None else {
                "runtime": "unavailable", "selected_model": None,
                "available_models": (), "state": "backend-unavailable"},
            "local_output": local_output.snapshot() if local_output is not None else {"state": "unavailable", "active": False},
        }

    @router.post("/test-output")
    def test_local_output(request: Request,
                          _principal=Depends(require_permission("capability-pack:manage"))):
        if local_output is None or media_packs is None or media_packs.preview("voice")["state"] == "not-installed":
            raise HTTPException(409, "Install the reviewed local Voice pack before testing pyttsx3 output")
        if request.app.state.emergency_stop_service.stopped:
            raise HTTPException(423, "Emergency stop is active; local speech output cannot start")
        return local_output.start_test()

    @router.get("/output-status")
    def local_output_status(_principal=Depends(require_permission("capability-pack:manage"))):
        return local_output.snapshot() if local_output is not None else {"state": "unavailable", "active": False}

    @router.post("/stop-output")
    def stop_local_output(_principal=Depends(require_permission("capability-emergency:manage"))):
        return local_output.stop() if local_output is not None else {"state": "unavailable", "active": False}

    @router.post("/local-model")
    async def select_local_model(request: Request,
                                 _principal=Depends(require_permission("chat:send"))):
        if local_speech is None:
            raise HTTPException(503, "Optional local speech backend is unavailable")
        from app.api.chat import bounded_body
        try:
            body = LocalSpeechModelRequest.model_validate_json(await bounded_body(request))
            return local_speech.select_model(body.model_id).__dict__
        except LocalSpeechUnavailable as error:
            raise HTTPException(409, str(error)) from None
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @router.get("/local-model-preview")
    def local_model_preview(_principal=Depends(require_permission("capability-pack:manage"))):
        catalog = speech_model_catalog or LocalSpeechModelCatalog(
            getattr(local_speech, "model_root", Path.home() / ".local" / "share" / "ERSELMETZ AI" / "speech-models"))
        return catalog.preview()

    @router.post("/local-model-install")
    def install_local_model(body: LocalSpeechModelInstall,
                            _principal=Depends(require_permission("capability-pack:manage"))):
        catalog = speech_model_catalog or LocalSpeechModelCatalog(
            getattr(local_speech, "model_root", Path.home() / ".local" / "share" / "ERSELMETZ AI" / "speech-models"))
        preview = catalog.preview()
        if body.confirmed is not True or body.manifest_digest != preview["manifest_digest"]:
            raise HTTPException(409, "Review the pinned speech model revision, exact files, size, and digest, then explicitly confirm the download")
        try:
            result = catalog.install(confirmed=body.confirmed, manifest_digest=body.manifest_digest)
            if result.get("state") == "installed" and local_speech is not None:
                try:
                    result["speech_status"] = local_speech.select_model("faster-whisper-tiny").__dict__
                    result["model_selected"] = True
                except LocalSpeechUnavailable as error:
                    result["speech_status"] = {"state": "model-download-complete", "detail": str(error)}
                    result["model_selected"] = False
            return result
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from None

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

    @router.post("/transcribe-local")
    async def transcribe_local(request: Request,
                               _principal=Depends(require_permission("chat:send"))):
        if local_speech is None:
            raise HTTPException(503, "Optional local speech backend is unavailable")
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "audio/wav":
            raise HTTPException(415, "Local speech accepts only bounded 16 kHz PCM WAV audio")
        audio = bytearray()
        try:
            async for chunk in request.stream():
                if len(audio) + len(chunk) > MAX_SPEECH_WAV_BYTES:
                    raise HTTPException(413, "Voice recording exceeds the 10-second limit")
                audio.extend(chunk)
        except BaseException:
            audio[:] = b"\0" * len(audio)
            raise
        try:
            query = request.query_params
            language = query.get("language", "en-US")
            speech_request = SpeechInputRequest(audio=audio, language=language)
        except SpeechInputError as error:
            audio[:] = b"\0" * len(audio)
            raise HTTPException(422, str(error)) from None
        cancelled = threading.Event()
        task = asyncio.create_task(asyncio.to_thread(
            local_speech.transcribe, speech_request, cancelled=cancelled))
        disconnected = False
        try:
            while not task.done():
                await asyncio.sleep(0.05)
                if (request.app.state.emergency_stop_service.stopped
                        or await request.is_disconnected()):
                    disconnected = await request.is_disconnected()
                    cancelled.set()
            if request.app.state.emergency_stop_service.stopped:
                cancelled.set()
                await task
                raise HTTPException(423, "Emergency stop is active; local transcription was cancelled")
            if disconnected:
                cancelled.set()
                await task
                raise HTTPException(409, "Local transcription was cancelled after the browser disconnected")
            result = await task
            if media_packs is not None:
                media_packs.mark_working("ears")
            return {"transcript": result.text, "backend": "local", "language": result.language,
                    "audio_retained": False}
        except LocalSpeechUnavailable as error:
            raise HTTPException(409, str(error)) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502, "Local speech recognition failed") from None
        finally:
            cancelled.set()
            speech_request.close()
            audio[:] = b"\0" * len(audio)

    return router
