from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import pytest

from app.integrations.capability_packs import (
    PACKS, OptionalMediaPacks, PackDefinition, WheelSpec,
)
from app.local import create_local_app


def test_pack_preview_is_exact_read_only_and_does_not_download(tmp_path):
    calls = []
    packs = OptionalMediaPacks(tmp_path, downloader=lambda spec: calls.append(spec))
    previews = packs.preview()["items"]
    assert [item["pack_id"] for item in previews] == ["eyes", "ears", "voice", "desktop-automation"]
    assert all(item["state"] == "not-installed" and item["source"].startswith("Official PyPI") for item in previews)
    assert all(item["manifest_digest"] and item["files"] and item["download_bytes"] > 0 for item in previews)
    assert not calls
    assert packs.preview("ears")["version"]


def test_install_requires_current_owner_confirmation_and_hash_checked_wheels(tmp_path, monkeypatch):
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("demo/__init__.py", "VALUE = 'isolated'\n")
    data = payload.getvalue()
    spec = WheelSpec("demo-1.0-py3-none-any.whl", "https://files.pythonhosted.org/demo.whl",
                     len(data), sha256(data).hexdigest())
    definition = PackDefinition("demo", "Demo", (spec,), ("demo",))
    monkeypatch.setitem(PACKS, "demo", definition)
    calls = []
    packs = OptionalMediaPacks(tmp_path, downloader=lambda wheel: calls.append(wheel) or data,
                               runtime_supported=lambda: True,
                               self_tester=lambda _pack: {"state": "working", "detail": "isolated import passed"})
    preview = packs.preview("demo")
    with pytest.raises(ValueError, match="Review"):
        packs.install("demo", confirmed=False, manifest_digest=preview["manifest_digest"])
    with pytest.raises(ValueError, match="Review"):
        packs.install("demo", confirmed=True, manifest_digest="0" * 64)
    assert not calls
    result = packs.install("demo", confirmed=True, manifest_digest=preview["manifest_digest"])
    assert result == {"pack_id": "demo", "state": "installed", "already_installed": False}
    assert packs.preview("demo")["state"] == "installed"
    assert (tmp_path / "capability-packs" / "demo" / "site-packages" / "demo" / "__init__.py").is_file()
    assert packs.self_test("demo")["state"] == "working"
    assert packs.preview("demo")["state"] == "working"
    import importlib
    import sys
    restarted = OptionalMediaPacks(tmp_path, runtime_supported=lambda: True)
    try:
        assert restarted.preview("demo")["state"] == "installed"
        assert importlib.import_module("demo").VALUE == "isolated"
    finally:
        sys.path.remove(str((tmp_path / "capability-packs" / "demo" / "site-packages").resolve()))
        sys.modules.pop("demo", None)


def test_bad_wheel_is_removed_without_leaving_a_partial_pack(tmp_path, monkeypatch):
    spec = WheelSpec("demo-1.0.whl", "https://files.pythonhosted.org/demo.whl", 3, "0" * 64)
    monkeypatch.setitem(PACKS, "demo", PackDefinition("demo", "Demo", (spec,), ()))
    packs = OptionalMediaPacks(tmp_path, downloader=lambda _spec: b"bad", runtime_supported=lambda: True)
    preview = packs.preview("demo")
    with pytest.raises(RuntimeError, match="SHA-256"):
        packs.install("demo", confirmed=True, manifest_digest=preview["manifest_digest"])
    assert not (tmp_path / "capability-packs" / "demo").exists()


