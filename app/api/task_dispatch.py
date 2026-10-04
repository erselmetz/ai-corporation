"""Permission-gated local worker dispatch and queue recovery routes."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.application.services.task_dispatch import (
    TaskDispatchConflict,
    TaskDispatchNotFound,
    TaskDispatchUnavailable,
)
from .models import (
    TaskDispatchQueueEntryResponse,
    TaskDispatchQueueResponse,
    TaskDispatchRequest,
    TaskDispatchResolutionRequest,
)
from .security import require_permission


router = APIRouter()


def get_application_service(request: Request):
    return request.app.state.application_service


@router.get(
    "/api/task-dispatch/queue",
    response_model=TaskDispatchQueueResponse,
    dependencies=[Depends(require_permission("task:dispatch"))],
)
def get_dispatch_queue(service=Depends(get_application_service)):
    try:
        return service.task_dispatch().list_queue()
    except TaskDispatchConflict as error:
        raise HTTPException(409, str(error)) from None


@router.post(
    "/api/tasks/{task_id}/dispatch",
    response_model=TaskDispatchQueueEntryResponse,
    dependencies=[Depends(require_permission("task:dispatch"))],
)
def dispatch_task(
    task_id: str,
    body: TaskDispatchRequest,
    principal=Depends(require_permission("task:dispatch")),
    service=Depends(get_application_service),
):
    try:
        return service.task_dispatch().dispatch(
            principal.identity,
            task_id,
            confirmed=body.confirmed,
        )
    except TaskDispatchNotFound as error:
        raise HTTPException(404, str(error)) from None
    except TaskDispatchConflict as error:
        raise HTTPException(409, str(error)) from None
    except TaskDispatchUnavailable as error:
        raise HTTPException(503, str(error)) from None
    except ValueError:
        raise HTTPException(422, "Invalid Task dispatch request") from None
    except RuntimeError:
        raise HTTPException(
            502,
            "Dispatch outcome may be uncertain; inspect the queue before taking further action",
        ) from None


@router.post(
    "/api/task-dispatch/{entry_id}/resolve",
    response_model=TaskDispatchQueueEntryResponse,
    dependencies=[Depends(require_permission("task:dispatch"))],
)
def resolve_dispatch_entry(
    entry_id: str,
    body: TaskDispatchResolutionRequest,
    principal=Depends(require_permission("task:dispatch")),
    service=Depends(get_application_service),
):
    try:
        return service.task_dispatch().resolve(
            principal.identity,
            entry_id,
            resolution=body.resolution,
            confirmed=body.confirmed,
        )
    except TaskDispatchNotFound as error:
        raise HTTPException(404, str(error)) from None
    except TaskDispatchConflict as error:
        raise HTTPException(409, str(error)) from None
    except ValueError:
        raise HTTPException(422, "Invalid queue resolution request") from None
