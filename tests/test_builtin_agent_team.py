import pytest

from app.agents import Agent
from app.agents.builtins import (
    BUILTIN_AGENT_PROFILES, profile_for, provision_builtin_agent_team,
    upgrade_unchanged_builtin_default,
)
from app.application.services.owned_chat import ChatConflict, ChatLimit
from app.runtime import create_corporation_runtime


def test_runtime_provisions_builtin_agents_and_linked_employees_idempotently():
    runtime = create_corporation_runtime(with_builtin_agent_team=True)
    agents = runtime.agents.all()
    employees = runtime.employees.all()
    assert len(agents) == len(BUILTIN_AGENT_PROFILES) == 6
    assert len(employees) == 6
    assert {agent.name for agent in agents} == {
        "Coordinator", "Researcher", "Developer", "Librarian", "Observer", "Operator"
    }
    assert all(employee.agent is not None for employee in employees)
    assert all(agent.brain_scopes or agent.builtin_key in {"observer", "operator"} for agent in agents)
    operator = runtime.agents.get("operator")
    assert operator.paused is True
    with pytest.raises(RuntimeError, match="paused"):
        with runtime.agents.execution(operator.id):
            pass
    researcher = runtime.agents.get("researcher")
    researcher.system_prompt = "Owner edit retained"
    again = provision_builtin_agent_team(runtime.agents, runtime.employees)
    assert len(again) == 6
    assert runtime.agents.get("researcher").system_prompt == "Owner edit retained"
    assert len(runtime.agents.all()) == 6


def test_developer_prefers_an_already_installed_coder_model_only():
    runtime = create_corporation_runtime(with_builtin_agent_team=True)
    provision_builtin_agent_team(runtime.agents, runtime.employees,
                                 installed_models=("llama3.2:3b", "qwen2.5-coder:3b"))
    developer = runtime.agents.get("developer")
    assert developer.model == "qwen2.5-coder:3b"
    assert developer.provider == "ollama"
    assert developer.model_route_preference == "installed-coder"


def test_legacy_coordinator_default_gains_new_tools_but_owner_edit_is_preserved():
    runtime = create_corporation_runtime(with_builtin_agent_team=True)
    coordinator = runtime.agents.get("local_worker")
    coordinator.allowed_tools = ["brain.search", "reviewed.calculator", "reviewed.local-document-lookup"]
    coordinator.capabilities = ["chat", *coordinator.allowed_tools]

    assert upgrade_unchanged_builtin_default(coordinator, profile_for("coordinator")) is True
    assert "native.open_url" in coordinator.allowed_tools
    assert "native.create_folder" in coordinator.allowed_tools

    coordinator.allowed_tools.remove("native.open_url")
    assert upgrade_unchanged_builtin_default(coordinator, profile_for("coordinator")) is False
    assert "native.open_url" not in coordinator.allowed_tools

    coordinator.allowed_tools = [
        "brain.search", "reviewed.calculator", "reviewed.local-document-lookup", "native.open_url",
    ]
    coordinator.capabilities = ["chat", *coordinator.allowed_tools]
    assert upgrade_unchanged_builtin_default(coordinator, profile_for("coordinator")) is True
    assert coordinator.allowed_tools[-1] == "native.create_folder"


def test_owned_agent_chat_uses_one_shared_resource_manager_slot():
    runtime = create_corporation_runtime(with_builtin_agent_team=True)
    application = runtime.application_service
    application.configure_agent_slots(global_slots=1)
    with application.owned_chat_agent_execution("researcher"):
        assert application.resource_manager().snapshot().global_capacity.allocated == 1
        with pytest.raises(ChatLimit, match="request-slot capacity is exhausted"):
            with application.owned_chat_agent_execution("developer"):
                pass
    snapshot = application.resource_manager().snapshot()
    assert snapshot.global_capacity.allocated == 0
    assert len(snapshot.allocations) == 0


def test_new_assigned_model_route_uses_shared_slot_without_resetting_id_history():
    runtime = create_corporation_runtime(with_builtin_agent_team=True)
    application = runtime.application_service
    manager = application.configure_agent_slots(global_slots=1)
    manager.allocate("history-before-route", provider_id="ollama", model_id="llama3.2:3b")
    manager.release("history-before-route")
    application.assign_model("researcher", "ollama", "qwen2.5:3b")

    with application.owned_chat_agent_execution("researcher"):
        snapshot = manager.snapshot()
        assert snapshot.global_capacity.allocated == 1
        assert any((provider, model) == ("ollama", "qwen2.5:3b")
                   for provider, model, _capacity in snapshot.models)
        assert snapshot.allocation_id_history_capacity.allocated == 2
    assert manager.snapshot().global_capacity.allocated == 0


def test_profile_persists_for_existing_agent_without_employee_link():
    runtime = create_corporation_runtime(with_builtin_agent_team=True)
    agent = Agent("custom_unlinked", "Specialist", "Specialist", "ollama", "llama3.2:3b")
    runtime.agents.register(agent)
    runtime.application_service.update_agent_profile(
        agent.id, name=agent.name, role=agent.role, system_prompt="Use the approved scope.",
        brain_scopes=["owner"], allowed_tools=["brain.search"], permissions=["brain:read"],
    )

    restarted = create_corporation_runtime(with_builtin_agent_team=True)
    assert restarted.agents.get(agent.id).system_prompt == "Use the approved scope."
    assert restarted.application_service.get_agent_profile(agent.id).brain_scopes == ("owner",)


def test_restart_upgrades_and_persists_exact_legacy_coordinator_default():
    runtime = create_corporation_runtime(with_builtin_agent_team=True)
    coordinator = runtime.agents.get("local_worker")
    legacy = ["brain.search", "reviewed.calculator", "reviewed.local-document-lookup"]
    coordinator.capabilities = ["chat", *legacy]
    runtime.application_service.update_agent_profile(
        coordinator.id, name=coordinator.name, role=coordinator.role,
        system_prompt=coordinator.system_prompt, brain_scopes=["owner"],
        allowed_tools=legacy, permissions=list(coordinator.permissions),
    )

    restarted = create_corporation_runtime(with_builtin_agent_team=True)
    restored = restarted.agents.get("local_worker")
    assert restored.allowed_tools[-2:] == ["native.open_url", "native.create_folder"]

    restarted_again = create_corporation_runtime(with_builtin_agent_team=True)
    assert restarted_again.agents.get("local_worker").allowed_tools == restored.allowed_tools
