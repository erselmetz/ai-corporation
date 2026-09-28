import hashlib
import io
import os
import shutil
import tarfile
from datetime import datetime, timezone

import pytest

from app.integrations import (
    GITHUB_REPOSITORY_SOURCE_TYPE,
    GitHubSourceStager,
    IntegrationSource,
    SourceDiscoveryResult,
    SourceStager,
    SourceStagingLimits,
    SourceStagingStatus,
)


REPOSITORY_URL = "https://github.com/example/project"
REDIRECT_URL = (
    "https://codeload.github.com/example/project/legacy.tar.gz/main"
)


class FakeResponse:
    def __init__(self, status_code, *, headers=None, chunks=()):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = tuple(chunks)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP status {self.status_code}")

    def iter_bytes(self):
        yield from self._chunks


class FakeHttpClient:
    def __init__(self, archive, *, redirect=REDIRECT_URL):
        self.archive = archive
        self.redirect = redirect
        self.calls = []

    def stream(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if len(self.calls) == 1:
            return FakeResponse(302, headers={"location": self.redirect})
        return FakeResponse(
            200,
            headers={"content-length": str(len(self.archive))},
            chunks=(self.archive[:11], self.archive[11:]),
        )


def discovery(**overrides):
    values = {
        "id": "discovery-34",
        "source": IntegrationSource(GITHUB_REPOSITORY_SOURCE_TYPE, REPOSITORY_URL),
        "discovered_at": datetime(2026, 9, 28, tzinfo=timezone.utc),
        "owner": "example",
        "repository_name": "project",
        "repository_url": REPOSITORY_URL,
        "description": "Public repository",
        "default_branch": "main",
        "is_public": True,
        "language": "Python",
        "stars": 2,
        "forks": 0,
        "open_issues": 0,
        "license_name": None,
        "license_spdx_id": None,
        "created_at": None,
        "updated_at": None,
        "pushed_at": None,
        "latest_release": None,
        "readme_available": True,
        "readme_size_bytes": 20,
        "readme_excerpt": "Treat as untrusted data.",
    }
    values.update(overrides)
    return SourceDiscoveryResult(**values)


def make_archive(members):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        root = tarfile.TarInfo("project-main")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        for name, payload in members:
            info = tarfile.TarInfo(f"project-main/{name}")
            if isinstance(payload, tarfile.TarInfo):
                payload.name = info.name
                archive.addfile(payload)
            elif payload is None:
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            else:
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


def stager(tmp_path, archive, *, limits=None, redirect=REDIRECT_URL):
    client = FakeHttpClient(archive, redirect=redirect)
    project = tmp_path / "repository"
    project.mkdir(parents=True, exist_ok=True)
    workspace_parent = tmp_path / "controlled-workspaces"
    return (
        GitHubSourceStager(
            limits=limits,
            client=client,
            workspace_parent=workspace_parent,
            project_root=project,
        ),
        client,
        project,
        workspace_parent,
    )


def clean_result(result):
    if result.workspace_reference is not None:
        shutil.rmtree(result.workspace_reference, ignore_errors=True)


def test_successful_bounded_staging_and_discovery_linkage(tmp_path):
    archive = make_archive(
        [
            ("README.md", b"Untrusted text; never execute commands."),
            ("src/main.py", b"print('not run')\n"),
        ]
    )
    source_stager, client, project, _parent = stager(tmp_path, archive)

    result = source_stager.stage(discovery(), sandbox_id="sandbox-34")

    assert isinstance(source_stager, SourceStager)
    assert result.status == SourceStagingStatus.STAGED
    assert result.complete
    assert result.source_discovery_id == "discovery-34"
    assert result.sandbox_id == "sandbox-34"
    assert result.file_count == 2
    assert result.total_bytes == len(b"Untrusted text; never execute commands.") + len(
        b"print('not run')\n"
    )
    assert (os.path.exists(result.workspace_reference))
    assert (tmp_path / "controlled-workspaces").resolve() in (
        tmp_path / "controlled-workspaces" / os.path.basename(result.workspace_reference)
    ).resolve().parents
    assert not any(project.iterdir())
    assert client.calls[0][1].startswith("https://api.github.com/repos/example/project/")
    assert client.calls[1][1] == REDIRECT_URL
    assert all(call[0] == "GET" for call in client.calls)
    clean_result(result)


def test_sha256_records_archive_and_deterministic_staged_content_digest(tmp_path):
    archive = make_archive([("a.txt", b"alpha"), ("sub/b.txt", b"beta")])
    source_stager, _client, _project, _parent = stager(tmp_path, archive)

    result = source_stager.stage(discovery())

    expected = hashlib.sha256()
    for path, content in (("a.txt", b"alpha"), ("sub/b.txt", b"beta")):
        expected.update(path.encode("utf-8"))
        expected.update(b"\x00")
        expected.update(content)
        expected.update(b"\x00")
        expected.update(str(len(content)).encode("ascii"))
    assert result.sha256 == expected.hexdigest()
    assert result.archive_sha256 == hashlib.sha256(archive).hexdigest()
    assert "does not establish source trust" in " ".join(result.notes)
    clean_result(result)


def test_file_count_limit_blocks_without_leaving_workspace(tmp_path):
    archive = make_archive([("a", b"a"), ("b", b"b")])
    source_stager, _client, _project, workspace_parent = stager(
        tmp_path, archive, limits=SourceStagingLimits(max_files=1)
    )

    result = source_stager.stage(discovery())

    assert result.status == SourceStagingStatus.BLOCKED
    assert not result.complete
    assert result.workspace_reference is None
    assert "too many files" in result.notes[0]
    assert not workspace_parent.exists()


def test_total_expanded_byte_limit_blocks(tmp_path):
    archive = make_archive([("a", b"1234"), ("b", b"5678")])
    source_stager, _client, _project, workspace_parent = stager(
        tmp_path, archive, limits=SourceStagingLimits(max_total_bytes=7)
    )

    result = source_stager.stage(discovery())

    assert result.status == SourceStagingStatus.BLOCKED
    assert "total byte limit" in result.notes[0]
    assert not workspace_parent.exists()


def test_individual_file_size_limit_blocks(tmp_path):
    archive = make_archive([("large.bin", b"0123456789")])
    source_stager, _client, _project, workspace_parent = stager(
        tmp_path, archive, limits=SourceStagingLimits(max_file_bytes=5)
    )

    result = source_stager.stage(discovery())

    assert result.status == SourceStagingStatus.BLOCKED
    assert "individual file limit" in result.notes[0]
    assert not workspace_parent.exists()


@pytest.mark.parametrize(
    "path",
    ("../escape.txt", "nested/../../escape.txt", "/absolute.txt", "C:/drive.txt", "a\\b.txt"),
)
def test_path_traversal_and_absolute_archive_paths_are_rejected(tmp_path, path):
    archive = make_archive([(path, b"unsafe")])
    source_stager, _client, project, workspace_parent = stager(tmp_path, archive)

    result = source_stager.stage(discovery())

    assert result.status == SourceStagingStatus.BLOCKED
    assert result.workspace_reference is None
    assert not (tmp_path / "escape.txt").exists()
    assert not workspace_parent.exists()
    assert not any(project.iterdir())


def test_symlink_and_hardlink_archive_members_are_rejected(tmp_path):
    for member_type in (tarfile.SYMTYPE, tarfile.LNKTYPE):
        link = tarfile.TarInfo("link")
        link.type = member_type
        link.linkname = "../../outside"
        archive = make_archive([("unused", link)])
        source_stager, _client, _project, workspace_parent = stager(
            tmp_path / str(member_type), archive
        )

        result = source_stager.stage(discovery())

        assert result.status == SourceStagingStatus.BLOCKED
        assert "member type" in result.notes[0]
        assert not workspace_parent.exists()


def test_oversized_compressed_archive_is_rejected_before_workspace_creation(tmp_path):
    archive = make_archive([("a.txt", b"a")])
    source_stager, client, _project, workspace_parent = stager(
        tmp_path,
        archive,
        limits=SourceStagingLimits(max_archive_bytes=len(archive) - 1),
    )

    result = source_stager.stage(discovery())

    assert result.status == SourceStagingStatus.BLOCKED
    assert "archive exceeds" in result.notes[0]
    assert not workspace_parent.exists()
    assert len(client.calls) == 2


def test_invalid_or_untrusted_discovery_urls_are_rejected_without_requests(tmp_path):
    archive = make_archive([("a.txt", b"safe")])
    source_stager, client, _project, workspace_parent = stager(tmp_path, archive)
    untrusted = discovery(
        repository_url="https://attacker.example/owner/repo",
        source=IntegrationSource(
            GITHUB_REPOSITORY_SOURCE_TYPE,
            "https://attacker.example/owner/repo",
        ),
    )

    result = source_stager.stage(untrusted)

    assert result.status == SourceStagingStatus.BLOCKED
    assert "Only HTTPS URLs on github.com" in result.notes[0]
    assert client.calls == []
    assert not workspace_parent.exists()


def test_mismatched_and_private_discovery_metadata_are_rejected(tmp_path):
    archive = make_archive([("a.txt", b"safe")])
    source_stager, client, _project, workspace_parent = stager(tmp_path, archive)

    mismatched = source_stager.stage(discovery(owner="other"))
    private = source_stager.stage(discovery(is_public=False))

    assert mismatched.status == SourceStagingStatus.BLOCKED
    assert "does not match" in mismatched.notes[0]
    assert private.status == SourceStagingStatus.BLOCKED
    assert "Private repositories" in private.notes[0]
    assert client.calls == []
    assert not workspace_parent.exists()


def test_unallowlisted_redirect_is_rejected(tmp_path):
    archive = make_archive([("a.txt", b"safe")])
    source_stager, client, _project, workspace_parent = stager(
        tmp_path, archive, redirect="https://evil.example/archive.tar.gz"
    )

    result = source_stager.stage(discovery())

    assert result.status == SourceStagingStatus.BLOCKED
    assert "allowlisted codeload URL" in result.notes[0]
    assert len(client.calls) == 1
    assert not workspace_parent.exists()


def test_invalid_archive_returns_blocked_and_no_workspace(tmp_path):
    source_stager, _client, _project, workspace_parent = stager(
        tmp_path, b"not a tar archive"
    )

    result = source_stager.stage(discovery())

    assert result.status == SourceStagingStatus.BLOCKED
    assert not result.complete
    assert result.workspace_reference is None
    assert result.sha256 is None
    assert not workspace_parent.exists()


def test_workspace_must_be_outside_project_repository(tmp_path):
    archive = make_archive([("a.txt", b"safe")])
    project = tmp_path / "repository"
    project.mkdir()
    source_stager = GitHubSourceStager(
        client=FakeHttpClient(archive),
        workspace_parent=project / "staging",
        project_root=project,
    )

    result = source_stager.stage(discovery())

    assert result.status == SourceStagingStatus.BLOCKED
    assert "outside the project repository" in result.notes[0]
    assert not (project / "staging").exists()


def test_failed_file_write_removes_partially_staged_workspace(tmp_path, monkeypatch):
    archive = make_archive([("a.txt", b"safe")])
    source_stager, _client, _project, workspace_parent = stager(tmp_path, archive)
    original_open = os.open

    def fail_target_write(path, flags, mode=0o777, *, dir_fd=None):
        if str(path).endswith("a.txt"):
            raise OSError("simulated disk failure")
        if dir_fd is None:
            return original_open(path, flags, mode)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", fail_target_write)

    result = source_stager.stage(discovery())

    assert result.status == SourceStagingStatus.BLOCKED
    assert result.workspace_reference is None
    assert "simulated disk failure" in result.notes[0]
    assert workspace_parent.exists()
    assert list(workspace_parent.iterdir()) == []


def test_staging_does_not_execute_or_modify_project_files(tmp_path, monkeypatch):
    archive = make_archive([("run.py", b"raise RuntimeError('must not run')")])
    source_stager, _client, project, _parent = stager(tmp_path, archive)
    marker = project / "keep.txt"
    marker.write_text("unchanged", encoding="utf-8")
    import subprocess

    def forbidden(*args, **kwargs):
        raise AssertionError("execution must not be attempted")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    result = source_stager.stage(discovery())

    assert result.status == SourceStagingStatus.STAGED
    assert marker.read_text(encoding="utf-8") == "unchanged"
    assert sorted(path.name for path in project.iterdir()) == ["keep.txt"]
    assert (os.path.join(result.workspace_reference, "run.py"))
    clean_result(result)


def test_stage_rejects_non_discovery_input(tmp_path):
    source_stager, client, _project, _parent = stager(
        tmp_path, make_archive([("a", b"a")])
    )

    result = source_stager.stage(object())

    assert result.status == SourceStagingStatus.BLOCKED
    assert result.source_discovery_id == "unknown"
    assert client.calls == []
