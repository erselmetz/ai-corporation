from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app.api.app import create_app
from app.api.security import AuthenticatedPrincipal
from app.application.services.managed_software import ManagedSoftwareService, PACKAGE_ID
from app.local import create_local_app


def output(text="", code=0):
    return SimpleNamespace(stdout=text, stderr="private output omitted", returncode=code)


class FakeWinget:
    def __init__(self, installed=False, *, fail_after_change=False):
        self.installed = installed
        self.fail_after_change = fail_after_change
        self.calls = []
        self.pin = None
        self.pin_output = None

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        assert kwargs["shell"] is False
        assert kwargs["capture_output"] is True
        command = args[1]
        if command == "list":
            if args[args.index("--scope") + 1] == "machine":
                return output("No installed package found matching input criteria.", -1978335212)
            if self.installed is False:
                return output("No installed package found matching input criteria.", -1978335212)
            return output(f"Microsoft Visual Studio Code (User) {PACKAGE_ID} {self.installed} winget\nInstalled Scope: User\nVersion: {self.installed}\nInstalled Location: C:\\Users\\test\\AppData\\Local\\Programs\\Microsoft VS Code\\\n")
        if command == "show" and "--versions" in args:
            return output("Found Microsoft Visual Studio Code [Microsoft.VisualStudioCode]\nVersion\n-------\n1.140.0\n1.141.0\n1.142.0\n")
        if command == "show":
            version = args[args.index("--version") + 1]
            return output(f"Found Microsoft Visual Studio Code [Microsoft.VisualStudioCode]\nVersion: {version}\nInstaller:\n  Installer Type: inno\n  Installer Url: https://example.invalid/VSCodeUserSetup-x64-{version}.exe\n  Installer SHA256: {'a' * 64}\n")
        if command == "install":
            self.installed = args[args.index("--version") + 1]
            return output("installed", 1 if self.fail_after_change else 0)
        if command == "upgrade":
            self.installed = args[args.index("--version") + 1]
            return output("updated")
        if command == "uninstall":
            self.installed = False
            return output("removed")
        if command == "pin" and args[2] == "list":
            if self.pin_output is not None:
                return output(self.pin_output)
            return output(f"Name Id Version\nMicrosoft Visual Studio Code {PACKAGE_ID} {self.pin}\n" if self.pin else "There are no pins configured.")
        if command == "pin" and args[2] == "add":
            self.pin = args[args.index("--version") + 1]
            return output("pinned")
        if command == "pin" and args[2] == "remove":
            self.pin = None
            return output("unpinned")
        raise AssertionError(args)


def service(monkeypatch, tmp_path, runner, clock=lambda: 100.0):
    from app.database import connection
    monkeypatch.setattr(connection, "DATABASE_PATH", tmp_path / "managed.db")
    return ManagedSoftwareService(runner=runner, clock=clock, executable="winget.exe")


def test_version_change_requires_exact_preview_and_owner_confirmation(monkeypatch, tmp_path):
    manager = FakeWinget(installed="1.141.0")
    svc = service(monkeypatch, tmp_path, manager)
    svc._save_managed("1.141.0")
    preview = svc.preview("version", "1.142.0")
    assert preview["from_version"] == "1.141.0"
    assert preview["to_version"] == "1.142.0"
    assert preview["scope"] == "user"
    assert preview["installer_sha256"] == "a" * 64
    with pytest.raises(PermissionError):
        svc.confirm(preview["confirmation_id"], "0" * 64)
    result = svc.confirm(preview["confirmation_id"], preview["preview_sha256"])
    assert result["status"] == "completed"
    assert result["recovery"] is None  # WinGet downgrade is not treated as verified rollback.
    assert manager.installed == "1.142.0"
    operation = next(args for args, _ in manager.calls if args[1] == "upgrade")
    assert "--scope" in operation and operation[operation.index("--scope") + 1] == "user"
    assert "--uninstall-previous" not in operation and "--purge" not in operation
    assert svc._managed()["version"] == "1.142.0"
    assert svc.status()["recent_operations"][0]["status"] == "completed"


def test_existing_external_install_is_never_adopted_or_changed(monkeypatch, tmp_path):
    manager = FakeWinget(installed="1.141.0")
    svc = service(monkeypatch, tmp_path, manager)
    assert svc.status()["status"] == "externally_managed"
    with pytest.raises(Exception, match="Only an app-owned"):
        svc.preview("remove")
    assert not any(args[1] in {"upgrade", "uninstall", "install"} for args, _ in manager.calls)


def test_downgrade_is_rejected_without_a_verified_package_recovery_path(monkeypatch, tmp_path):
    manager = FakeWinget(installed="1.141.0")
    svc = service(monkeypatch, tmp_path, manager)
    svc._save_managed("1.141.0")
    with pytest.raises(Exception, match="Only forward upgrades"):
        svc.preview("version", "1.140.0")
    assert not any(args[1] == "upgrade" for args, _ in manager.calls)


def test_partial_install_failure_is_reported_uncertain_without_retry(monkeypatch, tmp_path):
    manager = FakeWinget(fail_after_change=True)
    svc = service(monkeypatch, tmp_path, manager)
    preview = svc.preview("install", "1.142.0")
    result = svc.confirm(preview["confirmation_id"], preview["preview_sha256"])
    assert result["status"] == "uncertain"
    assert "No retry" not in result.get("message", "")  # state change is surfaced for owner review
    assert sum(args[1] == "install" for args, _ in manager.calls) == 1
    assert svc._managed()["state"] == "uncertain"


