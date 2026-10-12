import json
from datetime import datetime, timezone
from difflib import unified_diff
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal, create_app
from app.application import DiagnosticEvidence
from app.application.services.code_review import (
    CodeReviewFinding,
    CodeReviewReport,
    ReviewArea,
    ReviewSeverity,
    _evidence_digest,
)
from app.application.services.maintenance_sandbox import (
    MaintenanceSandboxReport,
    MaintenanceSandboxStatus,
)
from app.application.services.maintenance_proposals import MaintenanceProposal
from app.application.services.patch_development import PatchDevelopmentService
from app.integrations import SandboxImagePolicy


IMAGE = "registry.example/maintenance@sha256:" + "a" * 64


def diff_for(path, original, updated):
    return "".join(
        unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


class ExperimentAuthentication:
    def authenticate(self, request):
        owner = request.headers.get("Authorization")
        if owner not in {"owner", "other"}:
            return None
        return AuthenticatedPrincipal(owner, frozenset({"maintenance:experiment"}))


class FakeMaintenanceApplication:
    def __init__(self, status=MaintenanceSandboxStatus.PASSED):
        self.workspaces = PatchDevelopmentService()
        self.proposal = MaintenanceProposal(
            proposal_id="proposal-122",
            diagnostic=SimpleNamespace(agent_id="author-agent"),
            title="Bounded adaptation",
            proposed_change="Change only module.py.",
            scope="module.py and explicitly selected tests only.",
            risk="The adaptation is unverified until isolated tests and review.",
            created_at=datetime.now(timezone.utc),
        )
        self.test_status = status
        self.test_calls = []
        self.review_calls = []

    def develop_patch(self, proposal_id, source_root, selected_files, unified_diff):
        assert proposal_id == self.proposal.proposal_id
        return self.workspaces.develop(
            self.proposal, source_root, selected_files, unified_diff
        )

    def get_patch_workspace(self, workspace_id):
        return self.workspaces.get(workspace_id)

    def dispose_patch_workspace(self, workspace_id):
        self.workspaces.dispose(workspace_id)

    def run_sandboxed_tests(
        self, workspace_id, selected_tests, image_policy, *, timeout_seconds
    ):
        workspace = self.workspaces.get(workspace_id)
        self.test_calls.append(
            (workspace_id, selected_tests, image_policy, timeout_seconds)
        )
        status = (
            self.test_status
            if image_policy.default_image is not None
            else MaintenanceSandboxStatus.BLOCKED
        )
        now = datetime.now(timezone.utc)
        return MaintenanceSandboxReport(
            run_id=f"test-run-{len(self.test_calls)}",
            proposal_id=workspace.proposal_id,
            workspace_id=workspace_id,
            selected_tests=selected_tests,
            status=status,
            backend_id="docker" if image_policy.default_image else "none",
            return_code=(
                0
                if status is MaintenanceSandboxStatus.PASSED
                else 124
                if status is MaintenanceSandboxStatus.TIMED_OUT
                else None
            ),
            output="deterministic test evidence",
            output_truncated=False,
            started_at=now,
            finished_at=now,
            notes=(),
        )

    def get_maintenance_proposal(self, proposal_id):
        assert proposal_id == self.proposal.proposal_id
        return self.proposal

    def get_agent(self, agent_id):
        return SimpleNamespace(
            id=agent_id,
            provider="online" if agent_id == "online-reviewer" else "ollama",
        )

    def provider_requires_explicit_cloud_consent(self, provider_id):
        return provider_id == "online"

    def review_code(self, agent_id, evidence):
        self.review_calls.append((agent_id, evidence))
        return CodeReviewReport(
            agent_id=agent_id,
            findings=(
                CodeReviewFinding(
                    summary="Review found no evidenced defect.",
                    severity=ReviewSeverity.LOW,
                    area=ReviewArea.CORRECTNESS,
                    evidence_refs=("exact-patch",),
                ),
            ),
            unknowns=("Review covers only the submitted patch and scope.",),
            generated_at=datetime.now(timezone.utc),
            evidence_sha256=_evidence_digest(evidence),
        )


def create_client(application_service=None, image_policy=None):
    service = application_service or FakeMaintenanceApplication()
    app = create_app(
        application_service=service,
        authentication_backend=ExperimentAuthentication(),
        maintenance_sandbox_image_policy=image_policy,
    )
    return TestClient(app), service


def create_payload(*, source="value = 1\n", patch=None):
    return {
        "proposal_id": "proposal-122",
        "files": [
            {"path": "module.py", "content": source},
            {
                "path": "tests/test_module.py",
                "content": "from module import VALUE\nassert VALUE == 2\n",
            },
        ],
        "unified_diff": patch
        or diff_for("module.py", "value = 1\n", "VALUE = 2\n"),
    }


def test_experiment_binds_exact_files_hashes_and_diff_without_touching_source():
    client, service = create_client()
    payload = create_payload(source="value = 1\n")
    with client:
        created = client.post(
            "/api/maintenance/experiments",
            headers={"Authorization": "owner"},
            json=payload,
        )
        assert created.status_code == 201, created.text
        result = created.json()
        assert result["allowed_files"] == ["module.py", "tests/test_module.py"]
        assert result["changed_files"] == ["module.py"]
        assert result["source_sha256"]
        assert result["patch_sha256"]
        assert result["unified_diff"] == payload["unified_diff"]
        assert result["test_report"] is None
        assert result["review_report"] is None
        assert result["execution_policy"]["network_access"] is False
        assert result["execution_policy"]["host_mounts"] is False
        assert result["execution_policy"]["automatic_image_pull"] is False
        assert result["execution_policy"]["maximum_test_timeout_seconds"] == 60
        assert result["execution_policy"]["resource_limits"] == {
            "memory_mb": 512,
            "cpu_seconds": 60,
            "processes": 16,
            "disk_mb": 256,
        }
        assert len(result["recovery_limits"]) == 4
        assert not (service.workspaces.get(result["workspace_id"]).source_root / "missing").exists()

        workspace = service.workspaces.get(result["workspace_id"])
        assert (workspace.path / "module.py").read_text(encoding="utf-8") == "VALUE = 2\n"
        assert (workspace.source_root / "module.py").read_text(encoding="utf-8") == "value = 1\n"


def test_authentication_and_workspace_ownership_are_enforced():
    client, _ = create_client()
    with client:
        denied = client.post("/api/maintenance/experiments", json=create_payload())
        assert denied.status_code == 401
        created = client.post(
            "/api/maintenance/experiments",
            headers={"Authorization": "owner"},
            json=create_payload(),
        )
        workspace_id = created.json()["workspace_id"]
        denied_read = client.get(
            f"/api/maintenance/experiments/{workspace_id}",
            headers={"Authorization": "other"},
        )
        assert denied_read.status_code == 404


@pytest.mark.parametrize(
    ("files", "patch"),
    (
        (
            [{"path": "../outside.py", "content": "value = 1\n"}],
            "--- a/../outside.py\n+++ b/../outside.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n",
        ),
        (
            [{"path": "module.py", "content": "value = 1\n"}],
            "--- a/outside.py\n+++ b/outside.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n",
        ),
    ),
)
def test_denied_source_scope_never_writes_or_creates_a_workspace(files, patch):
    client, service = create_client()
    with client:
        response = client.post(
            "/api/maintenance/experiments",
            headers={"Authorization": "owner"},
            json={
                "proposal_id": "proposal-122",
                "files": files,
                "unified_diff": patch,
            },
        )
    assert response.status_code == 422
    assert service.workspaces._workspaces == {}


@pytest.mark.parametrize(
    "files",
    (
        [
            {"path": "module.py", "content": "value = 1\n"},
            {"path": "MODULE.PY", "content": "value = 9\n"},
        ],
        [
            {"path": "src", "content": "value = 1\n"},
            {"path": "SRC/module.py", "content": "value = 9\n"},
        ],
    ),
)
def test_source_paths_that_alias_or_conflict_are_rejected(files):
    client, service = create_client()
    with client:
        response = client.post(
            "/api/maintenance/experiments",
            headers={"Authorization": "owner"},
            json={
                "proposal_id": "proposal-122",
                "files": files,
                "unified_diff": diff_for("module.py", "value = 1\n", "value = 2\n"),
            },
        )
    assert response.status_code == 422
    assert service.workspaces._workspaces == {}


def test_malicious_source_is_inert_and_default_missing_docker_is_reported_blocked():
    client, service = create_client()
    payload = create_payload(
        source=(
            "value = 1\n"
            "import pathlib\n"
            "pathlib.Path('host-marker').write_text('executed')\n"
        )
    )
    with client:
        created = client.post(
            "/api/maintenance/experiments",
            headers={"Authorization": "owner"},
            json=payload,
        )
        assert created.status_code == 201, created.text
        workspace_id = created.json()["workspace_id"]
        blocked = client.post(
            f"/api/maintenance/experiments/{workspace_id}/tests",
            headers={"Authorization": "owner"},
            json={"selected_tests": ["tests/test_module.py"], "timeout_seconds": 12},
        )
        assert blocked.status_code == 200
        assert blocked.json()["test_report"]["status"] == "blocked"
        # The service fake records the request but does not execute uploaded test code.
        assert not (service.workspaces.get(workspace_id).path / "host-marker").exists()
        assert service.test_calls[0][2].allowed_images == ()
        assert service.test_calls[0][3] == 12


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (MaintenanceSandboxStatus.FAILED, "failed"),
        (MaintenanceSandboxStatus.TIMED_OUT, "timed_out"),
    ),
)
def test_failed_or_interrupted_tests_are_recorded_and_block_independent_review(
    status, expected
):
    policy = SandboxImagePolicy(allowed_images=(IMAGE,), default_image=IMAGE)
    client, service = create_client(FakeMaintenanceApplication(status), policy)
    with client:
        created = client.post(
            "/api/maintenance/experiments",
            headers={"Authorization": "owner"},
            json=create_payload(),
        )
        workspace_id = created.json()["workspace_id"]
        tests = client.post(
            f"/api/maintenance/experiments/{workspace_id}/tests",
            headers={"Authorization": "owner"},
            json={"selected_tests": ["tests/test_module.py"]},
        )
        review = client.post(
            f"/api/maintenance/experiments/{workspace_id}/review",
            headers={"Authorization": "owner"},
            json={"reviewer_agent_id": "independent-reviewer"},
        )
    assert tests.json()["test_report"]["status"] == expected
    assert review.status_code == 403
    assert service.review_calls == []


