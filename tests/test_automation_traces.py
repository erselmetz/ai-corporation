rom __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.application.services.automation_traces import (
    AutomationTraceError,
    AutomationTraceService,
    ScreenshotReference,
)


NOW = datetime(2036, 4, 5, 6, 7, tzinfo=timezone.utc)
ACTOR = "local-owner"
APPROVAL = "0123456789abcdef0123456789abcdef"
DIGEST = "a" * 64


def record(service, **overrides):
    values = {
        "actor_id": ACTOR,
        "capability_id": "desktop:act",
        "grant_id": APPROVAL,
        "policy_version": "capability-risk-v1",
        "target_ref": "desktop:notepad.exe:4242:161616",
        "action_id": "desktop.invoke_button",
        "before_digest": DIGEST,
        "action_result": "dispatched",
        "remote_outcome": "unknown",
        "started_at": NOW - timedelta(milliseconds=125),
        "finished_at": NOW,
    }
    values.update(overrides)
    return service.record_action(**values)


def test_trace_binds_approval_policy_actor_target_action_timing_and_unknown_outcome():
    service = AutomationTraceService(clock=lambda: NOW)
    trace = record(service)

    assert trace.trace_id
    assert trace.actor_id == ACTOR
    assert trace.capability_id == "desktop:act"
    assert trace.grant_id == APPROVAL
    assert trace.grant_type == "one_use_action_approval"
    assert trace.policy_version == "capability-risk-v1"
    assert trace.target_ref == "desktop:notepad.exe:4242:161616"
    assert trace.action_id == "desktop.invoke_button"
    assert trace.before_digest == DIGEST
    assert trace.after_state == "unknown"
    assert trace.after_digest is None
    assert trace.remote_outcome == "unknown"
    assert trace.duration_milliseconds == 125
    assert trace.recovery_guidance == "inspect_manually_no_retry"
    assert trace.screenshot_references == ()
    assert service.get(trace.trace_id, actor_id=ACTOR) == trace
    with pytest.raises(AutomationTraceError):
        service.get(trace.trace_id, actor_id="different-owner")


def test_replay_simulation_describes_phases_without_repeating_side_effects():
    service = AutomationTraceService(clock=lambda: NOW)
    trace = record(service)

    simulation = service.simulate_replay(trace.trace_id, actor_id=ACTOR)

    assert simulation["mode"] == "inspection_only_simulation"
    assert simulation["would_repeat_action"] is False
    assert simulation["external_effects"] == "none"
    assert [phase["phase"] for phase in simulation["phases"]] == ["before", "action", "after"]
    assert simulation["phases"][2]["state"] == "unknown"
    assert simulation["screenshot_references"] == ()


def test_failed_before_dispatch_is_distinct_and_uses_review_guidance():
    service = AutomationTraceService(clock=lambda: NOW)
    trace = record(
        service, action_result="failed_before_dispatch", remote_outcome="not_dispatched",
    )
    assert trace.action_result == "failed_before_dispatch"
    assert trace.after_state == "not_observed"
    assert trace.recovery_guidance == "review_target_and_request_new_approval"


def test_trace_retention_and_capacity_are_bounded():
    now = [NOW]
    service = AutomationTraceService(max_records=1, retention_seconds=60, clock=lambda: now[0])
    first = record(service)
    second = record(service, started_at=NOW - timedelta(milliseconds=100))
    assert service.list_for_actor(actor_id=ACTOR) == (second,)
    with pytest.raises(AutomationTraceError):
        service.get(first.trace_id, actor_id=ACTOR)

    now[0] += timedelta(seconds=61)
    assert service.list_for_actor(actor_id=ACTOR) == ()


def test_trace_rejects_raw_or_unbounded_diagnostic_fields():
    service = AutomationTraceService(clock=lambda: NOW)
    with pytest.raises(ValueError):
        record(service, target_ref="https://example.com/path?token=secret")
    with pytest.raises(ValueError):
        record(service, action_id="click secret password=abc")
    with pytest.raises(ValueError):
        record(service, grant_id="not-an-approval")
    with pytest.raises(ValueError):
        record(service, after_digest=DIGEST)
    observed = record(service, after_digest="b" * 64, after_state="observed")
    assert observed.after_digest == "b" * 64
    assert observed.after_state == "observed"
    with pytest.raises(ValueError):
        record(service, action_result="failed", remote_outcome="raw exception path")


def test_screenshot_references_require_owner_consent_validation_and_store_ids_only():
    reference = ScreenshotReference(
        "scr_1234567890abcdef", "cons_12345678", (NOW + timedelta(minutes=5)).isoformat(),
    )
    service = AutomationTraceService(clock=lambda: NOW)
    with pytest.raises(ValueError, match="No consent-bound"):
        record(service, screenshot_references=(reference,))

    class ConsentValidator:
        def is_permitted(self, *, actor_id, reference):
            return actor_id == ACTOR and reference.consent_id == "cons_12345678"

    service = AutomationTraceService(
        clock=lambda: NOW, screenshot_reference_validator=ConsentValidator(),
    )
    trace = record(service, screenshot_references=(reference,))
    assert trace.screenshot_references == ("scr_1234567890abcdef",)
    assert trace.screenshot_consent_ids == ("cons_12345678",)
    assert not hasattr(trace, "image_bytes")


def test_expired_screenshot_reference_is_rejected():
    class ConsentValidator:
        def is_permitted(self, **_kwargs):
            return True

    service = AutomationTraceService(clock=lambda: NOW, screenshot_reference_validator=ConsentValidator())
    reference = ScreenshotReference("scr_1234567890abcdef", "cons_12345678",
                                    (NOW - timedelta(seconds=1)).isoformat())
    with pytest.raises(ValueError, match="Expired screenshot"):
        record(service, screenshot_references=(reference,))
