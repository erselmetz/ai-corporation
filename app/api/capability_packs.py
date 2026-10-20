"""Owner-confirmed optional local capability pack management."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

from app.integrations.capability_packs import OptionalMediaPacks
from .security import AuthenticatedPrincipal, require_permission


router = APIRouter(prefix="/api/capability-packs", tags=["capability-packs"])


class PackInstall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: StrictBool
    manifest_digest: StrictStr = Field(min_length=64, max_length=64)


def manager(request: Request):
    configured = getattr(request.app.state, "media_capability_packs", None)
    if configured is None:
        configured = OptionalMediaPacks()
        request.app.state.media_capability_packs = configured
    return configured


@router.get("")
def list_packs(_principal: AuthenticatedPrincipal = Depends(require_permission("capability-pack:manage")),
               packs=Depends(manager)):
    return packs.preview()


@router.post("/{pack_id}/install")
def install_pack(pack_id: str, body: PackInstall, request: Request,
                 _principal: AuthenticatedPrincipal = Depends(require_permission("capability-pack:manage")),
                 packs=Depends(manager)):
    try:
        preview = packs.preview(pack_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from None
    if body.confirmed is not True or body.manifest_digest != preview["manifest_digest"]:
        raise HTTPException(409, "Review this pack's exact source, wheel versions, total size, and SHA-256 manifest, then confirm again")
    try:
        result = packs.install(pack_id, confirmed=body.confirmed, manifest_digest=body.manifest_digest)
        if pack_id == "ears":
            speech = getattr(request.app.state, "local_speech_provider", None)
            if speech is not None and callable(getattr(speech, "refresh_runtime", None)):
                result["speech_runtime"] = speech.refresh_runtime().__dict__
        return result
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None


@router.post("/{pack_id}/self-test")
def self_test_pack(pack_id: str,
                   _principal: AuthenticatedPrincipal = Depends(require_permission("capability-pack:manage")),
                   packs=Depends(manager)):
    try:
        return packs.self_test(pack_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from None