def test_independent_review_requires_passed_tests_and_explicit_cloud_consent():
    policy = SandboxImagePolicy(allowed_images=(IMAGE,), default_image=IMAGE)
    client, service = create_client(image_policy=policy)
    with client:
        created = client.post(
            "/api/maintenance/experiments",
            headers={"Authorization": "owner"},
            json=create_payload(),
        )
        workspace_id = created.json()["workspace_id"]
        tests = client.post(
            f"/api/maintenance/experiments/{workspace_id}/tests",
            headers={"Authorization": "owner"},
            json={"selected_tests": ["tests/test_module.py"]},
        )
        same_agent = client.post(
            f"/api/maintenance/experiments/{workspace_id}/review",
            headers={"Authorization": "owner"},
            json={"reviewer_agent_id": "author-agent"},
        )
        no_consent = client.post(
            f"/api/maintenance/experiments/{workspace_id}/review",
            headers={"Authorization": "owner"},
            json={"reviewer_agent_id": "online-reviewer"},
        )
        reviewed = client.post(
            f"/api/maintenance/experiments/{workspace_id}/review",
            headers={"Authorization": "owner"},
            json={
                "reviewer_agent_id": "online-reviewer",
                "cloud_consent": True,
            },
        )
    assert tests.json()["test_report"]["status"] == "passed"
    assert same_agent.status_code == 403
    assert no_consent.status_code == 403
    assert reviewed.status_code == 200
    report = reviewed.json()["review_report"]
    assert report["agent_id"] == "online-reviewer"
    assert report["findings"][0]["summary"] == "Review found no evidenced defect."
    assert service.review_calls[0][1][0].content == create_payload()["unified_diff"]
    assert service.review_calls[0][1][1].reference_id == "experiment-scope"


