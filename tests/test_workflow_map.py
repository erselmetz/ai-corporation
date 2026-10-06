from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal
from app.application.services.workflow_map import build_workflow_map
from app.application.services.workflow_review import WorkflowReviewService, WorkNotStarted
from app.local import create_local_app
from app.runtime.factory import create_corporation_runtime

PASSWORD = "test-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"
READ = frozenset({"workflow:read", "agent:read", "position:read"})
DEST = [{"id": "d1", "kind": "local", "provider_id": "ollama-a", "model_id": "m", "agent_id": "w1"}]


class App:
    def __init__(self, runner=lambda dest, prompt: "OUTPUT-BODY", positions=()):
        self.service = WorkflowReviewService(runner)
        self._positions = positions

    def workflow_review(self):
        return self.service

    def list_positions(self):
        return self._positions


def pos(pid, title, parent=None):
    return NS(id=pid, title=title, reports_to_position_id=parent)


def seeded():
    app = App(positions=(pos("p1", "Architect"), pos("p2", "Developer", "p1"), pos("p3", "QA", "ghost")))
    wid = app.service.create("owner", "Plan", destinations=DEST)["id"]
    first = app.service.add_item(wid, role="worker", agent_id="w1", prompt="SECRET-PROMPT")["id"]
    second = app.service.add_item(wid, role="worker", agent_id="w1", prompt="p", parent_id=first,
                                  source_id=first)["id"]
    return app, wid, first, second


def test_operational_and_reporting_edges_are_kept_separate_and_content_is_omitted():
    app, wid, first, second = seeded()
    app.service.run(wid, first, confirmed=True)
    report = build_workflow_map(app, READ)
    workflow = report["workflows"][0]
    kinds = {(e["kind"], e["from"], e["to"]) for e in workflow["operational_edges"]}
    assert kinds == {("delegation", first, second), ("handoff", first, second)}
    org = report["organization"]
    assert org["reporting_edges"] == [{"kind": "reporting", "from": "p2", "to": "p1"}]
    assert not any(e["kind"] == "reporting" for e in workflow["operational_edges"])
    blob = str(report)
    assert "SECRET-PROMPT" not in blob and "OUTPUT-BODY" not in blob
    node = next(n for n in workflow["nodes"] if n["id"] == first)
    assert node["output_recorded"] is True and node["state"] == "review"


def test_outcome_evidence_and_state_changes_follow_records():
    app, wid, first, _ = seeded()
    app.service.run(wid, first, confirmed=True)
    app.service.review(wid, first, reviewer_agent_id="r1", passed=True, evidence="checked")
    app.service.approve(wid, first, "owner", confirmed=True, verification_evidence="ran tests")
    node = next(n for n in build_workflow_map(app, READ)["workflows"][0]["nodes"] if n["id"] == first)
    assert node["state"] == "approved"
    assert node["review"]["evidence"] == "checked" and node["approval"]["evidence"] == "ran tests"


def test_raw_errors_are_omitted_and_uncertain_outcomes_are_flagged():
    def boom(dest, prompt):
        raise RuntimeError("api_key=AIzaSECRET at C:\\private\\trace")

    app = App(boom)
    wid = app.service.create("owner", "T", destinations=DEST)["id"]
    item = app.service.add_item(wid, role="worker", agent_id="w1", prompt="p")["id"]
    app.service.run(wid, item, confirmed=True)
    report = build_workflow_map(app, READ)
    assert "AIzaSECRET" not in str(report)
    node = report["workflows"][0]["nodes"][0]
    assert node["state"] == "failed" and node["uncertain"] is True


def test_not_started_failure_reason_omits_provider_text():
    def never(dest, prompt):
        raise WorkNotStarted("token=SECRET-TOKEN")

    app = App(never)
    wid = app.service.create("owner", "T", destinations=DEST)["id"]
    item = app.service.add_item(wid, role="worker", agent_id="w1", prompt="p")["id"]
    app.service.run(wid, item, confirmed=True)
    report = build_workflow_map(app, READ)
    assert "SECRET-TOKEN" not in str(report)
    assert report["workflows"][0]["nodes"][0]["reason"] == "Retry did not start"


def test_forbidden_agents_and_positions_are_masked_not_dropped():
    app, wid, first, _ = seeded()
    app.service.run(wid, first, confirmed=True)
    report = build_workflow_map(app, frozenset({"workflow:read"}))
    node = report["workflows"][0]["nodes"][0]
    assert node["agent_id"] is None and node["destination_id"] is None
    assert node["agent_visibility"] == "forbidden"
    assert report["organization"] == {"state": "forbidden", "positions": [], "reporting_edges": []}
    with pytest.raises(PermissionError):
        build_workflow_map(app, frozenset({"agent:read"}))


def test_empty_and_freshness_contract():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    report = build_workflow_map(App(), READ, now=now)
    assert report["workflows"] == [] and report["generated_at"] == now.isoformat()
    assert report["stale_after_seconds"] == 60
    assert datetime.fromisoformat(report["generated_at"]) < now + timedelta(seconds=1)


def test_local_api_requires_workflow_read_and_is_not_a_workflow_id():
    runtime = create_corporation_runtime()
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/local/workflows/map").status_code == 401
        client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})
        body = client.get("/api/local/workflows/map")
        assert body.status_code == 200 and body.json()["workflows"] == []
        client.app.state.authentication_backend.principal = AuthenticatedPrincipal(
            "local-owner", frozenset({"position:read"}))
        assert client.get("/api/local/workflows/map").status_code == 403
        client.app.state.authentication_backend.principal = AuthenticatedPrincipal(
            "local-owner", frozenset({"workflow:read"}))
        partial = client.get("/api/local/workflows/map").json()
        assert partial["organization"]["state"] == "forbidden"