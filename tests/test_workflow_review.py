from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time

import pytest
from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal
from app.application.services.provider_connections import ProviderRequestGate
from app.application.services.workflow_review import (
    WorkflowConflict,
    WorkflowReviewService,
    WorkNotStarted,
)
from app.local import create_local_app
from app.providers import AIProvider
from app.runtime.factory import create_corporation_runtime


PASSWORD = "test-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"
DESTINATIONS = [
    {"id": "local-a", "kind": "local", "provider_id": "ollama-a", "model_id": "m1", "agent_id": "w1"},
    {"id": "local-b", "kind": "local", "provider_id": "ollama-b", "model_id": "m1", "agent_id": "w2"},
    {"id": "on-1", "kind": "online", "provider_id": "gemini-1", "model_id": "g", "agent_id": "w3",
     "request_cost_cents": 5},
    {"id": "on-2", "kind": "online", "provider_id": "gemini-2", "model_id": "g", "agent_id": "w4",
     "request_cost_cents": 5, "fallback_authorized": True},
    {"id": "on-3", "kind": "online", "provider_id": "gemini-3", "model_id": "g", "agent_id": "w3",
     "request_cost_cents": 5, "fallback_authorized": True},
]


class FakeRunner:
    def __init__(self, slots=None):
        self.gate = ProviderRequestGate()
        for provider, count in (slots or {"ollama-a": 2, "ollama-b": 1, "gemini-1": 1,
                                       "gemini-2": 1, "gemini-3": 1}).items():
            self.gate.configure(provider, count)
        self.calls = []
        self.script = {}
        self.entered = Event()
        self.release = Event()
        self.block = False

    def __call__(self, destination, prompt):
        self.calls.append(destination.id)
        step = self.script.get(destination.id)
        if callable(step):
            step = step()
        if isinstance(step, Exception):
            raise step
        with self.gate.reserve(destination.provider_id, destination.model_id):
            if self.block is True or destination.id in (self.block or ()):
                self.entered.set()
                assert self.release.wait(5)
            return f"result from {destination.id}"


def make(runner=None, **options):
    runner = runner or FakeRunner()
    service = WorkflowReviewService(runner)
    report = service.create("owner", "Plan", destinations=DESTINATIONS, **options)
    return service, runner, report["id"]


def worker(service, wid, agent="w1", **kw):
    return service.add_item(wid, role="worker", agent_id=agent, prompt="do it", **kw)["id"]


def test_local_first_is_default_and_online_first_is_owner_selectable():
    mixed = [dict(DESTINATIONS[2], agent_id="x"), dict(DESTINATIONS[0], agent_id="x")]
    for preference, expected in (("local_first", "local-a"), ("online_first", "on-1")):
        runner = FakeRunner()
        service = WorkflowReviewService(runner)
        wid = service.create("o", "t", destinations=mixed, preference=preference,
                             spend_ceiling_cents=50)["id"]
        service.run(wid, worker(service, wid, "x"), confirmed=True, cloud_consent_destinations=["on-1"])
        assert runner.calls == [expected]
    service, runner, wid = make()
    assert service.create("o", "t", destinations=mixed)["preference"] == "local_first"

def test_review_is_not_approval_and_reviewer_must_differ():
    service, _, wid = make()
    item = worker(service, wid)
    done = service.run(wid, item, confirmed=True)
    assert done["state"] == "review"
    with pytest.raises(WorkflowConflict):
        service.approve(wid, item, "owner", confirmed=True, verification_evidence="x")
    with pytest.raises(WorkflowConflict, match="different Agent"):
        service.review(wid, item, reviewer_agent_id="w1", passed=True, evidence="self")
    reviewed = service.review(wid, item, reviewer_agent_id="r1", passed=True, evidence="checked output")
    assert reviewed["state"] == "reviewed"
    report = service.report(wid)
    assert report["state"] == "reviewed" and report["owner_approved"] is False
    with pytest.raises(WorkflowConflict):
        service.approve(wid, item, "owner", confirmed=False, verification_evidence="x")
    service.approve(wid, item, "owner", confirmed=True, verification_evidence="ran tests")
    assert service.report(wid)["owner_approved"] is True


def test_failed_review_never_succeeds():
    service, _, wid = make()
    item = worker(service, wid)
    service.run(wid, item, confirmed=True)
    assert service.review(wid, item, reviewer_agent_id="r1", passed=False, evidence="wrong")["state"] == "failed"
    with pytest.raises(WorkflowConflict):
        service.approve(wid, item, "owner", confirmed=True, verification_evidence="x")


