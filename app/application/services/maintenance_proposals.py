"""Caller-authored, review-only proposals linked to diagnostic reports."""

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
import re

from .diagnostics import DiagnosticReport


_PROPOSAL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


@dataclass(frozen=True, slots=True)
class MaintenanceProposal:
    proposal_id: str
    diagnostic: DiagnosticReport
    title: str
    proposed_change: str
    scope: str
    risk: str
    created_at: datetime


class MaintenanceProposalService:
    MAX_PROPOSALS = 100

    def __init__(self):
        self._proposals: dict[str, MaintenanceProposal] = {}
        self._lock = RLock()

    def create(
        self,
        proposal_id: str,
        diagnostic: DiagnosticReport,
        *,
        title: str,
        proposed_change: str,
        scope: str,
        risk: str,
    ) -> MaintenanceProposal:
        if not isinstance(proposal_id, str) or not _PROPOSAL_ID.fullmatch(proposal_id):
            raise ValueError("Proposal ID must be a bounded identifier")
        if not isinstance(diagnostic, DiagnosticReport):
            raise TypeError("Expected DiagnosticReport")
        _validate_text(title, "title", 256, allow_empty=False)
        _validate_text(proposed_change, "proposed_change", 8192, allow_empty=False)
        _validate_text(scope, "scope", 2048, allow_empty=False)
        _validate_text(risk, "risk", 2048, allow_empty=False)

        proposal = MaintenanceProposal(
            proposal_id,
            diagnostic,
            title,
            proposed_change,
            scope,
            risk,
            datetime.now(timezone.utc),
        )
        with self._lock:
            if proposal_id in self._proposals:
                raise ValueError(f"Maintenance proposal already exists: {proposal_id}")
            if len(self._proposals) >= self.MAX_PROPOSALS:
                raise ValueError("Maintenance proposal limit reached")
            self._proposals[proposal_id] = proposal
            return proposal

    def get(self, proposal_id: str) -> MaintenanceProposal:
        if not isinstance(proposal_id, str) or not _PROPOSAL_ID.fullmatch(proposal_id):
            raise ValueError("Proposal ID must be a bounded identifier")
        with self._lock:
            try:
                return self._proposals[proposal_id]
            except KeyError:
                raise ValueError(f"Maintenance proposal not found: {proposal_id}") from None

    def all(self) -> tuple[MaintenanceProposal, ...]:
        with self._lock:
            return tuple(self._proposals.values())


def _validate_text(
    value: str,
    name: str,
    max_bytes: int,
    *,
    allow_empty: bool = True,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    if not allow_empty and not value.strip():
        raise ValueError(f"{name} cannot be empty")
    try:
        encoded_size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError(f"{name} must contain valid Unicode text") from exc
    if encoded_size > max_bytes:
        raise ValueError(f"{name} exceeds byte limit")
