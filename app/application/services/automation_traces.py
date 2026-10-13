"""Bounded, owner-scoped metadata traces for approved automation actions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import threading
from typing import Protocol
from uuid import uuid4


MAX_TRACE_RECORDS = 200
MAX_TRACE_TTL_SECONDS = 86_400
MAX_SCREENSHOT_REFERENCES = 4
_APPROVAL_ID = re.compile(r"^[0-9a-f]{32}$")
_ACTOR_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_POLICY_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_ACTION_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_TARGET_REF = re.compile(
    r"^(?:browser:[a-z0-9.-]{1,253}|desktop:[a-z0-9._-]{1,128}:[0-9]{1,10}:[0-9]{1,20})$"
)
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SCREENSHOT_ID = re.compile(r"^scr_[A-Za-z0-9_-]{16,64}$")
_CONSENT_ID = re.compile(r"^cons_[A-Za-z0-9_-]{8,64}$")


class AutomationTraceError(RuntimeError):
    """Safe failure from the local metadata-only automation trace store."""


class ScreenshotReferenceValidator(Protocol):
    def is_permitted(self, *, actor_id: str, reference: ScreenshotReference) -> bool: ...


@dataclass(frozen=True, slots=True)
class ScreenshotReference:
    """Opaque screenshot ID and consent receipt; never contains image bytes or a path."""

    reference_id: str
    consent_id: str
    expires_at: str


@dataclass(frozen=True, slots=True)
class AutomationTraceRecord:
    trace_id: str
    actor_id: str
    capability_id: str
    grant_id: str
    grant_type: str
    policy_version: str
    target_ref: str
    action_id: str
    before_state: str
    before_digest: str
    action_result: str
    remote_outcome: str
    after_state: str
    after_digest: str | None
    started_at: str
    finished_at: str
    duration_milliseconds: int
    screenshot_references: tuple[str, ...]
    screenshot_consent_ids: tuple[str, ...]
    recovery_guidance: str
    retained_until: str


class AutomationTraceService:
    """Process-local bounded trace records with owner-scoped inspection and dry replay."""

    def __init__(
        self,
        *,
        max_records: int = MAX_TRACE_RECORDS,
        retention_seconds: int = MAX_TRACE_TTL_SECONDS,
        clock=None,
        screenshot_reference_validator: ScreenshotReferenceValidator | None = None,
    ):
        if type(max_records) is not int or not 1 <= max_records <= MAX_TRACE_RECORDS:
            raise ValueError("Trace capacity must be between 1 and 200 records")
        if (type(retention_seconds) is not int
                or not 60 <= retention_seconds <= MAX_TRACE_TTL_SECONDS):
            raise ValueError("Trace retention must be between one minute and one day")
        self._max_records = max_records
        self._retention_seconds = retention_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._screenshot_validator = screenshot_reference_validator
        self._records: dict[str, AutomationTraceRecord] = {}
        self._lock = threading.RLock()

    def record_action(
        self,
        *,
        actor_id: str,
        capability_id: str,
        grant_id: str,
        policy_version: str,
        target_ref: str,
        action_id: str,
        before_digest: str,
        action_result: str,
        remote_outcome: str,
        started_at: datetime,
        finished_at: datetime | None = None,
        after_digest: str | None = None,
        after_state: str | None = None,
        screenshot_references: tuple[ScreenshotReference, ...] = (),
    ) -> AutomationTraceRecord:
        _validate_text(actor_id, _ACTOR_ID, "Actor identity")
        _validate_text(policy_version, _POLICY_ID, "Policy version")
        if capability_id not in {"browser:act", "desktop:act"}:
            raise ValueError("Automation capability is unsupported")
        if not isinstance(grant_id, str) or not _APPROVAL_ID.fullmatch(grant_id):
            raise ValueError("Trace grant must reference an exact one-use action approval")
        if not isinstance(target_ref, str) or not _TARGET_REF.fullmatch(target_ref):
            raise ValueError("Trace target must use a sanitized browser host or desktop window reference")
        if not isinstance(action_id, str) or not _ACTION_ID.fullmatch(action_id):
            raise ValueError("Trace action identifier is invalid")
        if not isinstance(before_digest, str) or not _DIGEST.fullmatch(before_digest):
            raise ValueError("Trace before evidence must be a SHA-256 digest")
        if after_digest is not None and (not isinstance(after_digest, str) or not _DIGEST.fullmatch(after_digest)):
            raise ValueError("Trace after evidence must be a SHA-256 digest")
        if action_result not in {
            "dispatched", "failed_before_dispatch", "timed_out_unknown", "failed_unknown",
        }:
            raise ValueError("Trace action result is not supported")
        if remote_outcome not in {"unknown", "not_dispatched"}:
            raise ValueError("Trace remote outcome is not supported")
        if (action_result == "dispatched" and remote_outcome != "unknown"
                or action_result == "failed_before_dispatch" and remote_outcome != "not_dispatched"
                or action_result in {"timed_out_unknown", "failed_unknown"}
                and remote_outcome != "unknown"):
            raise ValueError("Trace action and remote outcome are inconsistent")
        if after_state is not None and after_state not in {"observed", "unknown", "not_observed"}:
            raise ValueError("Trace after state is unsupported")
        if after_digest is not None and after_state != "observed":
            raise ValueError("After evidence digest requires an explicit read-only observation")
        if after_state == "observed" and after_digest is None:
            raise ValueError("Observed after state requires a bounded evidence digest")
        if not isinstance(screenshot_references, tuple) or len(screenshot_references) > MAX_SCREENSHOT_REFERENCES:
            raise ValueError("Trace screenshot references must be a tuple of at most four IDs")
        refs, consent_ids = self._validate_screenshot_references(actor_id, screenshot_references)
        started = _normalize_time(started_at, "Trace start")
        finished = _normalize_time(finished_at or self._now(), "Trace finish")
        elapsed = int((finished - started).total_seconds() * 1000)
        if elapsed < 0 or elapsed > self._retention_seconds * 1000:
            raise ValueError("Trace action duration is outside the retention bound")
        created_at = self._now()
        trace = AutomationTraceRecord(
            trace_id=uuid4().hex, actor_id=actor_id,
            capability_id=capability_id, grant_id=grant_id, grant_type="one_use_action_approval",
            policy_version=policy_version, target_ref=target_ref, action_id=action_id,
            before_state="observed", before_digest=before_digest,
            action_result=action_result, remote_outcome=remote_outcome,
            after_state=(after_state or ("unknown" if remote_outcome == "unknown" else "not_observed")),
            after_digest=after_digest, started_at=started.isoformat(), finished_at=finished.isoformat(),
            duration_milliseconds=elapsed, screenshot_references=refs,
            screenshot_consent_ids=consent_ids,
            recovery_guidance=("inspect_manually_no_retry" if remote_outcome == "unknown"
                               else "review_target_and_request_new_approval"),
            retained_until=(created_at + timedelta(seconds=self._retention_seconds)).isoformat(),
        )
        with self._lock:
            self._prune_locked(created_at)
            if len(self._records) >= self._max_records:
                oldest_id = min(self._records, key=lambda key: self._records[key].finished_at)
                del self._records[oldest_id]
            self._records[trace.trace_id] = trace
        return trace

    def get(self, trace_id: str, *, actor_id: str) -> AutomationTraceRecord:
        now = self._now()
        with self._lock:
            self._prune_locked(now)
            trace = self._records.get(trace_id)
            if trace is None or trace.actor_id != actor_id:
                raise AutomationTraceError("Automation trace is unavailable")
            return trace

    def list_for_actor(self, *, actor_id: str, limit: int = 50) -> tuple[AutomationTraceRecord, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Trace list limit must be between 1 and 100")
        now = self._now()
        with self._lock:
            self._prune_locked(now)
            values = [trace for trace in self._records.values() if trace.actor_id == actor_id]
            values.sort(key=lambda trace: trace.finished_at, reverse=True)
            return tuple(values[:limit])

    def simulate_replay(self, trace_id: str, *, actor_id: str) -> dict:
        trace = self.get(trace_id, actor_id=actor_id)
        return {
            "trace_id": trace.trace_id,
            "mode": "inspection_only_simulation",
            "would_repeat_action": False,
            "external_effects": "none",
            "phases": (
                {"phase": "before", "state": trace.before_state,
                 "evidence_digest": trace.before_digest},
                {"phase": "action", "result": trace.action_result,
                 "remote_outcome": trace.remote_outcome},
                {"phase": "after", "state": trace.after_state,
                 "evidence_digest": trace.after_digest},
            ),
            "recovery_guidance": trace.recovery_guidance,
            "screenshot_references": trace.screenshot_references,
        }

    def _validate_screenshot_references(
        self, actor_id: str, references: tuple[ScreenshotReference, ...],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if references and self._screenshot_validator is None:
            raise ValueError("No consent-bound screenshot reference validator is configured")
        ids: list[str] = []
        consents: list[str] = []
        for reference in references:
            if not isinstance(reference, ScreenshotReference):
                raise ValueError("Only opaque screenshot reference records are accepted")
            if (not _SCREENSHOT_ID.fullmatch(reference.reference_id)
                    or not _CONSENT_ID.fullmatch(reference.consent_id)):
                raise ValueError("Screenshot reference IDs must be opaque and bounded")
            expiry = _normalize_time(reference.expires_at, "Screenshot reference expiry")
            if expiry <= self._now():
                raise ValueError("Expired screenshot references cannot be retained")
            if not self._screenshot_validator.is_permitted(actor_id=actor_id, reference=reference):
                raise ValueError("Screenshot reference lacks valid owner consent")
            ids.append(reference.reference_id)
            consents.append(reference.consent_id)
        return tuple(ids), tuple(consents)

    def _prune_locked(self, now: datetime) -> None:
        for trace_id, trace in tuple(self._records.items()):
            if _normalize_time(trace.retained_until, "Trace expiry") <= now:
                del self._records[trace_id]

    def _now(self) -> datetime:
        return _normalize_time(self._clock(), "Trace clock")


def _validate_text(value: str, pattern: re.Pattern[str], label: str) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"{label} is invalid")


def _normalize_time(value: datetime | str, label: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(f"{label} is invalid") from None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)
