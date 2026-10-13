"""Read-only corporation structure map built from existing authorized records."""

from datetime import datetime, timezone

SECTIONS = {
    "positions": "position:read",
    "employees": "employee:read",
    "agents": "agent:read",
    "models": "model:read",
    "providers": "provider:read",
}


def build_structure_map(application, permissions, *, now=None):
    """Return positions with explicit assignment states; never invent relationships.

    Sections the caller may not read are reported as forbidden rather than omitted.
    """
    allowed = {name: perm in permissions for name, perm in SECTIONS.items()}
    if not allowed["positions"]:
        raise PermissionError("position:read is required")
    employees = {e.id: e for e in application.list_employees()} if allowed["employees"] else None
    agents = {a.id: a for a in application.list_agents()} if allowed["agents"] else None
    models = {m.agent_id: m for m in application.list_models()} if allowed["models"] else None
    positions = application.list_positions()
    known = {p.id for p in positions}
    nodes = []
    for position in positions:
        parent = position.reports_to_position_id
        if parent is None:
            parent_state = "root"
        elif parent in known:
            parent_state = "linked"
        else:
            parent_state = "missing"
        employee = _employee_state(position.employee_id, employees)
        agent = _agent_state(employee, employees, agents)
        model = _model_state(application, employee, employees, agents, models, allowed["providers"])
        nodes.append({
            "id": position.id,
            "title": position.title,
            "responsibilities": list(position.responsibilities),
            "active": position.active,
            "revision": position.revision,
            "reports_to_position_id": parent,
            "reporting_state": parent_state,
            "employee": employee,
            "agent": agent,
            "model": model,
        })
    return {
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "sections": {name: "available" if ok else "forbidden" for name, ok in allowed.items()},
        "positions": nodes,
        "roots": [n["id"] for n in nodes if n["reporting_state"] != "linked"],
    }


def _employee_state(employee_id, employees):
    if employee_id is None:
        return {"state": "unassigned"}
    if employees is None:
        return {"state": "forbidden", "id": employee_id}
    employee = employees.get(employee_id)
    if employee is None:
        return {"state": "missing", "id": employee_id}
    return {"state": "assigned", "id": employee.id, "name": employee.name, "role": employee.role}


def _agent_state(employee, employees, agents):
    if employee["state"] in {"unassigned", "missing"}:
        return {"state": "not_applicable"}
    if employee["state"] == "forbidden":
        return {"state": "forbidden"}
    agent_id = employees[employee["id"]].agent_id
    if agent_id is None:
        return {"state": "unassigned"}
    if agents is None:
        return {"state": "forbidden", "id": agent_id}
    agent = agents.get(agent_id)
    if agent is None:
        return {"state": "missing", "id": agent_id}
    return {"state": "assigned", "id": agent.id, "name": agent.name}


def _model_state(application, employee, employees, agents, models, can_read_providers):
    if employee["state"] in {"unassigned", "missing"}:
        return {"state": "not_applicable"}
    if employee["state"] == "forbidden" or agents is None or models is None:
        return {"state": "forbidden"}
    agent_id = employees[employee["id"]].agent_id
    if agent_id is None:
        return {"state": "not_applicable"}
    agent = agents.get(agent_id)
    if agent is None:
        return {"state": "missing"}
    assignment = models.get(agent.id)
    if assignment is None:
        return {"state": "missing"}
    return {
        "state": "assigned",
        "provider_id": assignment.provider_id,
        "model_id": assignment.model_id,
        "provider_state": (
            ("registered" if application.provider_exists(assignment.provider_id) else "unavailable")
            if can_read_providers else "forbidden"
        ),
    }
