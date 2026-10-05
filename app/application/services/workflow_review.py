"""Process-local workflow lifecycle, bounded routing and owner reporting.

Workflow state is kept separate from Task lifecycle: a workflow only holds an
optional Task reference. Review is advisory and never replaces owner approval.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from app.providers.base import ProviderCapacityError


class WorkflowNotFound(ValueError):
    pass


class WorkflowConflict(ValueError):
    pass


class WorkNotStarted(RuntimeError):
    """Raised by a runner only when the provider confirms work did not start."""


MAX_DEPTH = 3
MAX_CHILDREN = 10
MAX_WORKFLOWS = 20
MAX_DESTINATIONS = 16
MAX_PROMPT_BYTES = 4096
MAX_OUTPUT_CHARS = 8192
ROLES = frozenset({"planner", "worker", "reviewer"})
PREFERENCES = frozenset({"local_first", "online_first"})
KINDS = frozenset({"local", "online"})


def _text(value, name, limit):
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > limit:
        raise ValueError(f"{name} must be non-empty text of at most {limit} bytes")
    return value.strip()


@dataclass(frozen=True)
class Destination:
    id: str
    kind: str
    provider_id: str
    model_id: str
    agent_id: str
    request_cost_cents: int | None = None
    fallback_authorized: bool = False


class WorkflowReviewService:
    def __init__(self, runner, *, clock=lambda: datetime.now(timezone.utc)):
        """runner(destination, prompt) -> str; it must enforce provider capacity."""
        self._runner = runner
        self._clock = clock
        self._lock = RLock()
        self._workflows: dict[str, dict] = {}

    def _now(self):
        return self._clock().isoformat()

    def create(self, owner_id, title, *, task_id=None, destinations, preference="local_first",
               max_depth=MAX_DEPTH, max_children=MAX_CHILDREN, spend_ceiling_cents=None,
               fallback_enabled=False):
        _text(owner_id, "owner_id", 256)
        title = _text(title, "title", 256)
        if task_id is not None:
            task_id = _text(task_id, "task_id", 256)
        if preference not in PREFERENCES:
            raise ValueError("Unsupported routing preference")
        if type(max_depth) is not int or not 1 <= max_depth <= MAX_DEPTH:
            raise ValueError("max_depth must be an integer from 1 to 3")
        if type(max_children) is not int or not 0 <= max_children <= MAX_CHILDREN:
            raise ValueError("max_children must be an integer from 0 to 10")
        if spend_ceiling_cents is not None and (
            type(spend_ceiling_cents) is not int or spend_ceiling_cents < 0
        ):
            raise ValueError("spend_ceiling_cents must be a non-negative integer")
        if type(fallback_enabled) is not bool:
            raise ValueError("fallback_enabled must be a boolean")
        if not isinstance(destinations, (list, tuple)) or not 1 <= len(destinations) <= MAX_DESTINATIONS:
            raise ValueError("Between 1 and 16 destinations are required")
        parsed = []
        for item in destinations:
            dest = item if isinstance(item, Destination) else Destination(**item)
            for name in ("id", "provider_id", "model_id", "agent_id"):
                _text(getattr(dest, name), name, 256)
            if dest.kind not in KINDS:
                raise ValueError("Destination kind must be local or online")
            cost = dest.request_cost_cents
            if cost is not None and (type(cost) is not int or cost < 0):
                raise ValueError("request_cost_cents must be a non-negative integer")
            if type(dest.fallback_authorized) is not bool:
                raise ValueError("fallback_authorized must be a boolean")
            parsed.append(dest)
        if len({d.id for d in parsed}) != len(parsed):
            raise ValueError("Destination ids must be unique")
        with self._lock:
            if len(self._workflows) >= MAX_WORKFLOWS:
                raise WorkflowConflict("Workflow limit reached for this app run")
            workflow_id = uuid4().hex
            self._workflows[workflow_id] = {
                "id": workflow_id, "title": title, "task_id": task_id,
                "owner_id": owner_id, "created_at": self._now(),
                "destinations": tuple(parsed), "preference": preference,
                "max_depth": max_depth, "max_children": max_children,
                "spend_ceiling_cents": spend_ceiling_cents,
                "fallback_enabled": fallback_enabled,
                "paused": False, "spent_cents": 0, "items": {}, "events": [],
            }
            self._event(workflow_id, "created", None)
            return self.report(workflow_id)

    def _get(self, workflow_id):
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            raise WorkflowNotFound("Workflow not found")
        return workflow

    def _item(self, workflow, item_id):
        item = workflow["items"].get(item_id)
        if item is None:
            raise WorkflowNotFound("Work item not found")
        return item

    def _event(self, workflow_id, kind, item_id, detail=""):
        self._workflows[workflow_id]["events"].append(
            {"at": self._now(), "kind": kind, "item_id": item_id, "detail": detail}
        )

    def add_item(self, workflow_id, *, role, agent_id, prompt, parent_id=None, source_id=None):
        if role not in ROLES:
            raise ValueError("Unsupported work item role")
        agent_id = _text(agent_id, "agent_id", 256)
        prompt = _text(prompt, "prompt", MAX_PROMPT_BYTES)
        with self._lock:
            workflow = self._get(workflow_id)
            items = workflow["items"]
            depth = 1
            if parent_id is not None:
                depth = self._item(workflow, parent_id)["depth"] + 1
            if depth > workflow["max_depth"]:
                raise WorkflowConflict("Delegation depth limit reached")
            children = sum(1 for i in items.values() if i["parent_id"] is not None)
            if parent_id is not None and children >= workflow["max_children"]:
                raise WorkflowConflict("Delegated work item limit reached")
            if source_id is not None:
                self._item(workflow, source_id)
            item_id = uuid4().hex
            items[item_id] = {
                "id": item_id, "role": role, "agent_id": agent_id, "prompt": prompt,
                "parent_id": parent_id, "source_id": source_id, "depth": depth,
                "state": "waiting", "attempts": 0, "destination_id": None,
                "output": None, "reason": "", "review": None, "approval": None,
            }
            self._event(workflow_id, "item_added", item_id, role)
            return dict(items[item_id])

    def _ordered(self, workflow, item):
        first = "local" if workflow["preference"] == "local_first" else "online"
        eligible = [d for d in workflow["destinations"] if d.agent_id == item["agent_id"]]
        return sorted(eligible, key=lambda d: d.kind != first)

    def _block(self, workflow, item, reason):
        item["state"] = "blocked"
        item["reason"] = reason
        self._event(workflow["id"], "blocked", item["id"], reason)
        return dict(item)

    def _admit(self, workflow, dest, consents):
        """Return a blocking reason, or None when the destination may be called."""
        if dest.kind != "online":
            return None
        if dest.id not in consents:
            return "Per-turn cloud-data consent is required for this destination"
        ceiling = workflow["spend_ceiling_cents"]
        if ceiling is None or dest.request_cost_cents is None:
            return "UNKNOWN spend: an owner spend ceiling and request cost are required"
        if workflow["spent_cents"] + dest.request_cost_cents > ceiling:
            return "Workflow spend ceiling would be exceeded"
        return None

    def run(self, workflow_id, item_id, *, confirmed, cloud_consent_destinations=()):
        if confirmed is not True:
            raise WorkflowConflict("Explicit owner confirmation is required")
        consents = frozenset(cloud_consent_destinations)
        with self._lock:
            workflow = self._get(workflow_id)
            item = self._item(workflow, item_id)
            if workflow["paused"]:
                raise WorkflowConflict("Workflow is paused")
            if item["state"] != "waiting":
                raise WorkflowConflict("Only waiting work items can run")
            if item["role"] == "reviewer":
                raise WorkflowConflict("Reviewers submit reviews instead of running")
            ordered = self._ordered(workflow, item)
            if not ordered:
                return self._block(workflow, item, "No destination is configured for this Agent")
            primary = ordered[0]
            reason = self._admit(workflow, primary, consents)
            if reason:
                return self._block(workflow, item, reason)
            item["state"] = "running"
            item["destination_id"] = primary.id
            if primary.kind == "online":
                workflow["spent_cents"] += primary.request_cost_cents
            self._event(workflow_id, "started", item_id, primary.id)
            prompt = item["prompt"]
        return self._execute(workflow_id, item_id, primary, prompt, consents)

    def _execute(self, workflow_id, item_id, dest, prompt, consents):
        retried = False
        fell_back = False
        while True:
            with self._lock:
                workflow = self._get(workflow_id)
                item = self._item(workflow, item_id)
                item["attempts"] += 1
            try:
                output = self._runner(dest, prompt)
            except ProviderCapacityError as error:
                with self._lock:
                    self._refund(workflow, dest)
                    candidate = self._fallback(workflow, item, dest, consents)
                    if candidate is None or fell_back:
                        return self._block(
                            workflow, item,
                            f"Capacity or quota rejected the request without sending it: {error}",
                        )
                    fell_back = True
                    dest = candidate
                    item["destination_id"] = dest.id
                    if dest.kind == "online":
                        workflow["spent_cents"] += dest.request_cost_cents
                    self._event(workflow_id, "fallback", item_id, dest.id)
                continue
            except WorkNotStarted as error:
                with self._lock:
                    if retried:
                        self._refund(workflow, dest)
                        return self._fail(workflow, item, f"Retry did not start: {error}")
                    retried = True
                    self._event(workflow_id, "retry", item_id, "provider confirmed not started")
                continue
            except Exception:
                with self._lock:
                    return self._fail(
                        workflow, item, "Outcome is uncertain; inspect before retrying", uncertain=True
                    )
            with self._lock:
                if item["state"] != "running":
                    return dict(item)
                item["output"] = str(output)[:MAX_OUTPUT_CHARS]
                item["state"] = "review"
                item["reason"] = "Awaiting a different Agent's review"
                self._event(workflow_id, "completed", item_id, dest.id)
                return dict(item)

    def _refund(self, workflow, dest):
        if dest.kind == "online":
            workflow["spent_cents"] -= dest.request_cost_cents

    def _fallback(self, workflow, item, failed, consents):
        if not workflow["fallback_enabled"]:
            return None
        for dest in workflow["destinations"]:
            if (dest.id != failed.id and dest.agent_id == item["agent_id"]
                    and dest.fallback_authorized
                    and self._admit(workflow, dest, consents) is None):
                return dest
        return None

    def _fail(self, workflow, item, reason, uncertain=False):
        item["state"] = "failed"
        item["reason"] = reason
        item["uncertain"] = uncertain
        self._event(workflow["id"], "failed", item["id"], reason)
        return dict(item)

    def review(self, workflow_id, item_id, *, reviewer_agent_id, passed, evidence):
        reviewer_agent_id = _text(reviewer_agent_id, "reviewer_agent_id", 256)
        evidence = _text(evidence, "evidence", 2048)
        if type(passed) is not bool:
            raise ValueError("passed must be a boolean")
        with self._lock:
            workflow = self._get(workflow_id)
            item = self._item(workflow, item_id)
            if item["state"] != "review":
                raise WorkflowConflict("Only work awaiting review can be reviewed")
            if reviewer_agent_id == item["agent_id"]:
                raise WorkflowConflict("A reviewer must be a different Agent from the worker")
            item["review"] = {
                "reviewer_agent_id": reviewer_agent_id, "passed": passed,
                "evidence": evidence, "at": self._now(),
            }
            item["state"] = "reviewed" if passed else "failed"
            item["reason"] = (
                "Review passed; owner approval is still required" if passed
                else "Review rejected the work"
            )
            self._event(workflow_id, "reviewed", item_id, "passed" if passed else "rejected")
            return dict(item)

    def approve(self, workflow_id, item_id, owner_id, *, confirmed, verification_evidence):
        if confirmed is not True:
            raise WorkflowConflict("Explicit owner confirmation is required")
        evidence = _text(verification_evidence, "verification_evidence", 2048)
        with self._lock:
            workflow = self._get(workflow_id)
            item = self._item(workflow, item_id)
            if item["state"] != "reviewed":
                raise WorkflowConflict("Owner approval requires a passed review")
            item["approval"] = {"owner_id": owner_id, "evidence": evidence, "at": self._now()}
            item["state"] = "approved"
            item["reason"] = "Owner approved with verification evidence"
            self._event(workflow_id, "approved", item_id)
            return dict(item)

    def pause(self, workflow_id):
        with self._lock:
            self._get(workflow_id)["paused"] = True
            self._event(workflow_id, "paused", None, "running provider calls are not interrupted")
            return self.report(workflow_id)

    def resume(self, workflow_id):
        with self._lock:
            workflow = self._get(workflow_id)
            if any(i["state"] == "interrupted" for i in workflow["items"].values()):
                raise WorkflowConflict("Interrupted work requires explicit recovery first")
            workflow["paused"] = False
            self._event(workflow_id, "resumed", None)
            return self.report(workflow_id)

    def cancel(self, workflow_id):
        with self._lock:
            self._get(workflow_id)
        raise WorkflowConflict(
            "Cancellation is unsupported: started provider calls cannot be withdrawn"
        )

    def mark_interrupted(self, workflow_id):
        """Mark running work as interrupted (for example at shutdown); outcome unknown."""
        with self._lock:
            workflow = self._get(workflow_id)
            workflow["paused"] = True
            for item in workflow["items"].values():
                if item["state"] == "running":
                    item["state"] = "interrupted"
                    item["reason"] = "Interrupted; the provider outcome is unknown"
                    self._event(workflow_id, "interrupted", item["id"])
            return self.report(workflow_id)

    def recover(self, workflow_id, item_id, *, confirmed):
        if confirmed is not True:
            raise WorkflowConflict("Explicit owner confirmation is required")
        with self._lock:
            workflow = self._get(workflow_id)
            item = self._item(workflow, item_id)
            if item["state"] not in {"interrupted", "failed", "blocked"}:
                raise WorkflowConflict("Only interrupted, failed or blocked work can be requeued")
            item.update(state="waiting", reason="Requeued by owner", output=None,
                        review=None, attempts=0)
            self._event(workflow_id, "recovered", item_id)
            return dict(item)

    def report(self, workflow_id):
        with self._lock:
            workflow = self._get(workflow_id)
            items = [dict(i) for i in workflow["items"].values()]
            states = {i["state"] for i in items}
            for state in ("running", "interrupted", "failed", "blocked", "review", "reviewed", "waiting"):
                if state in states:
                    derived = state
                    break
            else:
                derived = "approved" if items else "waiting"
            if workflow["paused"] and derived in {"waiting", "reviewed"}:
                derived = "paused"
            return {
                "id": workflow["id"], "title": workflow["title"], "task_id": workflow["task_id"],
                "state": derived, "paused": workflow["paused"],
                "preference": workflow["preference"],
                "fallback_enabled": workflow["fallback_enabled"],
                "spend_ceiling_cents": workflow["spend_ceiling_cents"],
                "spent_cents": workflow["spent_cents"],
                "owner_approved": bool(items) and all(i["state"] == "approved" for i in items),
                "cancellation": "unsupported",
                "items": items,
                "handoffs": [
                    {"from": i["source_id"], "to": i["id"]} for i in items if i["source_id"]
                ],
                "events": list(workflow["events"]),
            }

    def list(self):
        with self._lock:
            return [self.report(key) for key in self._workflows]
