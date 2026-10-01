from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal, create_app
from app.application import (
    CorporationApplicationService,
    DocumentationNotFound,
    DocumentationSourceUnavailable,
)
from app.documentation import MarkdownDocumentationSource
from app.orchestrator import Orchestrator


class DocumentationTestAuthenticationBackend:
    def authenticate(self, request: Request) -> AuthenticatedPrincipal | None:
        permissions = {
            "documentation-reader": frozenset({"documentation:read"}),
            "project-reader": frozenset({"project:read"}),
        }.get(request.headers.get("Authorization", ""))
        if permissions is None:
            return None
        return AuthenticatedPrincipal(identity="test-user", permissions=permissions)


@pytest.fixture
def documentation_api(tmp_path):
    root = tmp_path / "corporation_docs"
    root.mkdir()
    (root / "overview.md").write_text(
        "# Corporation\n\nInternal overview.\n",
        encoding="utf-8",
    )
    (root / "z-notes.md").write_text("# Notes\n\nOperational notes.\n", encoding="utf-8")
    (root / "not-markdown.txt").write_text("Do not expose", encoding="utf-8")
    (root / ".hidden.md").write_text("# Hidden\n", encoding="utf-8")
    nested = root / "nested"
    nested.mkdir()
    (nested / "nested.md").write_text("# Nested\n", encoding="utf-8")

    source = MagicMock(wraps=MarkdownDocumentationSource(root))
    service = CorporationApplicationService(MagicMock(spec=Orchestrator))
    application = create_app(
        service,
        DocumentationTestAuthenticationBackend(),
        documentation_source=source,
    )
    return application, source, root


def documentation_headers():
    return {"Authorization": "documentation-reader"}


def test_documentation_list_is_authz_protected_and_exposes_markdown_summaries(
    documentation_api,
):
    application, source, _ = documentation_api

    with TestClient(application) as client:
        unauthenticated = client.get("/api/documentation")
        forbidden = client.get(
            "/api/documentation",
            headers={"Authorization": "project-reader"},
        )
        response = client.get(
            "/api/documentation",
            headers=documentation_headers(),
        )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"id": "overview", "title": "Corporation"},
            {"id": "z-notes", "title": "Notes"},
        ]
    }
    assert set(response.json()["items"][0]) == {"id", "title"}
    assert "content" not in response.json()["items"][0]
    source.list_documents.assert_called_once_with()


def test_documentation_detail_returns_markdown_through_application_service(
    documentation_api,
):
    application, source, _ = documentation_api

    with TestClient(application) as client:
        unauthenticated = client.get("/api/documentation/overview")
        forbidden = client.get(
            "/api/documentation/overview",
            headers={"Authorization": "project-reader"},
        )
        response = client.get(
            "/api/documentation/overview",
            headers=documentation_headers(),
        )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert response.status_code == 200
    assert response.json() == {
        "id": "overview",
        "title": "Corporation",
        "content": "# Corporation\n\nInternal overview.\n",
    }
    source.get_document.assert_called_once_with("overview")
    assert "filesystem" not in response.text.lower()


def test_missing_invalid_traversal_and_absolute_document_ids_are_not_found(
    documentation_api,
    tmp_path,
):
    application, _, _ = documentation_api
    outside = tmp_path / "outside.md"
    outside.write_text("# Secret\nDo not expose this file.", encoding="utf-8")
    document_ids = (
        "missing",
        "..",
        "../outside",
        str(outside),
        "C:\\outside",
        "overview.md",
    )

    with TestClient(application) as client:
        responses = [
            client.get(
                f"/api/documentation/{document_id}",
                headers=documentation_headers(),
            )
            for document_id in document_ids
        ]

    assert all(response.status_code == 404 for response in responses)
    assert all("Do not expose this file" not in response.text for response in responses)


