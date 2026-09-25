from app.agents import Employee, Agent, AgentRegistry, EmployeeRegistry
from app.providers import OllamaProvider, ProviderRegistry

def test_employee_registry_basic():
    registry = EmployeeRegistry()
    agent = Agent(id="a1", name="Agent 1", role="Executor", provider="ollama", model="m1")
    
    emp = Employee(id="emp_1", name="Employee 1", role="Developer", agent=agent)
    registry.register(emp)
    
    assert registry.exists("emp_1")
    assert registry.get("emp_1") == emp
    assert len(registry.all()) == 1

def test_employee_registry_duplicates():
    registry = EmployeeRegistry()
    agent = Agent(id="a1", name="Agent 1", role="Executor", provider="ollama", model="m1")
    emp = Employee(id="emp_1", name="Employee 1", role="Developer", agent=agent)
    
    registry.register(emp)
    try:
        registry.register(emp)
        raise AssertionError("Should have raised ValueError for duplicate registration")
    except ValueError as e:
        assert "Employee already registered: emp_1" in str(e)

def test_employee_registry_invalid_type():
    registry = EmployeeRegistry()
    try:
        registry.register("not an employee")
        raise AssertionError("Should have raised TypeError")
    except TypeError as e:
        assert "Only Employee instances can be registered" in str(e)

def test_employee_find_by_role():
    registry = EmployeeRegistry()
    agent = Agent(id="a1", name="Agent 1", role="Executor", provider="ollama", model="m1")
    
    emp1 = Employee(id="emp_1", name="Employee 1", role="Developer", agent=agent)
    emp2 = Employee(id="emp_2", name="Employee 2", role="Developer", agent=agent)
    emp3 = Employee(id="emp_3", name="Employee 3", role="Architect", agent=agent)
    
    registry.register(emp1)
    registry.register(emp2)
    registry.register(emp3)
    
    devs = registry.find_by_role("Developer")
    assert len(devs) == 2
    assert emp1 in devs
    assert emp2 in devs
    assert emp3 not in devs

def test_employee_agent_relationship():
    # Verify different employees can use different agents
    registry = EmployeeRegistry()
    
    agent1 = Agent(id="a1", name="Agent 1", role="Executor", provider="ollama", model="m1")
    agent2 = Agent(id="a2", name="Agent 2", role="Executor", provider="ollama", model="m2")
    
    emp1 = Employee(id="emp_1", name="Employee 1", role="Dev", agent=agent1)
    emp2 = Employee(id="emp_2", name="Employee 2", role="Dev", agent=agent2)
    
    registry.register(emp1)
    registry.register(emp2)
    
    assert registry.get("emp_1").agent == agent1
    assert registry.get("emp_2").agent == agent2

if __name__ == "__main__":
    try:
        test_employee_registry_basic()
        test_employee_registry_duplicates()
        test_employee_registry_invalid_type()
        test_employee_find_by_role()
        test_employee_agent_relationship()
        print("Employee Registry tests passed!")
    except Exception as e:
        print(f"Employee Registry tests failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
