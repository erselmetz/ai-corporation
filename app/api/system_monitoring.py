"""Protected, on-demand system and software-capacity snapshot."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.application.services.system_monitoring import SystemMonitoringReport
from .security import require_permission


router = APIRouter(prefix="/api/system")


def _snapshot(report: SystemMonitoringReport) -> dict:
    return {
        "observed_at": report.observed_at.isoformat(),
        "task_status_counts": [
            {"status": status.value, "count": count}
            for status, count in report.task_status_counts
        ],
        "registered_provider_ids": list(report.registered_provider_ids),
        "omitted_provider_count": report.omitted_provider_count,
        "provider_availability": report.provider_availability.value,
        "resource_capacities": None if report.resource_capacities is None else [
            {"scope": item.scope.value, "limit": item.limit, "allocated": item.allocated,
             "remaining": item.remaining, "provider_id": item.provider_id,
             "model_id": item.model_id}
            for item in report.resource_capacities
        ],
        "signals": [
            {"type": signal.type.value, "task_ids": list(signal.task_ids),
             "omitted_task_count": signal.omitted_task_count,
             "capacity": None if signal.capacity is None else {
                 "scope": signal.capacity.scope.value, "limit": signal.capacity.limit,
                 "allocated": signal.capacity.allocated,
                 "remaining": signal.capacity.remaining,
                 "provider_id": signal.capacity.provider_id,
                 "model_id": signal.capacity.model_id,
             }}
            for signal in report.signals
        ],
    }


@router.get("/monitor", dependencies=[Depends(require_permission("system:read"))])
def system_monitor(request: Request):
    try:
        return _snapshot(request.app.state.application_service.monitor_system())
    except (RuntimeError, TypeError, ValueError):
        raise HTTPException(503, "System snapshot unavailable") from None
