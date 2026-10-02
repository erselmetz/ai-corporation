from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.database import get_connection, initialize_database
from app.orchestrator.execution_queue import ExecutionQueue, QueueState
from app.orchestrator.task import Task, TaskStatus
from app.runtime.factory import create_corporation_runtime

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


@pytest.fixture
def setup():
    runtime = create_corporation_runtime()
    for identifier in ("a", "b", "c"):
        runtime.tasks.register(Task(identifier, identifier, "Work"))
    return runtime, runtime.application_service.execution_queue()


def test_fifo_order_claim_snapshot_and_restart_without_replay(setup):
    runtime, queue = setup
    first = queue.enqueue("entry-b", "b", now=NOW)
    queue.enqueue("entry-a", "a", now=NOW)
    assert [entry.task_id for entry in queue.list()] == ["b", "a"]
    claim = queue.claim_next(worker_id="worker", claim_id="claim-b", now=NOW)
    assert claim.task_id == "b"
    assert first.state is QueueState.QUEUED
    with pytest.raises(FrozenInstanceError):
        claim.state = QueueState.QUEUED
    restarted = create_corporation_runtime().application_service.execution_queue()
    assert restarted.get("entry-b") == claim
    assert restarted.claim_next(worker_id="worker", claim_id="claim-a", now=NOW).task_id == "a"
    assert restarted.claim_next(worker_id="worker", claim_id="empty", now=NOW) is None
    assert runtime.tasks.get("b").status is TaskStatus.PENDING


@pytest.mark.parametrize("status", [TaskStatus.COMPLETED, TaskStatus.FAILED])
def test_acknowledge_requires_matching_claim_and_actual_terminal_task(setup, status):
    runtime, queue = setup
    queue.enqueue("entry", "a", now=NOW)
    queue.claim_next(worker_id="worker", claim_id="claim", now=NOW)
    with pytest.raises(ValueError, match="terminal"):
        queue.acknowledge("entry", worker_id="worker", claim_id="claim", now=NOW)
    runtime.tasks.update(replace(runtime.tasks.get("a"), status=status))
    with pytest.raises(ValueError, match="matching"):
        queue.acknowledge("entry", worker_id="other", claim_id="claim", now=NOW)
    completed = queue.acknowledge("entry", worker_id="worker", claim_id="claim", now=NOW)
    assert completed.state.value == status.value
    with pytest.raises(ValueError):
        queue.acknowledge("entry", worker_id="worker", claim_id="claim", now=NOW)


def test_interrupted_claim_requires_explicit_resolution_and_never_requeues(setup):
    _, queue = setup
    queue.enqueue("entry", "a", now=NOW)
    queue.claim_next(worker_id="worker", claim_id="claim", now=NOW)
    restarted = ExecutionQueue("corp_local")
    with pytest.raises(ValueError):
        restarted.abandon("entry", resolution="Inspected manually", now=NOW)
    result = restarted.abandon("entry", resolution="Outcome uncertain; no replay", confirm=True, now=NOW)
    assert result.state is QueueState.ABANDONED
    assert result.claim_id == "claim"
    assert restarted.claim_next(worker_id="worker", claim_id="new", now=NOW) is None
    with pytest.raises(ValueError):
        restarted.enqueue("new", "a", now=NOW)


def test_invalid_head_blocks_fifo_until_human_resolution(setup):
    runtime, queue = setup
    queue.enqueue("first", "a", now=NOW)
    queue.enqueue("second", "b", now=NOW)
    runtime.tasks.update(replace(runtime.tasks.get("a"), status=TaskStatus.RUNNING))
    with pytest.raises(ValueError, match="human resolution"):
        queue.claim_next(worker_id="worker", claim_id="claim", now=NOW)
    assert queue.get("second").state is QueueState.QUEUED
    queue.abandon("first", resolution="Execution occurred outside queue", confirm=True, now=NOW)
    assert queue.claim_next(worker_id="worker", claim_id="claim", now=NOW).task_id == "b"


def test_duplicate_membership_and_claim_id_roll_back(setup):
    _, queue = setup
    queue.enqueue("first", "a", now=NOW)
    for entry, task in [("first", "b"), ("other", "a")]:
        with pytest.raises(ValueError):
            queue.enqueue(entry, task, now=NOW)
    queue.enqueue("second", "b", now=NOW)
    queue.claim_next(worker_id="worker", claim_id="claim", now=NOW)
    with pytest.raises(ValueError):
        queue.claim_next(worker_id="worker", claim_id="claim", now=NOW)
    assert queue.get("second").state is QueueState.QUEUED


def test_atomic_competing_claims_no_duplicate_claim(setup):
    _, queue = setup
    queue.enqueue("entry", "a", now=NOW)
    def claim(index):
        return queue.claim_next(worker_id="worker", claim_id=str(index), now=NOW)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(claim, range(12)))
    assert sum(result is not None for result in results) == 1


def test_scope_limits_missing_task_and_time_validation(setup):
    runtime, queue = setup
    with pytest.raises(ValueError):
        queue.enqueue("entry", "missing", now=NOW)
    runtime.tasks.update(replace(runtime.tasks.get("a"), status=TaskStatus.COMPLETED))
    with pytest.raises(ValueError):
        queue.enqueue("entry", "a", now=NOW)
    queue.enqueue("entry", "b", now=NOW)
    other = ExecutionQueue("other-corp")
    assert other.list() == ()
    with pytest.raises(KeyError):
        other.get("entry")
    with pytest.raises(ValueError):
        queue.claim_next(worker_id="worker", claim_id="claim", now=NOW - timedelta(seconds=1))
    with pytest.raises(ValueError):
        queue.list(limit=True)
    with pytest.raises(ValueError):
        queue.enqueue("another", "c", now=NOW.replace(tzinfo=None))


def test_additive_initialization_and_corrupt_data_rejection(setup):
    runtime, queue = setup
    original = queue.enqueue("entry", "a", now=NOW)
    initialize_database(); initialize_database()
    assert queue.get("entry") == original
    assert create_corporation_runtime().tasks.get("a").title == "a"
    connection = get_connection()
    try:
        with connection:
            connection.execute("UPDATE execution_queue SET updated_at='invalid'")
    finally:
        connection.close()
    with pytest.raises(ValueError, match="Stored queue"):
        queue.list()
