from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.application.services.readiness_evidence import readiness_snapshot
from app.local import create_local_app

NOW = datetime(2026, 10, 14, tzinfo=timezone.utc)
PASSWORD = "readiness-owner-password"
ORIGIN = "http://127.0.0.1:8000"


@dataclass(frozen=True)
class Assignment:
    agent_id: str
    provider_id: str
    model_id: str


@dataclass(frozen=True)
class QueueEntry:
    id: str
    task_id: str
    state: object
    updated_at: datetime


class QueueState:
    value = "claimed"


class FakeQueue:
    def list_active(self, *, limit):
        assert limit == 100
        return (
            QueueEntry("prior-claim", "task-prior", QueueState(), NOW - timedelta(seconds=5)),
            QueueEntry("current-claim", "task-current", QueueState(), NOW + timedelta(seconds=5)),
        )


class FakeApplication:
    def list_models(self):
        return [Assignment(f"agent-{index}", "ollama", f"model-{index}") for index in range(102)]

    def execution_queue(self):
        return FakeQueue()


def test_snapshot_measures_only_supported_evidence_and_keeps_uncertainty_explicit():
    memory = Mock(return_value={"state": "measured", "bytes": 1234, "source": "test fixture"})
    snapshot = readiness_snapshot(
        application_service=FakeApplication(), app_started_at=NOW,
        startup_setup_ms=17.12345, observed_at=NOW, memory_reader=memory,
    )

    assert snapshot["observed_at"] == NOW.isoformat()
    assert snapshot["retention"] == "response snapshot only; not persisted"
    assert snapshot["conditions"]["workloads"]["model"] == "recorded assignments only; no inference request"
    assert snapshot["measurements"]["startup_setup"]["milliseconds"] == 17.123
    assert snapshot["measurements"]["process_memory"]["bytes"] == 1234
    assert snapshot["measurements"]["rendering"]["state"] == "unknown"
    assert snapshot["measurements"]["model_workload"]["state"] == "unknown"
    assert snapshot["measurements"]["model_workload"]["provider_calls"] == 0
    assert snapshot["measurements"]["hardware_fit"]["state"] == "unknown"
    assert snapshot["conditions"]["model_assignment_limit"] == 100
    assert snapshot["conditions"]["omitted_model_assignment_count"] == 2
    assert snapshot["recovery"]["automatic_replay"] is False
    assert snapshot["recovery"]["preexisting_claims"] == [
        {"entry_id": "prior-claim", "task_id": "task-prior", "state": "outcome_unknown",
         "claimed_at": (NOW - timedelta(seconds=5)).isoformat(), "resolution_required": True}
    ]
    memory.assert_called_once_with()


def test_snapshot_reports_unknown_when_measurement_sources_fail():
    class UnavailableApplication:
        def list_models(self):
            raise RuntimeError("private internal failure")

        def execution_queue(self):
            raise RuntimeError("private internal failure")

    snapshot = readiness_snapshot(
        application_service=UnavailableApplication(), app_started_at=NOW,
        startup_setup_ms=0, observed_at=NOW,
        memory_reader=Mock(side_effect=OSError("private path")),
    )

    assert snapshot["conditions"]["model_assignments_state"] == "unknown"
    assert snapshot["recovery"]["state"] == "unknown"
    assert snapshot["measurements"]["process_memory"]["state"] == "unknown"
    assert "private" not in repr(snapshot)


def test_readiness_api_is_local_owner_only_and_never_runs_a_model():
    local = create_local_app(password=PASSWORD)
    with patch("app.providers.ollama.OllamaProvider.generate",
               side_effect=AssertionError("readiness must not run a model")) as generate:
        with TestClient(local, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
            assert client.get("/api/local/readiness").status_code == 401
            assert client.get("/ui/readiness").status_code == 404
            assert client.get("/ui/static/readiness.mjs").status_code == 404
            client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})
            result = client.get("/api/local/readiness")
            assert result.status_code == 200
            body = result.json()
            assert body["measurements"]["startup_setup"]["state"] == "measured"
            assert body["measurements"]["process_memory"]["state"] in {"measured", "unknown"}
            assert body["measurements"]["model_workload"]["state"] == "unknown"
            assert body["measurements"]["model_workload"]["provider_calls"] == 0
            assert body["recovery"]["automatic_replay"] is False
        generate.assert_not_called()

    with TestClient(create_app(), base_url=ORIGIN) as default:
        assert default.get("/api/local/readiness").status_code == 404