def test_shared_model_concurrency_is_bounded_by_configured_slots():
    runner = FakeRunner({"ollama-a": 2, "ollama-b": 1, "gemini-1": 1, "gemini-2": 1, "gemini-3": 1})
    runner.block = True
    service, _, wid = make(runner)
    ids = [worker(service, wid, "w1") for _ in range(3)]
    with ThreadPoolExecutor(3) as pool:
        futures = [pool.submit(service.run, wid, i, confirmed=True) for i in ids]
        assert runner.entered.wait(5)
        deadline = time.monotonic() + 5
        while sum(runner.gate._active.values()) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        runner.release.set()
        states = sorted(f.result()["state"] for f in futures)
    assert states == ["blocked", "review", "review"]
    blocked = next(i for i in service.report(wid)["items"] if i["state"] == "blocked")
    assert "capacity" in blocked["reason"].lower() and blocked["attempts"] == 1


def test_online_requires_consent_ceiling_and_known_cost():
    service, runner, wid = make()
    item = worker(service, wid, "w3")
    assert "consent" in service.run(wid, item, confirmed=True)["reason"]
    service.recover(wid, item, confirmed=True)
    assert "UNKNOWN" in service.run(wid, item, confirmed=True, cloud_consent_destinations=["on-1"])["reason"]
    assert runner.calls == []
    unknown_cost = [dict(DESTINATIONS[2], request_cost_cents=None)]
    wid = service.create("o", "t", destinations=unknown_cost, spend_ceiling_cents=100)["id"]
    item = worker(service, wid, "w3")
    assert "UNKNOWN" in service.run(wid, item, confirmed=True, cloud_consent_destinations=["on-1"])["reason"]


def test_spend_ceiling_is_enforced_across_the_run():
    service, runner, wid = make(spend_ceiling_cents=5)
    first, second = worker(service, wid, "w3"), worker(service, wid, "w3")
    service.run(wid, first, confirmed=True, cloud_consent_destinations=["on-1"])
    blocked = service.run(wid, second, confirmed=True, cloud_consent_destinations=["on-1"])
    assert blocked["state"] == "blocked" and "ceiling" in blocked["reason"]
    assert service.report(wid)["spent_cents"] == 5 and runner.calls == ["on-1"]


def test_quota_exhaustion_blocks_without_switching_or_retry_by_default():
    runner = FakeRunner({"ollama-a": 1, "ollama-b": 1, "gemini-1": 1, "gemini-2": 1, "gemini-3": 1})
    runner.gate._limits["gemini-1"] = 1
    runner.block = True
    service, _, wid = make(runner, spend_ceiling_cents=100)
    a, b = worker(service, wid, "w3"), worker(service, wid, "w3")
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(service.run, wid, a, confirmed=True, cloud_consent_destinations=["on-1", "on-3"])
        assert runner.entered.wait(5)
        second = service.run(wid, b, confirmed=True, cloud_consent_destinations=["on-1", "on-3"])
        runner.release.set()
        first.result()
    assert second["state"] == "blocked"
    assert runner.calls.count("on-3") == 0 and service.report(wid)["spent_cents"] == 5


def test_fallback_only_to_authorized_destination_with_consent_and_budget():
    runner = FakeRunner()
    runner.block = {"on-1"}
    service, _, wid = make(runner, spend_ceiling_cents=100, fallback_enabled=True)
    a, b = worker(service, wid, "w3"), worker(service, wid, "w3")
    consent = ["on-1", "on-3"]
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(service.run, wid, a, confirmed=True, cloud_consent_destinations=consent)
        assert runner.entered.wait(5)
        second = service.run(wid, b, confirmed=True, cloud_consent_destinations=consent)
        runner.release.set()
        first.result()
    assert second["state"] == "review" and second["destination_id"] == "on-3"
    assert service.report(wid)["spent_cents"] == 10
    runner2 = FakeRunner()
    runner2.block = {"on-1"}
    service, _, wid = make(runner2, spend_ceiling_cents=100, fallback_enabled=True)
    a, b = worker(service, wid, "w3"), worker(service, wid, "w3")
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(service.run, wid, a, confirmed=True, cloud_consent_destinations=["on-1"])
        assert runner2.entered.wait(5)
        blocked = service.run(wid, b, confirmed=True, cloud_consent_destinations=["on-1"])
        runner2.release.set()
        first.result()
    assert blocked["state"] == "blocked" and "on-3" not in runner2.calls


def test_one_retry_only_when_provider_confirms_not_started():
    service, runner, wid = make()
    runner.script["local-a"] = WorkNotStarted("refused")
    item = worker(service, wid)
    assert service.run(wid, item, confirmed=True)["state"] == "failed"
    assert runner.calls == ["local-a", "local-a"]
    sequence = iter([WorkNotStarted("once"), None])
    runner.script["local-a"] = lambda: next(sequence)
    service2 = WorkflowReviewService(runner)
    wid = service2.create("o", "t", destinations=DESTINATIONS)["id"]
    runner.calls.clear()
    assert service2.run(wid, worker(service2, wid), confirmed=True)["state"] == "review"
    assert runner.calls == ["local-a", "local-a"]


