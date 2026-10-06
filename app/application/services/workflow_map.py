"""Read-only workflow map: operational edges kept apart from reporting edges."""

from datetime import datetime, timezone

STALE_AFTER_SECONDS = 60
_SAFE_PREFIXES = (
    "Capacity or quota rejected the request without sending it",
    "Retry did not start",
)


def _safe_reason(reason):
    text = str(reason or "")
    for prefix in _SAFE_PREFIXES:
        if text.startswith(prefix):
            return prefix
    return text[:200]


def _node(item, can_see_agents):
    review = item.get("review")
    approval = item.get("approval")
    return {
        "id": item["id"],
        "role": item["role"],
        "state": item["state"],
        "depth": item["depth"],
        "attempts": item["attempts"],
        "agent_id": item["agent_id"] if can_see_agents else None,
        "agent_visibility": "available" if can_see_agents else "forbidden",
        "destination_id": item["destination_id"] if can_see_agents else None,
        "reason": _safe_reason(item["reason"]),
        "uncertain": bool(item.get("uncertain")),
        "output_recorded": item["output"] is not None,
        "review": None if review is None else {
            "passed": review["passed"], "evidence": review["evidence"], "at": review["at"],
        },
        "approval": None if approval is None else {
            "evidence": approval["evidence"], "at": approval["at"],
        },
    }


def build_workflow_map(application, permissions, *, now=None):
    if "workflow:read" not in permissions:
        raise PermissionError("workflow:read is required")
    can_see_agents = "agent:read" in permissions
    generated = (now or datetime.now(timezone.utc)).isoformat()
    workflows = []
    for report in application.workflow_review().list():
        nodes = [_node(item, can_see_agents) for item in report["items"]]
        edges = []
        for item in report["items"]:
            if item["parent_id"]:
                edges.append({"kind": "delegation", "from": item["parent_id"], "to": item["id"]})
            if item["source_id"]:
                edges.append({"kind": "handoff", "from": item["source_id"], "to": item["id"]})
        workflows.append({
            "id": report["id"],
            "title": report["title"],
            "state": report["state"],
            "paused": report["paused"],
            "owner_approved": report["owner_approved"],
            "nodes": nodes,
            "operational_edges": edges,
            "events": [
                {"at": e["at"], "kind": e["kind"], "item_id": e["item_id"]} for e in report["events"]
            ],
        })
    if "position:read" in permissions:
        positions = application.list_positions()
        known = {p.id for p in positions}
        organization = {
            "state": "available",
            "positions": [{"id": p.id, "title": p.title} for p in positions],
            "reporting_edges": [
                {"kind": "reporting", "from": p.id, "to": p.reports_to_position_id}
                for p in positions
                if p.reports_to_position_id in known
            ],
        }
    else:
        organization = {"state": "forbidden", "positions": [], "reporting_edges": []}
    return {
        "generated_at": generated,
        "stale_after_seconds": STALE_AFTER_SECONDS,
        "workflows": workflows,
        "organization": organization,
    }