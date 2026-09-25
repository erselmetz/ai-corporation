import pytest
from app.agents import Employee, EmployeeRegistry, EmployeeManagement, Agent, AgentRegistry

class TestEmployeeManagement:
    @pytest.fixture
    def setup(self):
        registry = EmployeeRegistry()
        mgmt = EmployeeManagement(registry)
        agent_reg = AgentRegistry()
        return registry, mgmt, agent_reg

    def test_create_employee(self, setup):
        registry, mgmt, _ = setup
        emp = mgmt.create_employee("researcher", "AI Researcher", "researcher", ["Research AI technologies"])
        assert emp.id == "researcher"
        assert emp.name == "AI Researcher"
        assert registry.exists("researcher")

    def test_get_employee(self, setup):
        registry, mgmt, _ = setup
        mgmt.create_employee("dev", "Developer", "developer", ["Code things"])
        emp = mgmt.get_employee("dev")
        assert emp.name == "Developer"

    def test_list_employees(self, setup):
        registry, mgmt, _ = setup
        mgmt.create_employee("e1", "Emp 1", "role1", ["r1"])
        mgmt.create_employee("e2", "Emp 2", "role2", ["r2"])
        employees = mgmt.list_employees()
        assert len(employees) == 2

    def test_remove_employee(self, setup):
        registry, mgmt, _ = setup
        mgmt.create_employee("e1", "Emp 1", "role1", ["r1"])
        mgmt.remove_employee("e1")
        assert not registry.exists("e1")

    def test_duplicate_employee_rejection(self, setup):
        registry, mgmt, _ = setup
        mgmt.create_employee("e1", "Emp 1", "role1", ["r1"])
        with pytest.raises(ValueError, match="Employee already registered"):
            mgmt.create_employee("e1", "Emp 1 Duplicate", "role1", ["r1"])

    def test_missing_employee_handling(self, setup):
        registry, mgmt, _ = setup
        with pytest.raises(ValueError, match="Employee not found"):
            mgmt.get_employee("none")

    def test_invalid_employee_validation(self, setup):
        registry, mgmt, _ = setup
        with pytest.raises(ValueError, match="Employee id cannot be empty"):
            mgmt.create_employee("", "Name", "Role", ["Resp"])
        with pytest.raises(ValueError, match="Employee name cannot be empty"):
            mgmt.create_employee("id", "", "Role", ["Resp"])
        with pytest.raises(ValueError, match="Employee role cannot be empty"):
            mgmt.create_employee("id", "Name", "", ["Resp"])
        with pytest.raises(ValueError, match="All responsibilities must be non-empty strings"):
            mgmt.create_employee("id", "Name", "Role", ["", "  "])

    def test_employee_without_agent(self, setup):
        registry, mgmt, _ = setup
        emp = mgmt.create_employee("e1", "Emp 1", "role1", ["r1"])
        assert emp.agent is None

    def test_employee_with_agent(self, setup):
        registry, mgmt, agent_reg = setup
        agent = Agent(id="a1", name="Agent 1", role="role1", provider="ollama", model="llama3")
        agent_reg.register(agent)
        emp = mgmt.create_employee("e1", "Emp 1", "role1", ["r1"])
        emp.assign_agent(agent)
        assert emp.agent == agent

    def test_removing_employee_does_not_delete_agent(self, setup):
        registry, mgmt, agent_reg = setup
        agent = Agent(id="a1", name="Agent 1", role="role1", provider="ollama", model="llama3")
        agent_reg.register(agent)
        emp = mgmt.create_employee("e1", "Emp 1", "role1", ["r1"])
        emp.assign_agent(agent)
        
        mgmt.remove_employee("e1")
        assert agent_reg.exists("a1")
