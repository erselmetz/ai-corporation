from datetime import datetime, timedelta, timezone
from app.inventory import build_software_inventory


NOW = datetime(2026, 10, 12, 8, 0, tzinfo=timezone.utc)


def test_inventory_reports_only_supported_sources_and_readable_workflow_dependencies(tmp_path):
    assignments = [type("Assignment", (), {"provider_id": "ollama-lab", "agent_id": "architect"})()]
    snapshot = build_software_inventory(
        checkout_root=tmp_path,
        assignments=assignments,
        provider_connections=[{
            "provider_id": "ollama-lab",
            "name": "Local model service",
            "provider_type": "ollama",
            "state": "available",
            "source": "ollama:/api/tags",
            "checked_at": NOW.isoformat(),
            "models": ["qwen3:4b"],
            "api_key": "must-never-be-returned",
        }],
        now=NOW,
    )
    by_id = {item["id"]: item for item in snapshot["items"]}
    assert by_id["application:erselmetz-ai"]["status"] == "running"
    assert by_id["runtime:python"]["management"] == "externally_managed"
    assert by_id["repository:current"]["status"] == "unknown"
    connection = by_id["ollama-lab"]
    assert connection["status"] == "available"
    assert connection["dependent_workflows"] == ["agent:architect"]
    assert "qwen3:4b" in connection["models"]
    assert "must-never-be-returned" not in repr(snapshot)
    assert all("api_key" not in item for item in snapshot["items"])
    assert snapshot["generated_at"] == NOW.isoformat()


def test_missing_connection_registry_is_explicit_and_not_claimed_available(tmp_path):
    snapshot = build_software_inventory(checkout_root=tmp_path, now=NOW)
    summary = next(item for item in snapshot["items"] if item["kind"] == "integration_summary")
    assert summary["status"] == "not_configured"
    assert summary["dependent_workflows"] == []


def test_stale_connection_keeps_stale_status_and_original_observation_time(tmp_path):
    stale_time = (NOW - timedelta(days=2)).isoformat()
    snapshot = build_software_inventory(
        checkout_root=tmp_path,
        provider_connections=[{
            "provider_id": "gemini-research",
            "name": "Research API",
            "provider_type": "gemini",
            "state": "stale",
            "checked_at": stale_time,
            "models": [],
        }],
        now=NOW,
    )
    record = next(item for item in snapshot["items"] if item["id"] == "gemini-research")
    assert record["status"] == "stale"
    assert record["observed_at"] == stale_time
    assert record["source"] == "configured provider connection"


def test_inventory_bounds_connections_models_and_assignments(tmp_path):
    connections = [
        {"provider_id": f"provider-{index}", "models": [f"model-{model}" for model in range(1000)],
         "state": "unknown"}
        for index in range(200)
    ]
    snapshot = build_software_inventory(checkout_root=tmp_path, provider_connections=connections, now=NOW)
    assert len(snapshot["items"]) <= 128
    for record in snapshot["items"]:
        assert len(record.get("models", [])) <= 64


def test_inventory_requires_timezone_aware_clock(tmp_path):
    try:
        build_software_inventory(checkout_root=tmp_path, now=datetime(2026, 10, 12))
    except ValueError as error:
        assert "timezone-aware" in str(error)
    else:
        raise AssertionError("naive timestamp must not be accepted")
