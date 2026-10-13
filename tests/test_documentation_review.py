from fastapi import Request
from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal, create_app
from app.application.services.documentation_review import (
    DocumentationReviewConflict,
    DocumentationReviewService,
)
from app.orchestrator import Orchestrator
from app.application.services.corporation import CorporationApplicationService
from unittest.mock import MagicMock
import pytest
from app.application.services.documentation_review import DocumentationReviewNotFound


class ReviewAuthentication:
    def authenticate(self, request: Request):
        header = request.headers.get("Authorization")
        permissions = {
            "reviewer": frozenset({"documentation:review", "documentation:read"}),
            "reader": frozenset({"documentation:read"}),
        }.get(header)
        return AuthenticatedPrincipal("owner-1", permissions) if permissions else None


def client(tmp_path):
    service = CorporationApplicationService(MagicMock(spec=Orchestrator))
    drafts = DocumentationReviewService(tmp_path / "review.sqlite")
    app = create_app(service, ReviewAuthentication(), documentation_review_service=drafts)
    return TestClient(app), drafts


def test_draft_versions_approval_conflicts_and_recovery_are_exact_and_append_only(tmp_path):
    api, service = client(tmp_path)
    with api:
        created = api.post("/api/documentation/review", headers={"Authorization": "reviewer"}, json={
            "title": "Architecture proposal", "content": "Draft one\n", "provenance": "owner-authored proposal",
        })
        assert created.status_code == 201
        first = created.json()
        assert first["version"] == 1
        assert first["approved_at"] is None
        assert first["digest"]

        approved = api.post(f"/api/documentation/review/{first['document_id']}/approve",
                            headers={"Authorization": "reviewer"},
                            json={"version": 1, "digest": first["digest"]})
        assert approved.status_code == 200
        assert approved.json()["reviewer"] == "owner-1"
        assert approved.json()["approved_at"]

        updated = api.put(f"/api/documentation/review/{first['document_id']}",
                          headers={"Authorization": "reviewer"}, json={
            "expected_version": 1, "title": "Architecture proposal",
            "content": "Draft two\n", "provenance": "revised by owner",
        })
        assert updated.status_code == 200
        second = updated.json()
        assert second["version"] == 2
        assert "Draft one" in second["diff"] and "Draft two" in second["diff"]
        assert second["approved_at"] is None
        assert api.post(f"/api/documentation/review/{first['document_id']}/approve",
                        headers={"Authorization": "reviewer"},
                        json={"version": 1, "digest": first["digest"]}).status_code == 409
        assert api.put(f"/api/documentation/review/{first['document_id']}",
                       headers={"Authorization": "reviewer"}, json={
            "expected_version": 1, "title": "stale", "content": "stale", "provenance": "stale",
        }).status_code == 409

        recovered = api.post(f"/api/documentation/review/{first['document_id']}/recover",
                             headers={"Authorization": "reviewer"},
                             json={"source_version": 1, "expected_version": 2})
        assert recovered.status_code == 200
        third = recovered.json()
        assert third["version"] == 3
        assert third["content"] == "Draft one\n"
        assert third["recovered_from_version"] == 1
        assert third["approved_at"] is None

        history = api.get(f"/api/documentation/review/{first['document_id']}/versions",
                          headers={"Authorization": "reviewer"}).json()["items"]
        assert [item["version"] for item in history] == [3, 2, 1]
        assert history[-1]["reviewer"] == "owner-1"
        assert service.get(first["document_id"], actor="owner-1").version == 3


def test_review_permission_is_separate_and_default_auth_stays_fail_closed(tmp_path):
    api, _ = client(tmp_path)
    with api:
        payload = {"title": "Proposal", "content": "Text", "provenance": "human"}
        assert api.post("/api/documentation/review", json=payload).status_code == 401
        assert api.post("/api/documentation/review", headers={"Authorization": "reader"},
                        json=payload).status_code == 403


def test_approval_requires_exact_digest_and_private_owner_scope(tmp_path):
    api, service = client(tmp_path)
    draft = service.create(title="Proposal", content="Text", provenance="owner", actor="owner-1")
    with api:
        assert api.post(f"/api/documentation/review/{draft.document_id}/approve",
                        headers={"Authorization": "reviewer"},
                        json={"version": 1, "digest": "0" * 64}).status_code == 409
    with pytest.raises(DocumentationReviewNotFound):
        service.get(draft.document_id, actor="someone-else")


def test_storage_survives_service_restart_and_history_limits_fail_closed(tmp_path):
    db_path = tmp_path / "durable.sqlite"
    service = DocumentationReviewService(db_path)
    first = service.create(title="Proposal", content="Text", provenance="owner", actor="owner-1")
    restarted = DocumentationReviewService(db_path)
    assert restarted.get(first.document_id, actor="owner-1").digest == first.digest

    restarted.MAX_DOCUMENTS = 1
    with pytest.raises(DocumentationReviewConflict, match="draft limit"):
        restarted.create(title="Second", content="Text", provenance="owner", actor="owner-1")

    restarted.MAX_VERSIONS = 1
    with pytest.raises(DocumentationReviewConflict, match="history is full"):
        restarted.update(first.document_id, expected_version=1, title="Proposal",
                         content="Changed", provenance="owner", actor="owner-1")


def test_published_documentation_api_remains_read_only(tmp_path):
    api, _ = client(tmp_path)
    with api:
        assert api.post("/api/documentation", headers={"Authorization": "reviewer"}, json={}).status_code == 405