@pytest.mark.parametrize("error", [TimeoutError("slow"), RuntimeError("unknown")])
def test_uncertain_outcomes_are_never_retried(error):
    service, runner, wid = make()
    runner.script["local-a"] = error
    item = service.run(wid, worker(service, wid), confirmed=True)
    assert item["state"] == "failed" and item["uncertain"] is True
    assert runner.calls == ["local-a"]


def test_delegation_bounds_and_lower_limits():
    service, _, wid = make(max_depth=2, max_children=2)
    root = service.add_item(wid, role="planner", agent_id="p", prompt="plan")["id"]
    child = service.add_item(wid, role="worker", agent_id="w1", prompt="a", parent_id=root)["id"]
    with pytest.raises(WorkflowConflict, match="depth"):
        service.add_item(wid, role="worker", agent_id="w1", prompt="b", parent_id=child)
    service.add_item(wid, role="worker", agent_id="w1", prompt="c", parent_id=root, source_id=child)
    with pytest.raises(WorkflowConflict, match="limit"):
        service.add_item(wid, role="worker", agent_id="w1", prompt="d", parent_id=root)
    assert service.report(wid)["handoffs"][0]["from"] == child
    with pytest.raises(ValueError):
        service.create("o", "t", destinations=DESTINATIONS, max_depth=4)
    with pytest.raises(ValueError):
        service.create("o", "t", destinations=DESTINATIONS, max_children=11)


def test_pause_resume_interruption_recovery_and_cancel_unsupported():
    runner = FakeRunner()
    runner.block = True
    service, _, wid = make(runner)
    item = worker(service, wid)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(service.run, wid, item, confirmed=True)
        assert runner.entered.wait(5)
        assert service.report(wid)["state"] == "running"
        with pytest.raises(WorkflowConflict, match="unsupported"):
            service.cancel(wid)
        assert service.mark_interrupted(wid)["state"] == "interrupted"
        runner.release.set()
        assert future.result()["state"] == "interrupted"
    with pytest.raises(WorkflowConflict, match="recovery"):
        service.resume(wid)
    service.recover(wid, item, confirmed=True)
    runner.block = False
    with pytest.raises(WorkflowConflict, match="paused"):
        service.run(wid, item, confirmed=True)
    assert service.resume(wid)["paused"] is False
    assert service.run(wid, item, confirmed=True)["state"] == "review"


class ApiFake(AIProvider):
    def generate(self, model, prompt):
        return "api fake"


def test_local_owner_api_permissions_validation_and_unsupported_cancel():
    runtime = create_corporation_runtime()
    runtime.application_service.register_local_provider("ollama-a", ApiFake())
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    body = {"title": "T", "destinations": [
        {"id": "d", "kind": "local", "provider_id": "ollama-a", "model_id": "m", "agent_id": "w1"}]}
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/local/workflows").status_code == 401
        assert client.post("/api/local/login", json={"password": PASSWORD},
                           headers={"Origin": ORIGIN}).status_code == 200
        headers = {"Origin": ORIGIN, "X-Local-CSRF": client.get("/api/local/session").json()["csrf"]}
        bad = dict(body, destinations=[dict(body["destinations"][0], kind="online")])
        assert client.post("/api/local/workflows", json=bad, headers=headers).status_code == 422
        created = client.post("/api/local/workflows", json=body, headers=headers)
        assert created.status_code == 201
        wid = created.json()["id"]
        item = client.post(f"/api/local/workflows/{wid}/items", headers=headers, json={
            "role": "worker", "agent_id": "w1", "prompt": "go"}).json()["id"]
        assert client.post(f"/api/local/workflows/{wid}/items/{item}/run", headers=headers,
                           json={"confirmed": False}).status_code == 409
        ran = client.post(f"/api/local/workflows/{wid}/items/{item}/run", headers=headers,
                          json={"confirmed": True})
        assert ran.json()["state"] == "review"
        assert client.post(f"/api/local/workflows/{wid}/cancel", headers=headers, json={}).status_code == 409
        assert client.get(f"/api/local/workflows/{wid}", headers=headers).json()["cancellation"] == "unsupported"
        client.app.state.authentication_backend.principal = AuthenticatedPrincipal(
            "local-owner", frozenset({"workflow:read"}))
        assert client.post(f"/api/local/workflows/{wid}/pause", headers=headers, json={}).status_code == 403
        assert client.get("/api/local/workflows", headers=headers).status_code == 200
