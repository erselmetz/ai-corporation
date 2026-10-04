"""Explicit local-owner controls for review-only assignment recommendations."""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.application.services.assignment_policy import (
    AssignmentModelCandidate,
    AssignmentPolicy,
    CapabilityEvidence,
)
from .chat import bounded_body, contains_gemini_key, get_application_service
from .security import require_permission

router = APIRouter(prefix="/api/local/assignment-policy")


class EvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability: str = Field(min_length=1, max_length=128)
    kind: str
    supports: bool
    reference: str = Field(min_length=1, max_length=512)
    observed_at: datetime


class CandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: str = Field(min_length=1, max_length=256)
    model_id: str = Field(min_length=1, max_length=256)
    inventory_kind: str
    inventory_models: list[str] = Field(min_length=1, max_length=100)
    inventory_reference: str = Field(min_length=1, max_length=512)
    inventory_observed_at: datetime
    estimated_cost: Decimal | None = Field(default=None, ge=0)
    evidence: list[EvidenceRequest] = Field(default_factory=list, max_length=30)


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    allowed_provider_ids: list[str] = Field(default_factory=list, max_length=100)
    online_enabled: bool = False
    budget_limit: Decimal | None = Field(default=None, ge=0)
    budget_unit: str | None = Field(default=None, min_length=1, max_length=64)
    candidates: list[CandidateRequest] = Field(default_factory=list, max_length=100)


def _policy(payload: PolicyRequest) -> AssignmentPolicy:
    return AssignmentPolicy(
        enabled=payload.enabled,
        allowed_provider_ids=tuple(payload.allowed_provider_ids),
        online_enabled=payload.online_enabled,
        budget_limit=payload.budget_limit,
        budget_unit=payload.budget_unit,
        candidates=tuple(
            AssignmentModelCandidate(
                provider_id=candidate.provider_id,
                model_id=candidate.model_id,
                inventory_kind=candidate.inventory_kind,
                inventory_models=tuple(candidate.inventory_models),
                inventory_reference=candidate.inventory_reference,
                inventory_observed_at=candidate.inventory_observed_at,
                estimated_cost=candidate.estimated_cost,
                evidence=tuple(
                    CapabilityEvidence(
                        capability=item.capability,
                        kind=item.kind,
                        supports=item.supports,
                        reference=item.reference,
                        observed_at=item.observed_at,
                    )
                    for item in candidate.evidence
                ),
            )
            for candidate in payload.candidates
        ),
    )


def _payload(policy: AssignmentPolicy) -> dict:
    return {
        "enabled": policy.enabled,
        "allowed_provider_ids": list(policy.allowed_provider_ids),
        "online_enabled": policy.online_enabled,
        "budget_limit": str(policy.budget_limit) if policy.budget_limit is not None else None,
        "budget_unit": policy.budget_unit,
        "candidates": [
            {
                "provider_id": candidate.provider_id,
                "model_id": candidate.model_id,
                "inventory_kind": candidate.inventory_kind,
                "inventory_models": list(candidate.inventory_models),
                "inventory_reference": candidate.inventory_reference,
                "inventory_observed_at": candidate.inventory_observed_at.isoformat(),
                "estimated_cost": (
                    str(candidate.estimated_cost)
                    if candidate.estimated_cost is not None else None
                ),
                "evidence": [
                    {
                        "capability": item.capability,
                        "kind": item.kind,
                        "supports": item.supports,
                        "reference": item.reference,
                        "observed_at": item.observed_at.isoformat(),
                    }
                    for item in candidate.evidence
                ],
            }
            for candidate in policy.candidates
        ],
    }


def _parse(payload: bytes) -> PolicyRequest:
    try:
        body = PolicyRequest.model_validate_json(payload)
        _policy(body)
    except (ValueError, TypeError):
        raise HTTPException(422, "Invalid assignment policy fields") from None
    references = [body.budget_unit or "", *body.allowed_provider_ids]
    for candidate in body.candidates:
        references.extend((
            candidate.provider_id,
            candidate.model_id,
            candidate.inventory_reference,
            *candidate.inventory_models,
        ))
        for item in candidate.evidence:
            references.extend((item.capability, item.reference))
    if any(contains_gemini_key(value) for value in references):
        raise HTTPException(
            422,
            "Credential-like content is not allowed in assignment policy fields; it was not saved.",
        )
    return body


@router.get("")
def get_policy(
    principal=Depends(require_permission("assignment-policy:read")),
    service=Depends(get_application_service),
):
    return _payload(service.assignment_policy().get(principal.identity))


@router.put("")
async def configure_policy(
    payload=Depends(bounded_body),
    principal=Depends(require_permission("assignment-policy:manage")),
    service=Depends(get_application_service),
):
    body = _parse(payload)
    return _payload(
        service.assignment_policy().configure(principal.identity, _policy(body))
    )


@router.delete("")
def disable_policy(
    principal=Depends(require_permission("assignment-policy:manage")),
    service=Depends(get_application_service),
):
    return _payload(service.assignment_policy().disable(principal.identity))


@router.get("/preview")
def preview_policy(
    principal=Depends(require_permission("assignment-policy:read")),
    service=Depends(get_application_service),
):
    return service.assignment_policy().preview(principal.identity)
