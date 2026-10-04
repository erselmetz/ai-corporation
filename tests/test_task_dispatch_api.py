from datetime import datetime, timezone

from fastapi import Request
from fastapi.testclient import TestClient

from app.agents import Agent
from app.api import AuthenticatedPrincipal, create_app
from app.local import create_local_app
from app.orchestrator.execution_queue import QueueState
from app.providers import OllamaProvider
from app.resources import ModelLimit, ProviderLimit, ResourceLimits
from app.runtime.factory import create_corporation_runtime


PASSWORD = "test-only-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"
NOW = datetime.now(timezone.utc)


class DispatchAuthenticationBackend:
    def authenticate(self, request: Request) -> AuthenticatedPrincipal | None:
        authorization = request.headers.get("Authorization")
        if authorization == "dispatch-owner":
            return AuthenticatedPrincipal(
                "dispatch-owner",
                frozenset({"task:dispatch", "task:read"}),
            )
        if authorization == "task-reader":
            return AuthenticatedPrincipal("reader", frozenset({"task:read"}))
        return None


def _configured_runtime():
    runtime = create_corporation_runtime()
    runtime.application_service.resource_manager(
        ResourceLimits(
            1,
            (ProviderLimit("ollama", 1),),
            (ModelLimit("ollama", "llama3.2:3b", 1),),
        )
    )
    project = runtime.application_service.create_project("Dispatch project", "")
    task = runtime.application_service.create_task(
        "Reviewed local work",
        "Use only the supplied Task description.",
        project_id=project.id,
        agent_id="local_worker",
    )
    return runtime, task


def _client(runtime):
    return TestClient(
        create_app(
            application_service=runtime.application_service,
            authentication_backend=DispatchAuthenticationBackend(),
        )
    )


def test_owner_dispatch_runs_one_local_task_and_records_actual_queue_outcome(monkeypatch):
    calls = []
    monkeypatch.setattr(
        OllamaProvider,
        "generate",
        lambda _self, model, prompt: calls.append((model, prompt)) or "Local result.",
    )
    runtime, task = _configured_runtime()

    with _client(runtime) as client:
        response = client.post(
            f"/api/tasks/{task.id}/dispatch",
            headers={"Authorization": "dispatch-owner"},
            json={"confirmed": True},
        )
        queue = client.get(
            "/api/task-dispatch/queue",
            headers={"Authorization": "dispatch-owner"},
        )
        replay = client.post(
            f"/api/tasks/{task.id}/dispatch",
            headers={"Authorization": "dispatch-owner"},
            json={"confirmed": True},
        )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["state"] == "completed"
    assert result["worker_id"] == "dispatch-owner"
    assert result["task"] == {
        "title": "Reviewed local work",
        "status": "completed",
        "result_recorded": True,
        "error_recorded": False,
    }
    assert len(calls) == 1
    assert calls[0][0] == "llama3.2:3b"
    assert "Use only the supplied Task description." in calls[0][1]
    assert queue.status_code == 200
    assert queue.json()["items"][0]["state"] == "completed"
    assert replay.status_code == 409
    assert len(calls) == 1


def test_dispatch_requires_narrow_permission_and_explicit_confirmation(monkeypatch):
    calls = []
    monkeypatch.setattr(
        OllamaProvider,
        "generate",
        lambda *args, **kwargs: calls.append((args, kwargs)) or "No call expected.",
    )
    runtime, task = _configured_runtime()

    with _client(runtime) as client:
        denied = client.post(
            f"/api/tasks/{task.id}/dispatch",
            headers={"Authorization": "task-reader"},
            json={"confirmed": True},
        )
        missing_confirmation = client.post(
            f"/api/tasks/{task.id}/dispatch",
            headers={"Authorization": "dispatch-owner"},
            json={"confirmed": False},
        )
        malformed_confirmation = client.post(
            f"/api/tasks/{task.id}/dispatch",
            headers={"Authorization": "dispatch-owner"},
            json={"confirmed": "true"},
        )

    assert denied.status_code == 403
    assert missing_confirmation.status_code == 409
    assert malformed_confirmation.status_code == 422
    assert runtime.application_service.get_task(task.id).status == "pending"
    assert runtime.application_service.execution_queue().list() == ()
    assert calls == []


