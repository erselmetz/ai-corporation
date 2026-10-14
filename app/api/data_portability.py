"""Explicit owner-only encrypted backup and restore endpoints."""
import json
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.api.security import require_permission
from app.portability.backups import BackupError, DataPortabilityService, MAX_BACKUP_BYTES

router = APIRouter(prefix="/api/local/backup", tags=["local-data-portability"])


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passphrase: str = Field(min_length=12, max_length=1024, repr=False)
    include_private_data: bool = False


def _service(request: Request) -> DataPortabilityService:
    return request.app.state.data_portability_service


def _safe(error: BackupError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


async def _read_upload(file: UploadFile) -> bytes:
    try:
        content = await file.read(MAX_BACKUP_BYTES + 1)
        if len(content) > MAX_BACKUP_BYTES:
            raise HTTPException(413, "Backup file exceeds the supported size")
        return content
    finally:
        await file.close()


@router.get("/preview", dependencies=[Depends(require_permission("backup:read"))])
def preview(include_private_data: bool = False, service: DataPortabilityService = Depends(_service)):
    try:
        return service.preview(include_private_data=include_private_data)
    except BackupError as error:
        raise _safe(error) from None


@router.get("/diagnostics", dependencies=[Depends(require_permission("backup:export"))])
def diagnostics(service: DataPortabilityService = Depends(_service)):
    try:
        payload = service.diagnostics()
    except BackupError as error:
        raise _safe(error) from None
    return Response(
        json.dumps(payload, ensure_ascii=True, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="erselmetz-ai-diagnostics.json"',
                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/export", dependencies=[Depends(require_permission("backup:export"))])
def export(body: ExportRequest, service: DataPortabilityService = Depends(_service)):
    try:
        payload = service.export(body.passphrase, include_private_data=body.include_private_data)
    except BackupError as error:
        raise _safe(error) from None
    return Response(
        payload,
        media_type="application/vnd.erselmetz.backup",
        headers={"Content-Disposition": 'attachment; filename="erselmetz-ai-backup.erselbackup"',
                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/inspect", dependencies=[Depends(require_permission("backup:read"))])
async def inspect(file: UploadFile = File(...), passphrase: str = Form(..., min_length=12, max_length=1024),
                  service: DataPortabilityService = Depends(_service)):
    payload = await _read_upload(file)
    try:
        return await run_in_threadpool(service.inspect, payload, passphrase)
    except BackupError as error:
        raise _safe(error) from None


@router.post("/restore", dependencies=[Depends(require_permission("backup:restore"))])
async def restore(request: Request, file: UploadFile = File(...), passphrase: str = Form(..., min_length=12, max_length=1024),
                  confirmation: str = Form(..., max_length=16),
                  service: DataPortabilityService = Depends(_service)):
    payload = await _read_upload(file)
    if confirmation != "RESTORE":
        raise HTTPException(400, "Type RESTORE to confirm replacing application data")
    try:
        # Reject a wrong passphrase or invalid file before closing the API. Once
        # verification succeeds, keep the restart gate closed even if applying
        # the restore fails: SQLite may already have replaced some on-disk state.
        await run_in_threadpool(service.inspect, payload, passphrase)
    except BackupError as error:
        raise _safe(error) from None
    request.app.state.data_restore_requires_restart = True
    try:
        result = await run_in_threadpool(service.restore, payload, passphrase, confirmed=True)
    except BackupError as error:
        raise _safe(error) from None
    except Exception:
        # Unknown failures may occur after SQLite applied the verified snapshot.
        # Keep the restart gate closed rather than claiming the old state remains active.
        raise HTTPException(500, "Restore did not complete cleanly. Restart the app and verify its data before continuing.") from None
    return result
