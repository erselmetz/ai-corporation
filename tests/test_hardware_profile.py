from datetime import datetime, timezone

from app.application.services import hardware_profile as profile_module
from app.application.services.hardware_profile import (
    Observation,
    collect_hardware_profile,
    profile_to_dict,
)


def _observation(timestamp, *, state="observed", value=None, unit=None, source="test source", reason=None):
    return Observation(state, value, unit, source if state == "observed" else None, timestamp,
                       reason if state == "unknown" else None)


def test_profile_records_source_and_timestamp_for_each_local_observation(monkeypatch):
    timestamp = "2026-10-18T00:00:00+00:00"
    monkeypatch.setattr(profile_module, "_observe_cpu", lambda at: _observation(at, value={"name": "CPU"}))
    monkeypatch.setattr(profile_module, "_observe_gpu", lambda at: _observation(at, value=[]))
    monkeypatch.setattr(profile_module, "_observe_memory", lambda at: _observation(
        at, value={"total_bytes": 16 * 1024**3, "available_bytes": 10 * 1024**3}, unit="bytes"))
    monkeypatch.setattr(profile_module, "_observe_disk", lambda at: _observation(
        at, value={"free_bytes": 32 * 1024**3, "total_bytes": 100 * 1024**3, "destination": "default"}, unit="bytes"))

    profile = collect_hardware_profile(now=datetime(2026, 10, 18, tzinfo=timezone.utc))
    result = profile_to_dict(profile)

    assert result["observed_at"] == timestamp
    for key in ("cpu", "gpu", "memory", "disk"):
        assert result[key]["state"] == "observed"
        assert result[key]["source"] == "test source"
        assert result[key]["observed_at"] == timestamp
    assert result["privacy"] == "Read-only local observation; not stored or uploaded."
    assert result["recommendation"]["ollama_model_class"].startswith("small-to-medium")
    assert "No hardware GPU adapter" in result["recommendation"]["cpu_warning"]


def test_unknown_inventory_stays_unknown_and_never_claims_model_fit():
    timestamp = "2026-10-18T00:00:00+00:00"
    unknown = _observation(timestamp, state="unknown", reason="not supported")
    result = profile_to_dict(profile_module.HardwareProfile(
        timestamp, unknown, unknown, unknown, unknown,
        profile_module._recommend(unknown, unknown, unknown),
    ))

    assert result["cpu"]["value"] is None
    assert result["gpu"]["state"] == "unknown"
    assert result["recommendation"]["ollama_model_class"] == "UNKNOWN"
    assert "GPU status is unknown" in result["recommendation"]["cpu_warning"]
    assert "does not guarantee model fit" in result["recommendation"]["fit_claim"]


def test_recommendation_is_bounded_and_reports_low_disk_without_starting_download():
    timestamp = "2026-10-18T00:00:00+00:00"
    memory = _observation(timestamp, value={"total_bytes": 8 * 1024**3, "available_bytes": 3 * 1024**3})
    gpu = _observation(timestamp, value=[{"name": "GPU", "dedicated_memory_bytes": None}])
    disk = _observation(timestamp, value={"free_bytes": 2 * 1024**3, "total_bytes": 100 * 1024**3, "destination": "custom"})

    recommendation = profile_module._recommend(memory, gpu, disk)

    assert recommendation["ollama_model_class"] == "small (up to about 3B parameters, Q4)"
    assert "accelerator use and usable VRAM are not verified" in recommendation["cpu_warning"]
    assert "below 8 GiB" in recommendation["basis"]
    assert "does not guarantee model fit" in recommendation["fit_claim"]


def test_disk_observation_never_returns_configured_destination_path(monkeypatch, tmp_path):
    timestamp = "2026-10-18T00:00:00+00:00"
    destination = tmp_path / "private-model-store"
    destination.mkdir()
    monkeypatch.setenv("OLLAMA_MODELS", str(destination))

    result = profile_module._observe_disk(timestamp)

    assert result.state == "observed"
    assert result.value["destination"] == "custom"
    assert str(destination) not in repr(result)