def test_media_pack_api_is_owner_protected_and_install_needs_csrf(tmp_path):
    app = create_local_app(password="capability-pack-test-password", application_service=MagicMock())
    app.state.media_capability_packs = OptionalMediaPacks(tmp_path, runtime_supported=lambda: False)
    origin = "http://127.0.0.1:8000"
    with TestClient(app, base_url=origin, client=("127.0.0.1", 50191)) as client:
        assert client.get("/api/capability-packs").status_code == 401
        assert client.post("/api/local/login", json={"password": "capability-pack-test-password"},
                           headers={"Origin": origin}).status_code == 200
        preview = client.get("/api/capability-packs").json()["items"][0]
        assert client.post("/api/capability-packs/eyes/install", json={
            "confirmed": True, "manifest_digest": preview["manifest_digest"]},
            headers={"Origin": origin}).status_code == 403
        auth = client.get("/api/local/session").json()
        response = client.post("/api/capability-packs/missing/self-test", json={}, headers={
            "Origin": origin, "X-Local-CSRF": auth["csrf"]})
        assert response.status_code == 404
        response = client.post("/api/capability-packs/eyes/install", json={
            "confirmed": True, "manifest_digest": preview["manifest_digest"]}, headers={
                "Origin": origin, "X-Local-CSRF": auth["csrf"]})
        assert response.status_code == 503
        assert "CPython 3.14" in response.json()["detail"]


def test_local_speech_model_preview_is_protected_and_pull_requires_explicit_digest_confirmation(tmp_path):
    from app.integrations.local_speech_model import LocalSpeechModelCatalog
    origin = "http://127.0.0.1:8000"
    catalog = LocalSpeechModelCatalog(tmp_path / "speech-models", downloader=lambda _item: (_ for _ in ()).throw(AssertionError("download must not occur")))
    app = create_local_app(password="speech-model-test-password", application_service=MagicMock(), speech_model_catalog=catalog)
    with TestClient(app, base_url=origin, client=("127.0.0.1", 50193)) as client:
        assert client.get("/api/local/voice/local-model-preview").status_code == 401
        client.post("/api/local/login", json={"password": "speech-model-test-password"}, headers={"Origin": origin})
        session = client.get("/api/local/session").json()
        headers = {"Origin": origin, "X-Local-CSRF": session["csrf"]}
        preview = client.get("/api/local/voice/local-model-preview").json()
        assert preview["state"] == "not-installed"
        assert preview["download_bytes"] == sum(item["size"] for item in preview["files"])
        assert client.post("/api/local/voice/local-model-install", json={
            "confirmed": True, "manifest_digest": "0" * 64}, headers=headers).status_code == 409


def test_settings_exposes_optional_pack_status_and_actions_with_existing_safety_controls():
    origin = "http://127.0.0.1:8000"
    app = create_local_app(password="settings-pack-test-password", application_service=MagicMock())
    with TestClient(app, base_url=origin, client=("127.0.0.1", 50192)) as client:
        client.post("/api/local/login", json={"password": "settings-pack-test-password"}, headers={"Origin": origin})
        page = client.get("/ui/settings/capabilities").text
    assert 'id="media-capability-packs"' in page
    assert 'src="/ui/static/capability-packs.mjs"' in page
    assert 'id="emergency-stop"' in page
    assert "No speech model or Tesseract engine is included or downloaded" in page


def test_optional_voice_output_test_is_owner_gated_and_emergency_stop_reaches_backend_output(
        tmp_path, monkeypatch):
    from unittest.mock import Mock
    from app.integrations import capability_packs

    monkeypatch.setattr(capability_packs, "application_data_root", lambda: tmp_path)
    origin = "http://127.0.0.1:8000"
    app = create_local_app(password="voice-output-gate-password", application_service=MagicMock())
    output = Mock()
    output.snapshot.return_value = {"state": "speaking", "active": True, "detail": "Test only"}
    output.stop.return_value = {"state": "stopping", "active": True}
    app.state.local_speech_output = output
    with TestClient(app, base_url=origin, client=("127.0.0.1", 50194)) as client:
        assert client.post("/api/local/voice/test-output").status_code == 403
        client.post("/api/local/login", json={"password": "voice-output-gate-password"}, headers={"Origin": origin})
        auth = client.get("/api/local/session").json()
        headers = {"Origin": origin, "X-Local-CSRF": auth["csrf"]}
        assert client.post("/api/local/voice/test-output", json={}, headers=headers).status_code == 409
        assert client.post("/api/local/emergency-stop/stop", json={}, headers=headers).status_code == 200
        output.stop.assert_called_once()