def test_empty_source_is_a_successful_empty_list(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    application = create_app(
        CorporationApplicationService(MagicMock(spec=Orchestrator)),
        DocumentationTestAuthenticationBackend(),
        documentation_source=MarkdownDocumentationSource(root),
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/documentation",
            headers=documentation_headers(),
        )

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_default_source_is_configured_to_the_internal_document_directory():
    application = create_app(
        CorporationApplicationService(MagicMock(spec=Orchestrator)),
        DocumentationTestAuthenticationBackend(),
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/documentation",
            headers=documentation_headers(),
        )

    assert response.status_code == 200
    assert {item["id"] for item in response.json()["items"]} == {
        "api-and-web-ui-boundaries",
        "corporation-overview",
    }


def test_unavailable_source_is_a_server_error_not_an_empty_list(tmp_path):
    application = create_app(
        CorporationApplicationService(MagicMock(spec=Orchestrator)),
        DocumentationTestAuthenticationBackend(),
        documentation_source=MarkdownDocumentationSource(tmp_path / "missing"),
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/documentation",
            headers=documentation_headers(),
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Documentation source unavailable"}
    assert str(tmp_path) not in response.text


def test_symlink_escape_is_neither_listed_nor_read(documentation_api, tmp_path):
    application, _, root = documentation_api
    outside = tmp_path / "outside.md"
    outside.write_text("# Secret\nDo not expose this file.", encoding="utf-8")
    link = root / "escape.md"
    try:
        link.symlink_to(outside)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")

    with TestClient(application) as client:
        listing = client.get(
            "/api/documentation",
            headers=documentation_headers(),
        )
        detail = client.get(
            "/api/documentation/escape",
            headers=documentation_headers(),
        )

    assert "escape" not in {item["id"] for item in listing.json()["items"]}
    assert detail.status_code == 404
    assert "Do not expose this file" not in detail.text


def test_symlinked_source_root_is_unavailable(tmp_path):
    external_root = tmp_path / "external-documents"
    external_root.mkdir()
    (external_root / "outside.md").write_text("# Outside\n", encoding="utf-8")
    root_link = tmp_path / "linked-document-root"
    try:
        root_link.symlink_to(external_root, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")

    with pytest.raises(DocumentationSourceUnavailable):
        MarkdownDocumentationSource(root_link).list_documents()


def test_symlink_metadata_is_rejected_without_platform_symlink_support(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "docs"
    root.mkdir()
    (root / "escape.md").write_text("# Outside\n", encoding="utf-8")
    original_is_symlink = Path.is_symlink

    def report_escape_as_symlink(path):
        return path.name == "escape.md" or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", report_escape_as_symlink)
    with pytest.raises(DocumentationNotFound):
        MarkdownDocumentationSource(root).get_document("escape")


def test_resolved_document_outside_root_is_rejected(tmp_path, monkeypatch):
    root = tmp_path / "docs"
    root.mkdir()
    candidate = root / "escape.md"
    candidate.write_text("# Do not expose\n", encoding="utf-8")
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    outside = outside_root / "escape.md"
    outside.write_text("# Secret\nDo not expose this file.", encoding="utf-8")
    original_resolve = Path.resolve

    def resolve_escape(path, strict=False):
        if path == candidate:
            return outside
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve_escape)
    with pytest.raises(DocumentationNotFound):
        MarkdownDocumentationSource(root).get_document("escape")


def test_symlinked_documentation_root_metadata_is_rejected(
    tmp_path,
    monkeypatch,
):
    external_root = tmp_path / "external-documents"
    external_root.mkdir()
    (external_root / "outside.md").write_text("# Outside\n", encoding="utf-8")
    root_link = tmp_path / "linked-document-root"
    root_link.mkdir()
    original_is_symlink = Path.is_symlink

    def report_root_as_symlink(path):
        return path == root_link or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", report_root_as_symlink)
    with pytest.raises(DocumentationSourceUnavailable):
        MarkdownDocumentationSource(root_link).list_documents()


def test_documentation_api_has_no_write_routes(documentation_api):
    application, _, _ = documentation_api

    with TestClient(application) as client:
        post_response = client.post("/api/documentation")
        put_response = client.put("/api/documentation/overview")
        delete_response = client.delete("/api/documentation/overview")

    assert post_response.status_code == 405
    assert put_response.status_code == 405
    assert delete_response.status_code == 405
    paths = application.openapi()["paths"]
    assert set(paths["/api/documentation"]) == {"get"}
    assert set(paths["/api/documentation/{document_id}"]) == {"get"}