def test_test_selection_must_stay_inside_workspace_and_disposal_removes_artifacts():
    client, service = create_client()
    with client:
        created = client.post(
            "/api/maintenance/experiments",
            headers={"Authorization": "owner"},
            json=create_payload(),
        )
        workspace_id = created.json()["workspace_id"]
        workspace = service.workspaces.get(workspace_id)
        source_root = workspace.source_root
        denied_test = client.post(
            f"/api/maintenance/experiments/{workspace_id}/tests",
            headers={"Authorization": "owner"},
            json={"selected_tests": ["../outside.py"]},
        )
        deleted = client.delete(
            f"/api/maintenance/experiments/{workspace_id}",
            headers={"Authorization": "owner"},
        )
        missing = client.get(
            f"/api/maintenance/experiments/{workspace_id}",
            headers={"Authorization": "owner"},
        )
    assert denied_test.status_code == 422
    assert deleted.status_code == 204
    assert missing.status_code == 404
    assert not workspace.path.exists()
    assert not source_root.exists()


def test_workspace_request_rejects_oversized_utf8_source_before_allocation():
    client, service = create_client()
    too_large = "é" * (PatchDevelopmentService.MAX_FILE_BYTES // 2 + 1)
    with client:
        response = client.post(
            "/api/maintenance/experiments",
            headers={"Authorization": "owner"},
            content=json.dumps(
                {
                    "proposal_id": "proposal-122",
                    "files": [{"path": "module.py", "content": too_large}],
                    "unified_diff": "",
                },
                ensure_ascii=False,
            ).encode("utf-8"),
        )
    assert response.status_code == 422
    assert service.workspaces._workspaces == {}
