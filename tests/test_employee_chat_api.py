import json
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.agents import Agent, Employee
from app.api import AuthenticatedPrincipal, create_app
from app.providers import AIProvider
from app.runtime.factory import create_corporation_runtime


class Provider(AIProvider):
    def __init__(self):
        self.calls = []
        self.reply = "deterministic reply"

    def generate(self, model, prompt):
        self.calls.append((model, prompt))
        return self.reply


class Authentication:
    def authenticate(self, request: Request):
        owner = request.headers.get("x-test-owner")
        if owner is None:
            return None
        permissions = {
            "employee:read",
            "employee-chat:read",
            "employee-chat:start",
            "employee-chat:send",
            "employee-chat:close",
        }
        if owner == "reader":
            permissions = {"employee-chat:read"}
        return AuthenticatedPrincipal(owner, frozenset(permissions))


@pytest.fixture
def setup():
    runtime = create_corporation_runtime()
    provider = Provider()
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", provider)
    runtime.employees.register(Employee("unassigned", "Unassigned", "Worker"))
    runtime.employees.register(Employee("private-employee", "Private Name", "Private Role",
                                        responsibilities=["private responsibility"],
                                        agent=runtime.agents.get("local_worker")))
    application = create_app(runtime.application_service, Authentication())
    with TestClient(application) as client:
        yield runtime, provider, client


def headers(owner="alice"):
    return {"x-test-owner": owner}


def test_employee_chat_is_owned_isolated_and_does_not_send_profile_or_task_context(setup):
    runtime, provider, client = setup
    first = client.post("/api/employee-chat/conversations",
                        json={"employee_id": "private-employee"}, headers=headers())
    second = client.post("/api/employee-chat/conversations",
                         json={"employee_id": "local_employee"}, headers=headers())
    assert first.status_code == 201
    assert second.status_code == 201
    first_body, second_body = first.json(), second.json()
    assert first_body["employee"] == {
        "id": "private-employee", "name": "Private Name", "role": "Private Role"
    }
    assert first_body["agent"]["id"] == "local_worker"

    path = f"/api/employee-chat/conversations/{first_body['conversation']['id']}"
    response = client.post(path + "/messages", json={"text": "private question"},
                           headers=headers())
    assert response.status_code == 200
    prompt = json.loads(provider.calls[0][1])
    assert prompt == {"history": [], "request": "private question"}
    assert "Private Name" not in provider.calls[0][1]
    assert "private responsibility" not in provider.calls[0][1]
    assert runtime.application_service.list_tasks() == []

    other_path = f"/api/employee-chat/conversations/{second_body['conversation']['id']}"
    second_response = client.post(other_path + "/messages",
                                  json={"text": "separate question"}, headers=headers())
    assert second_response.status_code == 200
    second_prompt = json.loads(provider.calls[1][1])
    assert second_prompt == {"history": [], "request": "separate question"}
    assert client.get(path, headers=headers("bob")).status_code == 404
    assert client.get("/api/employee-chat/conversations", headers=headers("bob")).json() == {"items": []}
    assert client.get(path, headers=headers("reader")).status_code == 404

    listed = client.get("/api/employee-chat/conversations", headers=headers()).json()
    assert {item["conversation_id"] for item in listed["items"]} == {
        first_body["conversation"]["id"], second_body["conversation"]["id"]
    }
    assert client.post(path + "/close", headers=headers()).json()["conversation"]["status"] == "closed"
    assert client.post(path + "/messages", json={"text": "closed"}, headers=headers()).status_code == 422


def test_gemini_requires_per_turn_consent_and_rejects_key_paste_before_saving(setup):
    runtime, local_provider, client = setup
    gemini = Provider()
    runtime.providers.register("gemini", gemini)
    runtime.application_service.replace_model("local_worker", "gemini", "gemini-test")
    started = client.post("/api/employee-chat/conversations",
                          json={"employee_id": "local_employee"}, headers=headers())
    path = f"/api/employee-chat/conversations/{started.json()['conversation']['id']}"
    no_consent = client.post(path + "/messages", json={"text": "Hello"},
                             headers=headers())
    assert no_consent.status_code == 403
    key = "AIza" + "A" * 35
    pasted_key = client.post(path + "/messages", json={"text": key, "cloud_consent": True},
                             headers=headers())
    assert pasted_key.status_code == 422
    assert key not in pasted_key.text
    assert client.get(path, headers=headers()).json()["conversation"]["messages"] == []
    assert gemini.calls == []
    assert local_provider.calls == []

    accepted = client.post(path + "/messages",
                           json={"text": "Hello", "cloud_consent": True},
                           headers=headers())
    assert accepted.status_code == 200
    assert len(gemini.calls) == 1
    assert json.loads(gemini.calls[0][1]) == {"history": [], "request": "Hello"}


