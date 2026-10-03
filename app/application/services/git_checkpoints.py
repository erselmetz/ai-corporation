"""Create local Git checkpoint commits from exactly approved maintenance patches."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from threading import Event, RLock, Thread
from uuid import uuid4

from .maintenance_approvals import (
    MaintenanceApprovalService,
    MaintenanceApprovalSummary,
)
from .patch_development import (
    PatchDevelopmentService,
    PatchWorkspace,
    _apply_file_patch,
    _parse_unified_diff,
    _source_digest,
    _source_file,
    _validate_relative_path,
)


class GitCheckpointError(RuntimeError):
    """A bounded Git operation could not create a checkpoint."""


class GitCheckpointBlockedError(GitCheckpointError):
    """A policy precondition for checkpoint creation was not met."""


class GitCheckpointNotFoundError(LookupError):
    pass


class GitCheckpointCapacityError(GitCheckpointError):
    pass


class _GitCommandFailure(RuntimeError):
    def __init__(self, returncode: int):
        self.returncode = returncode


@dataclass(frozen=True, slots=True)
class GitCheckpoint:
    checkpoint_id: str
    workspace_id: str
    proposal_id: str
    approval_request_id: str
    branch_name: str
    commit_sha: str
    parent_sha: str
    patch_sha256: str
    source_sha256: str
    changed_files: tuple[str, ...]
    created_by: str
    created_at: datetime
    unified_diff: str = field(repr=False)


class GitCheckpointService:
    MAX_CHECKPOINTS = 100
    MAX_FILE_BYTES = PatchDevelopmentService.MAX_FILE_BYTES
    MAX_TOTAL_SOURCE_BYTES = PatchDevelopmentService.MAX_TOTAL_SOURCE_BYTES
    MAX_GIT_OUTPUT_BYTES = 64 * 1024
    GIT_TIMEOUT_SECONDS = 15
    _CHECKPOINT_BRANCH_PREFIX = "maintenance-checkpoints"
    _SUPPORTED_FILE_MODES = {b"100644", b"100755"}
    _SAFE_ENVIRONMENT = (
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "TEMP",
        "TMP",
        "LANG",
        "LC_ALL",
    )

    def __init__(
        self,
        workspaces: PatchDevelopmentService,
        approvals: MaintenanceApprovalService,
    ):
        if not isinstance(workspaces, PatchDevelopmentService):
            raise TypeError("workspaces must be a PatchDevelopmentService")
        if not isinstance(approvals, MaintenanceApprovalService):
            raise TypeError("approvals must be a MaintenanceApprovalService")
        self._workspaces = workspaces
        self._approvals = approvals
        self._git_executable = shutil.which("git")
        self._records: dict[str, GitCheckpoint] = {}
        self._workspace_records: dict[str, str] = {}
        self._lock = RLock()

    def create(self, workspace_id: str, *, created_by: str) -> GitCheckpoint:
        _validate_creator_identity(created_by)
        try:
            workspace = self._workspaces.get(workspace_id)
        except ValueError:
            raise GitCheckpointNotFoundError(
                "Maintenance workspace was not found"
            ) from None
        approval = self._approvals.require_approved(workspace_id)

        with self._lock:
            existing_id = self._workspace_records.get(workspace.workspace_id)
            if existing_id is not None:
                existing = self._records[existing_id]
                if (
                    existing.patch_sha256 == workspace.patch_sha256
                    and existing.source_sha256 == workspace.source_sha256
                    and existing.approval_request_id == approval.request_id
                ):
                    return existing
                raise GitCheckpointBlockedError(
                    "A checkpoint already exists for this workspace"
                )
            if len(self._records) >= self.MAX_CHECKPOINTS:
                raise GitCheckpointCapacityError(
                    "Maintenance checkpoint record limit reached"
                )
            checkpoint = self._create_checkpoint(
                workspace,
                approval,
                created_by=created_by,
            )
            self._records[checkpoint.checkpoint_id] = checkpoint
            self._workspace_records[workspace.workspace_id] = (
                checkpoint.checkpoint_id
            )
            return checkpoint

    def list(self) -> tuple[GitCheckpoint, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._records.values(),
                    key=lambda checkpoint: checkpoint.created_at,
                    reverse=True,
                )
            )

    def get(self, checkpoint_id: str) -> GitCheckpoint:
        if not isinstance(checkpoint_id, str) or not checkpoint_id:
            raise GitCheckpointNotFoundError("Git checkpoint was not found")
        with self._lock:
            try:
                return self._records[checkpoint_id]
            except KeyError:
                raise GitCheckpointNotFoundError(
                    "Git checkpoint was not found"
                ) from None

    def _create_checkpoint(
        self,
        workspace: PatchWorkspace,
        approval: MaintenanceApprovalSummary,
        *,
        created_by: str,
    ) -> GitCheckpoint:
        if self._git_executable is None:
            raise GitCheckpointError("Git is not available on this installation")
        if not re.fullmatch(r"[0-9a-f]{32}", workspace.workspace_id):
            raise GitCheckpointBlockedError(
                "Maintenance workspace identifier is invalid"
            )
        if workspace.source_root is None:
            raise GitCheckpointBlockedError(
                "Maintenance workspace has no registered source repository"
            )
        if (
            workspace.patch_sha256 != approval.patch_sha256
            or workspace.source_sha256 != approval.source_sha256
            or workspace.unified_diff == ""
        ):
            raise GitCheckpointBlockedError(
                "Approved maintenance workspace is unavailable or has changed"
            )

        try:
            source_root = workspace.source_root.resolve(strict=True)
        except (OSError, RuntimeError):
            raise GitCheckpointBlockedError(
                "Maintenance source repository is unavailable"
            ) from None
        if not source_root.is_dir():
            raise GitCheckpointBlockedError(
                "Maintenance source repository is unavailable"
            )

        with tempfile.TemporaryDirectory(
            prefix="ai-corp-git-checkpoint-"
        ) as temporary_directory:
            context_directory = Path(temporary_directory)
            hooks_directory = context_directory / "empty-hooks"
            hooks_directory.mkdir()
            repository_root = self._repository_root(
                source_root, hooks_directory
            )
            try:
                source_prefix = source_root.relative_to(repository_root)
            except ValueError:
                raise GitCheckpointBlockedError(
                    "Maintenance source is outside its Git repository"
                ) from None

            patched_files, repository_paths = self._validated_patch(
                workspace, source_root, source_prefix
            )
            parent_sha = self._head(repository_root, hooks_directory)
            self._require_clean_repository(repository_root, hooks_directory)
            self._require_identity(repository_root, hooks_directory)
            self._require_unsigned_policy(repository_root, hooks_directory)

            branch_name = (
                f"{self._CHECKPOINT_BRANCH_PREFIX}/{workspace.workspace_id}"
            )
            branch_ref = f"refs/heads/{branch_name}"

            empty_object_id = b"0" * len(parent_sha)
            index_path = context_directory / "index"
            index_environment = self._environment(
                hooks_directory, index_path=index_path
            )
            self._run_git(
                ("read-tree", parent_sha.decode("ascii")),
                repository_root,
                hooks_directory,
                environment=index_environment,
            )
            for source_path, content in patched_files.items():
                repository_path = repository_paths[source_path]
                mode = self._tracked_file_mode(
                    repository_root,
                    hooks_directory,
                    repository_path,
                )
                blob_id = self._run_git(
                    ("hash-object", "-w", "--stdin"),
                    repository_root,
                    hooks_directory,
                    input_data=content,
                ).strip()
                if not re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", blob_id):
                    raise GitCheckpointError(
                        "Git returned an invalid object identifier"
                    )
                self._run_git(
                    (
                        "update-index",
                        "--add",
                        "--cacheinfo",
                        mode.decode("ascii"),
                        blob_id.decode("ascii"),
                        repository_path,
                    ),
                    repository_root,
                    hooks_directory,
                    environment=index_environment,
                )
            tree_id = self._run_git(
                ("write-tree",),
                repository_root,
                hooks_directory,
                environment=index_environment,
            ).strip()
            message = (
                "Approved maintenance checkpoint\n\n"
                f"Workspace: {workspace.workspace_id}\n"
                f"Approval: {approval.request_id}\n"
                f"Checkpoint-Created-By: {created_by}\n"
                f"Patch SHA-256: {workspace.patch_sha256}\n"
                f"Source SHA-256: {workspace.source_sha256}\n"
            )
            commit_id = self._run_git(
                (
                    "commit-tree",
                    tree_id.decode("ascii"),
                    "-p",
                    parent_sha.decode("ascii"),
                    "-m",
                    message,
                ),
                repository_root,
                hooks_directory,
            ).strip()
            if not re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", commit_id):
                raise GitCheckpointError(
                    "Git returned an invalid checkpoint identifier"
                )

            current_approval = self._approvals.require_approved(
                workspace.workspace_id
            )
            if current_approval.request_id != approval.request_id:
                raise GitCheckpointBlockedError(
                    "The approved maintenance workspace changed during checkpoint creation"
                )
            current_head = self._head(repository_root, hooks_directory)
            if current_head != parent_sha:
                raise GitCheckpointBlockedError(
                    "The source repository changed during checkpoint creation"
                )
            self._require_clean_repository(repository_root, hooks_directory)
            try:
                self._run_git(
                    (
                        "update-ref",
                        branch_ref,
                        commit_id.decode("ascii"),
                        empty_object_id.decode("ascii"),
                    ),
                    repository_root,
                    hooks_directory,
                )
            except _GitCommandFailure:
                raise GitCheckpointBlockedError(
                    "The maintenance checkpoint branch could not be created"
                ) from None

        return GitCheckpoint(
            checkpoint_id=uuid4().hex,
            workspace_id=workspace.workspace_id,
            proposal_id=workspace.proposal_id,
            approval_request_id=approval.request_id,
            branch_name=branch_name,
            commit_sha=commit_id.decode("ascii"),
            parent_sha=parent_sha.decode("ascii"),
            patch_sha256=workspace.patch_sha256,
            source_sha256=workspace.source_sha256,
            changed_files=workspace.changed_files,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            unified_diff=workspace.unified_diff,
        )

    def _validated_patch(
        self,
        workspace: PatchWorkspace,
        source_root: Path,
        source_prefix: Path,
    ) -> tuple[dict[str, bytes], dict[str, str]]:
        try:
            parsed = _parse_unified_diff(
                workspace.unified_diff,
                frozenset(workspace.files),
                PatchDevelopmentService.MAX_LINES,
            )
            if tuple(sorted(parsed)) != workspace.changed_files:
                raise ValueError("Patch file list changed")
            source_contents: dict[str, bytes] = {}
            repository_paths: dict[str, str] = {}
            total_bytes = 0
            for relative_path in workspace.files:
                safe_path = _validate_relative_path(relative_path)
                source_file = _source_file(source_root, safe_path)
                with source_file.open("rb") as stream:
                    content = stream.read(self.MAX_FILE_BYTES + 1)
                if len(content) > self.MAX_FILE_BYTES:
                    raise ValueError("Source file exceeds the byte limit")
                total_bytes += len(content)
                if total_bytes > self.MAX_TOTAL_SOURCE_BYTES:
                    raise ValueError("Source files exceed the total byte limit")
                source_contents[safe_path] = content
                repository_path = (
                    PurePosixPath(*source_prefix.parts)
                    / PurePosixPath(safe_path)
                ).as_posix()
                repository_paths[safe_path] = _validate_relative_path(
                    repository_path
                )
            if _source_digest(source_contents) != workspace.source_sha256:
                raise ValueError("Source digest changed")
            patched_files = {
                path: _apply_file_patch(
                    source_contents[path],
                    hunks,
                    self.MAX_FILE_BYTES,
                )
                for path, hunks in parsed.items()
            }
            return patched_files, repository_paths
        except (OSError, ValueError):
            raise GitCheckpointBlockedError(
                "Approved maintenance patch no longer matches its source"
            ) from None

    def _repository_root(
        self,
        source_root: Path,
        hooks_directory: Path,
    ) -> Path:
        try:
            raw_root = self._run_git(
                ("rev-parse", "--show-toplevel"),
                source_root,
                hooks_directory,
            )
        except _GitCommandFailure:
            raise GitCheckpointBlockedError(
                "Maintenance source directory is not an available Git repository"
            ) from None
        try:
            repository_root = Path(
                os.fsdecode(raw_root).rstrip("\r\n")
            ).resolve(strict=True)
        except (OSError, RuntimeError):
            raise GitCheckpointBlockedError(
                "Maintenance source directory is not an available Git repository"
            ) from None
        if not repository_root.is_dir():
            raise GitCheckpointBlockedError(
                "Maintenance source directory is not an available Git repository"
            )
        return repository_root

    def _head(self, repository_root: Path, hooks_directory: Path) -> bytes:
        try:
            head = self._run_git(
                ("rev-parse", "--verify", "HEAD"),
                repository_root,
                hooks_directory,
            ).strip()
        except _GitCommandFailure:
            raise GitCheckpointBlockedError(
                "Git repository must have an existing commit"
            ) from None
        if not re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", head):
            raise GitCheckpointError("Git returned an invalid HEAD identifier")
        return head

    def _require_clean_repository(
        self,
        repository_root: Path,
        hooks_directory: Path,
    ) -> None:
        self._require_no_differences(
            (
                "diff-index",
                "--cached",
                "--quiet",
                "--ignore-submodules=none",
                "HEAD",
                "--",
            ),
            repository_root,
            hooks_directory,
        )
        self._require_no_differences(
            ("diff-files", "--quiet", "--ignore-submodules=none", "--"),
            repository_root,
            hooks_directory,
        )
        if self._has_untracked_files(repository_root, hooks_directory):
            raise GitCheckpointBlockedError(
                "Git checkpoints require a clean worktree and index"
            )

    def _require_no_differences(
        self,
        arguments: tuple[str, ...],
        repository_root: Path,
        hooks_directory: Path,
    ) -> None:
        try:
            self._run_git(
                arguments,
                repository_root,
                hooks_directory,
            )
        except _GitCommandFailure as error:
            if error.returncode == 1:
                raise GitCheckpointBlockedError(
                    "Git checkpoints require a clean worktree and index"
                ) from None
            raise GitCheckpointError(
                "Git could not inspect the source repository changes"
            ) from None

    def _has_untracked_files(
        self,
        repository_root: Path,
        hooks_directory: Path,
    ) -> bool:
        if self._git_executable is None:
            raise GitCheckpointError("Git is not available on this installation")
        command = [
            self._git_executable,
            "-c",
            f"core.hooksPath={hooks_directory}",
            "-c",
            "core.fsmonitor=false",
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--directory",
        ]
        try:
            process = subprocess.Popen(
                command,
                cwd=repository_root,
                env=self._environment(hooks_directory),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            raise GitCheckpointError(
                "Git could not inspect untracked source files"
            ) from None
        if process.stdout is None:
            if process.poll() is None:
                process.kill()
            process.wait()
            raise GitCheckpointError(
                "Git could not inspect untracked source files"
            )

        first_byte = bytearray()
        read_error: list[OSError] = []
        output_ready = Event()

        def read_one_byte() -> None:
            try:
                value = process.stdout.read(1)
                if value:
                    first_byte.extend(value)
            except OSError as error:
                read_error.append(error)
            finally:
                output_ready.set()

        reader = Thread(target=read_one_byte, daemon=True)
        reader.start()
        if not output_ready.wait(self.GIT_TIMEOUT_SECONDS):
            if process.poll() is None:
                process.kill()
            process.wait()
            reader.join()
            process.stdout.close()
            raise GitCheckpointError(
                "Git untracked-file inspection exceeded its time limit"
            )
        if first_byte:
            if process.poll() is None:
                process.kill()
            process.wait()
            reader.join()
            process.stdout.close()
            return True
        try:
            return_code = process.wait(timeout=self.GIT_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                process.kill()
            process.wait()
            reader.join()
            process.stdout.close()
            raise GitCheckpointError(
                "Git untracked-file inspection exceeded its time limit"
            ) from None
        reader.join()
        process.stdout.close()
        if read_error or return_code != 0:
            raise GitCheckpointError(
                "Git could not inspect untracked source files"
            )
        return False

    def _require_identity(
        self,
        repository_root: Path,
        hooks_directory: Path,
    ) -> None:
        try:
            self._run_git(
                ("var", "GIT_AUTHOR_IDENT"),
                repository_root,
                hooks_directory,
            )
            self._run_git(
                ("var", "GIT_COMMITTER_IDENT"),
                repository_root,
                hooks_directory,
            )
        except _GitCommandFailure:
            raise GitCheckpointBlockedError(
                "Git author and committer identity must be configured"
            ) from None

    def _require_unsigned_policy(
        self,
        repository_root: Path,
        hooks_directory: Path,
    ) -> None:
        try:
            result = self._run_git(
                ("config", "--bool", "--get", "commit.gpgsign"),
                repository_root,
                hooks_directory,
                expected_codes=(0, 1),
            )
        except _GitCommandFailure:
            raise GitCheckpointError(
                "Git commit-signing policy could not be determined"
            ) from None
        if result.strip().lower() == b"true":
            raise GitCheckpointBlockedError(
                "Configured signed commits are not supported for maintenance checkpoints"
            )

    def _tracked_file_mode(
        self,
        repository_root: Path,
        hooks_directory: Path,
        repository_path: str,
    ) -> bytes:
        pathspec = f":(literal){repository_path}"
        try:
            output = self._run_git(
                ("ls-files", "--stage", "-z", "--", pathspec),
                repository_root,
                hooks_directory,
            )
        except _GitCommandFailure:
            raise GitCheckpointError(
                "Git could not inspect a selected source file"
            ) from None
        entries = [entry for entry in output.split(b"\0") if entry]
        if len(entries) != 1 or b"\t" not in entries[0]:
            raise GitCheckpointBlockedError(
                "Checkpoint files must already be tracked by Git"
            )
        metadata, encoded_path = entries[0].split(b"\t", 1)
        try:
            mode, object_id, stage = metadata.split(b" ")
        except ValueError:
            raise GitCheckpointError(
                "Git returned invalid source file metadata"
            ) from None
        if (
            encoded_path != os.fsencode(repository_path)
            or mode not in self._SUPPORTED_FILE_MODES
            or stage != b"0"
            or not re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", object_id)
        ):
            raise GitCheckpointBlockedError(
                "Checkpoint files must be tracked regular files without merge conflicts"
            )
        return mode

    def _run_git(
        self,
        arguments: tuple[str, ...],
        cwd: Path,
        hooks_directory: Path,
        *,
        environment: dict[str, str] | None = None,
        input_data: bytes | None = None,
        expected_codes: tuple[int, ...] = (0,),
    ) -> bytes:
        if self._git_executable is None:
            raise GitCheckpointError("Git is not available on this installation")
        command = [
            self._git_executable,
            "-c",
            f"core.hooksPath={hooks_directory}",
            "-c",
            "core.fsmonitor=false",
            *arguments,
        ]
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=environment or self._environment(hooks_directory),
                input=input_data,
                stdin=None if input_data is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.GIT_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise GitCheckpointError(
                "A Git operation exceeded its time limit"
            ) from None
        except OSError:
            raise GitCheckpointError(
                "A Git operation could not be started"
            ) from None
        if (
            len(result.stdout) > self.MAX_GIT_OUTPUT_BYTES
            or len(result.stderr) > self.MAX_GIT_OUTPUT_BYTES
        ):
            raise GitCheckpointError("Git output exceeded the safety limit")
        if result.returncode not in expected_codes:
            raise _GitCommandFailure(result.returncode)
        return result.stdout

    def _environment(
        self,
        hooks_directory: Path,
        *,
        index_path: Path | None = None,
    ) -> dict[str, str]:
        environment = {
            key: os.environ[key]
            for key in self._SAFE_ENVIRONMENT
            if key in os.environ
        }
        environment["GIT_TERMINAL_PROMPT"] = "0"
        if index_path is not None:
            environment["GIT_INDEX_FILE"] = str(index_path)
        return environment


def _validate_creator_identity(created_by: str) -> None:
    if (
        not isinstance(created_by, str)
        or not created_by.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in created_by)
    ):
        raise ValueError("Checkpoint creator identity must be nonempty and line-safe")
    try:
        identity_size = len(created_by.encode("utf-8"))
    except UnicodeEncodeError:
        raise ValueError(
            "Checkpoint creator identity must be nonempty and line-safe"
        ) from None
    if identity_size > 256:
        raise ValueError("Checkpoint creator identity must be nonempty and line-safe")
