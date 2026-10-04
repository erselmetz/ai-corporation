from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.local import create_local_app
from app.runtime.factory import create_corporation_runtime

PASSWORD = "assignment-policy-test-password"
ORIGIN = "http://127.0.0.1:8000"


def test_policy_api_is_local_owner_protected_and_never_changes_assignment():
    runtime = create_corporation_runtime()
    assignments_before = tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    )
    app = create_local_app(
        password=PASSWORD,
        origin=ORIGIN,
        application_service=runtime.application_service,
    )
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        assert client.get("/api/local/assignment-policy").status_code == 401
        assert client.post("/api/local/login", json={"password": PASSWORD},
                           headers={"Origin": ORIGIN}).status_code == 200
        session = client.get("/api/local/session").json()
        assert {
            "assignment-policy:read",
            "assignment-policy:manage",
        }.issubset(session["permissions"])
        assert client.get("/api/local/assignment-policy").json()["enabled"] is False

        capabilities = runtime.application_service.get_agent("local_worker").capabilities
        now = datetime.now(timezone.utc).isoformat()
        policy = {
            "enabled": True,
            "allowed_provider_ids": ["ollama"],
            "online_enabled": False,
            "budget_limit": "1",
            "budget_unit": "owner units per request",
            "candidates": [{
                "provider_id": "ollama",
                "model_id": "llama3.2:3b",
                "inventory_kind": "local",
                "inventory_models": ["llama3.2:3b"],
                "inventory_reference": "owner-refreshed-local-inventory",
                "inventory_observed_at": now,
                "estimated_cost": "0",
                "evidence": [{
                    "capability": capability,
                    "kind": "tested",
                    "supports": True,
                    "reference": f"test-report-{capability}",
                    "observed_at": now,
                } for capability in capabilities],
            }],
        }
        token = "AIza" + "A" * 35
        credential_policy = {
            **policy,
            "candidates": [{
                **policy["candidates"][0],
                "inventory_reference": token,
            }],
        }
        rejected_secret = client.put(
            "/api/local/assignment-policy",
            json=credential_policy,
            headers={"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]},
        )
        assert rejected_secret.status_code == 422
        assert token not in rejected_secret.text
        assert client.get("/api/local/assignment-policy").json()["enabled"] is False
        no_csrf = client.put("/api/local/assignment-policy", json=policy,
                             headers={"Origin": ORIGIN})
        assert no_csrf.status_code == 403
        saved = client.put(
            "/api/local/assignment-policy",
            json=policy,
            headers={"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]},
        )
        assert saved.status_code == 200
        assert saved.json()["enabled"] is True
        preview = client.get("/api/local/assignment-policy/preview")
        assert preview.status_code == 200
        assert preview.json()["enabled"] is True
        candidate = preview.json()["assignments"][0]["candidates"][0]
        assert candidate["eligible"] is False
        assert "capacity_not_eligible" in candidate["reasons"]
        assert preview.json()["assignments"][0]["recommendation"] is None
        disabled = client.request(
            "DELETE",
            "/api/local/assignment-policy",
            json={},
            headers={"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]},
        )
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False
        assert disabled.json()["candidates"] == []
        assert client.get("/api/local/assignment-policy/preview").json()["assignments"] == []

    assert tuple((agent.id, agent.provider, agent.model) for agent in runtime.agents.all()) == assignments_before


def test_assignment_policy_routes_remain_default_deny():
    runtime = create_corporation_runtime()
    from app.api.app import create_app

    with TestClient(create_app(application_service=runtime.application_service)) as client:
        assert client.get("/api/local/assignment-policy").status_code == 404
        page = client.get("/ui/assignment-policy")
        script = client.get("/ui/static/assignment-policy.mjs")
        assert page.status_code == 200
        assert "Owner-approved policy JSON" in page.text
        assert "The example is not evidence" in page.text
        assert script.status_code == 200
        assert script.headers["content-type"].startswith("text/javascript")


def test_policy_owner_limit_is_per_authenticated_identity():
    from app.application.services.assignment_policy import AssignmentPolicyService

    runtime = create_corporation_runtime()
    service = AssignmentPolicyService(runtime.application_service)
    for owner in range(service.MAX_OWNERS):
        service.configure(str(owner), service.get(str(owner)))
    try:
        service.configure("overflow", service.get("overflow"))
    except ValueError as error:
        assert "owner limit" in str(error)
    else:
        raise AssertionError("expected bounded owner policy storage")