def test_uncertain_removal_can_only_be_recovered_by_confirmed_exact_reinstall(monkeypatch, tmp_path):
    manager = FakeWinget(installed=False)
    svc = service(monkeypatch, tmp_path, manager)
    svc._mark_uncertain("1.141.0")
    assert svc.status()["status"] == "ownership_uncertain"
    with pytest.raises(Exception, match="owner review"):
        svc.preview("install", "1.142.0")
    recovery = svc.preview("install", "1.141.0")
    assert recovery["recovery_from_uncertain"] is True
    assert svc.confirm(recovery["confirmation_id"], recovery["preview_sha256"])["status"] == "completed"
    assert svc._managed() == {"version": "1.141.0", "state": "managed"}


def test_remove_never_requests_user_data_cleanup_and_offers_verified_reinstall(monkeypatch, tmp_path):
    manager = FakeWinget(installed="1.141.0")
    svc = service(monkeypatch, tmp_path, manager)
    svc._save_managed("1.141.0")
    user_data = tmp_path / "user-data"
    user_data.mkdir()
    settings = user_data / "settings.json"
    settings.write_text('{"editor.fontSize": 14}')
    preview = svc.preview("remove")
    assert preview["preserved_data"]
    assert preview["removed_install_directory"] == "C:\\Users\\test\\AppData\\Local\\Programs\\Microsoft VS Code"
    result = svc.confirm(preview["confirmation_id"], preview["preview_sha256"])
    assert result["status"] == "completed"
    assert settings.read_text() == '{"editor.fontSize": 14}'
    removal = next(args for args, _ in manager.calls if args[1] == "uninstall")
    assert "--purge" not in removal and "--preserve" not in removal
    assert result["recovery"]["version"] == "1.141.0"
    assert result["recovery"]["requires_new_preview_and_owner_confirmation"] is True


def test_preview_expires_and_cannot_be_replayed(monkeypatch, tmp_path):
    manager = FakeWinget()
    clock = [100.0]
    svc = service(monkeypatch, tmp_path, manager, clock=lambda: clock[0])
    preview = svc.preview("install", "1.142.0")
    clock[0] += 301
    with pytest.raises(PermissionError):
        svc.confirm(preview["confirmation_id"], preview["preview_sha256"])
    assert not any(args[1] == "install" for args, _ in manager.calls)


def test_pin_and_unpin_are_verified_and_external_pins_are_preserved(monkeypatch, tmp_path):
    manager = FakeWinget(installed="1.141.0")
    svc = service(monkeypatch, tmp_path, manager)
    svc._save_managed("1.141.0")
    manager.pin = "1.140.0"
    with pytest.raises(Exception, match="verified pin"):
        svc.preview("unpin")
    manager.pin = None
    pin = svc.preview("pin", "1.141.0")
    assert svc.confirm(pin["confirmation_id"], pin["preview_sha256"])["status"] == "completed"
    assert svc.status()["pinned_version"] == "1.141.0"
    unpin = svc.preview("unpin")
    assert svc.confirm(unpin["confirmation_id"], unpin["preview_sha256"])["status"] == "completed"
    assert svc.status()["pinned_version"] is False


def test_unrecognized_pin_output_blocks_removal(monkeypatch, tmp_path):
    manager = FakeWinget(installed="1.141.0")
    manager.pin_output = "Unrecognized package pin response"
    svc = service(monkeypatch, tmp_path, manager)
    svc._save_managed("1.141.0")
    with pytest.raises(Exception, match="pin state could not be verified"):
        svc.preview("remove")


def test_local_api_gates_read_mutation_and_default_api(monkeypatch, tmp_path):
    manager = FakeWinget()
    svc = service(monkeypatch, tmp_path, manager)
    local = create_local_app(password="test-only-owner-passphrase", application_service=object())
    local.state.managed_software_service = svc
    with TestClient(local, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50100)) as client:
        assert client.get("/api/local/software").status_code == 401
        login = client.post("/api/local/login", json={"password": "test-only-owner-passphrase"},
                            headers={"Origin": "http://127.0.0.1:8000"})
        assert login.status_code == 200
        session = client.get("/api/local/session").json()
        headers = {"Origin": "http://127.0.0.1:8000", "X-Local-CSRF": session["csrf"]}
        assert client.get("/api/local/software").status_code == 200
        preview = client.post("/api/local/software/preview", json={"action": "install", "version": "1.142.0"}, headers=headers)
        assert preview.status_code == 200
        body = {"confirmation_id": preview.json()["confirmation_id"],
                "preview_sha256": preview.json()["preview_sha256"]}
        assert client.post("/api/local/software/confirm", json=body,
                           headers={"Origin": "http://127.0.0.1:8000"}).status_code == 403
        confirmed = client.post("/api/local/software/confirm", json=body, headers=headers)
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "completed"
    with TestClient(create_app(application_service=object())) as default:
        assert default.get("/api/local/software").status_code == 404


def test_software_read_permission_does_not_grant_mutation(monkeypatch, tmp_path):
    from app.api.managed_software import router

    class ReadOnlyOwner:
        def authenticate(self, _request):
            return AuthenticatedPrincipal("owner", frozenset({"software:read"}))

    svc = service(monkeypatch, tmp_path, FakeWinget())
    app = create_app(application_service=object(), authentication_backend=ReadOnlyOwner())
    app.include_router(router)
    app.state.managed_software_service = svc
    with TestClient(app) as client:
        assert client.get("/api/local/software").status_code == 200
        denied = client.post("/api/local/software/preview", json={"action": "install", "version": "1.142.0"})
        assert denied.status_code == 403
        assert not any(args[1] == "install" for args, _ in svc._runner.calls)