def test_local_owner_dispatch_requires_same_origin_csrf(monkeypatch):
    monkeypatch.setattr(
        OllamaProvider,
        "generate",
        lambda *_args, **_kwargs: "Local owner result.",
    )
    runtime, task = _configured_runtime()
    app = create_local_app(
        password=PASSWORD,
        origin=ORIGIN,
        application_service=runtime.application_service,
    )
    with TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 50100),
    ) as client:
        login = client.post(
            "/api/local/login",
            json={"password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        session = client.get("/api/local/session").json()
        denied = client.post(
            f"/api/tasks/{task.id}/dispatch",
            json={"confirmed": True},
            headers={"Origin": ORIGIN},
        )
        dispatched = client.post(
            f"/api/tasks/{task.id}/dispatch",
            json={"confirmed": True},
            headers={"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]},
        )

    assert login.status_code == 200
    assert "task:dispatch" in session["permissions"]
    assert denied.status_code == 403
    assert dispatched.status_code == 200


def test_unconfigured_or_exhausted_budgets_never_admit_dispatch(monkeypatch):
    calls = []
    monkeypatch.setattr(
        OllamaProvider,
        "generate",
        lambda *args, **kwargs: calls.append((args, kwargs)) or "No call expected.",
    )
    runtime = create_corporation_runtime()
    project = runtime.application_service.create_project("Project", "")
    task = runtime.application_service.create_task(
        "Task", "Bounded description", project_id=project.id, agent_id="local_worker"
    )

    with _client(runtime) as client:
        unconfigured = client.post(
            f"/api/tasks/{task.id}/dispatch",
            headers={"Authorization": "dispatch-owner"},
            json={"confirmed": True},
        )

    assert unconfigured.status_code == 503
    assert runtime.application_service.get_task(task.id).status == "pending"
    assert runtime.application_service.execution_queue().list() == ()

    runtime, task = _configured_runtime()
    manager = runtime.application_service.resource_manager()
    manager.allocate(
        "occupied",
        provider_id="ollama",
        model_id="llama3.2:3b",
    )
    with _client(runtime) as client:
        exhausted = client.post(
            f"/api/tasks/{task.id}/dispatch",
            headers={"Authorization": "dispatch-owner"},
            json={"confirmed": True},
        )

    assert exhausted.status_code == 409
    assert runtime.application_service.get_task(task.id).status == "pending"
    assert runtime.application_service.execution_queue().list() == ()
    assert manager.snapshot().global_capacity.allocated == 1
    assert calls == []


def test_dispatch_rejects_cloud_and_non_loopback_provider_targets(monkeypatch):
    calls = []
    monkeypatch.setattr(
        OllamaProvider,
        "generate",
        lambda *args, **kwargs: calls.append((args, kwargs)) or "No call expected.",
    )
    runtime, task = _configured_runtime()
    runtime.agents.register(
        Agent(
            id="cloud-agent",
            name="Cloud Agent",
            role="Researcher",
            provider="gemini",
            model="gemini-2.5-flash",
            capabilities=["research"],
        )
    )
    task = runtime.application_service.create_task(
        "Cloud work",
        "Must remain undispatched.",
        project_id=task.project_id,
        agent_id="cloud-agent",
    )

    with _client(runtime) as client:
        cloud = client.post(
            f"/api/tasks/{task.id}/dispatch",
            headers={"Authorization": "dispatch-owner"},
            json={"confirmed": True},
        )

    assert cloud.status_code == 409
    assert runtime.application_service.get_task(task.id).status == "pending"
    assert runtime.application_service.execution_queue().list() == ()
    assert calls == []

    runtime, task = _configured_runtime()
    runtime.providers.get("ollama").base_url = "https://remote.example"
    with _client(runtime) as client:
        remote = client.post(
            f"/api/tasks/{task.id}/dispatch",
            headers={"Authorization": "dispatch-owner"},
            json={"confirmed": True},
        )

    assert remote.status_code == 409
    assert runtime.application_service.get_task(task.id).status == "pending"
    assert runtime.application_service.execution_queue().list() == ()
    assert calls == []


def test_provider_failure_is_acknowledged_and_capacity_is_released(monkeypatch):
    def fail(_self, _model, _prompt):
        raise RuntimeError("Local model failed")

    monkeypatch.setattr(OllamaProvider, "generate", fail)
    runtime, task = _configured_runtime()

    with _client(runtime) as client:
        response = client.post(
            f"/api/tasks/{task.id}/dispatch",
            headers={"Authorization": "dispatch-owner"},
            json={"confirmed": True},
        )

    assert response.status_code == 200
    assert response.json()["state"] == "failed"
    assert response.json()["task"]["status"] == "failed"
    assert response.json()["task"]["error_recorded"] is True
    assert runtime.application_service.resource_manager().snapshot().global_capacity.allocated == 0


def test_interrupted_claim_requires_explicit_resolution_without_replay(monkeypatch):
    calls = []
    monkeypatch.setattr(
        OllamaProvider,
        "generate",
        lambda *args, **kwargs: calls.append((args, kwargs)) or "No replay.",
    )
    runtime, task = _configured_runtime()
    queue = runtime.application_service.execution_queue()
    entry = queue.enqueue("interrupted", task.id, now=NOW)
    claim = queue.claim_next(
        worker_id="dispatch-owner",
        claim_id="interrupted-claim",
        now=NOW,
        expected_entry_id=entry.id,
    )
    assert claim is not None and claim.state is QueueState.CLAIMED

    with _client(runtime) as client:
        blocked = client.post(
            f"/api/tasks/{task.id}/dispatch",
            headers={"Authorization": "dispatch-owner"},
            json={"confirmed": True},
        )
        resolved = client.post(
            f"/api/task-dispatch/{entry.id}/resolve",
            headers={"Authorization": "dispatch-owner"},
            json={
                "resolution": "Inspected; execution outcome is uncertain.",
                "confirmed": True,
            },
        )
        replay = client.post(
            f"/api/tasks/{task.id}/dispatch",
            headers={"Authorization": "dispatch-owner"},
            json={"confirmed": True},
        )

    assert blocked.status_code == 409
    assert resolved.status_code == 200
    assert resolved.json()["state"] == "abandoned"
    assert "Resolved by dispatch-owner" in resolved.json()["resolution"]
    assert replay.status_code == 409
    assert runtime.application_service.get_task(task.id).status == "pending"
    assert calls == []