def test_stale_employee_assignment_and_replaced_provider_do_not_retarget(setup):
    runtime, provider, client = setup
    started = client.post("/api/employee-chat/conversations",
                          json={"employee_id": "private-employee"}, headers=headers())
    path = f"/api/employee-chat/conversations/{started.json()['conversation']['id']}"
    other_agent = Agent("other-agent", "Other", "Worker", "ollama", "other-model")
    runtime.agents.register(other_agent)
    runtime.employees.get("private-employee").assign_agent(other_agent)
    stale = client.post(path + "/messages", json={"text": "must not reroute"},
                        headers=headers())
    assert stale.status_code == 409
    assert provider.calls == []
    assert client.get(path, headers=headers()).json()["conversation"]["messages"] == []

    runtime.employees.get("private-employee").assign_agent(runtime.agents.get("local_worker"))
    started_again = client.post("/api/employee-chat/conversations",
                                json={"employee_id": "private-employee"}, headers=headers())
    second_path = f"/api/employee-chat/conversations/{started_again.json()['conversation']['id']}"
    runtime.providers.remove("ollama")
    replacement = Provider()
    runtime.providers.register("ollama", replacement)
    changed_connection = client.post(second_path + "/messages", json={"text": "no reuse"},
                                     headers=headers())
    assert changed_connection.status_code == 409
    assert provider.calls == []
    assert replacement.calls == []


def test_missing_unassigned_and_removed_provider_are_explicit(setup):
    runtime, provider, client = setup
    assert client.post("/api/employee-chat/conversations",
                       json={"employee_id": "missing"}, headers=headers()).status_code == 503
    assert client.post("/api/employee-chat/conversations",
                       json={"employee_id": "unassigned"}, headers=headers()).status_code == 503
    started = client.post("/api/employee-chat/conversations",
                          json={"employee_id": "local_employee"}, headers=headers())
    runtime.providers.remove("ollama")
    path = f"/api/employee-chat/conversations/{started.json()['conversation']['id']}"
    assert client.post(path + "/messages", json={"text": "unavailable"},
                       headers=headers()).status_code == 503
    assert provider.calls == []


def test_utf8_message_limit_is_checked_before_history_or_provider_call(setup):
    _, provider, client = setup
    started = client.post("/api/employee-chat/conversations",
                          json={"employee_id": "local_employee"}, headers=headers())
    path = f"/api/employee-chat/conversations/{started.json()['conversation']['id']}"
    response = client.post(path + "/messages", json={"text": "界" * 3000},
                           headers=headers())
    assert response.status_code == 422
    assert client.get(path, headers=headers()).json()["conversation"]["messages"] == []
    assert provider.calls == []


def test_default_api_rejects_employee_chat_and_provider_failure_is_not_retried(setup):
    runtime, provider, client = setup
    started = client.post("/api/employee-chat/conversations",
                          json={"employee_id": "local_employee"}, headers=headers())
    identifier = started.json()["conversation"]["id"]
    provider.generate = MagicMock(side_effect=RuntimeError("sensitive provider failure"))
    path = f"/api/employee-chat/conversations/{identifier}"
    response = client.post(path + "/messages", json={"text": "fail once"},
                           headers=headers())
    assert response.status_code == 502
    assert "sensitive provider failure" not in response.text
    messages = client.get(path, headers=headers()).json()["conversation"]["messages"]
    assert len(messages) == 1 and messages[0]["status"] == "failed"
    assert provider.generate.call_count == 1
    changed = runtime.application_service.replace_model(
        "local_worker", "ollama", "after-failure"
    )
    assert changed.model_id == "after-failure"
    with TestClient(create_app(application_service=runtime.application_service)) as default:
        assert default.get("/api/employee-chat/conversations").status_code == 401
