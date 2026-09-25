from app.agents import Employee, Agent

def test_employee_creation():
    # Setup technical agent
    agent = Agent(
        id="tech_agent_1",
        name="Tech Agent 1",
        role="Executor",
        provider="ollama",
        model="llama3.2:3b",
    )
    
    # Create employee
    employee = Employee(
        id="emp_1",
        name="John AI",
        role="Junior Developer",
        responsibilities=["Write code", "Fix bugs"],
        agent=agent
    )
    
    assert employee.id == "emp_1"
    assert employee.name == "John AI"
    assert employee.role == "Junior Developer"
    assert "Write code" in employee.responsibilities
    assert employee.agent == agent
    assert "Junior Developer" in employee.describe()
    assert "Tech Agent 1" in employee.describe()

def test_employee_agent_assignment():
    employee = Employee(
        id="emp_2",
        name="Jane AI",
        role="Analyst",
        responsibilities=["Analyze data"]
    )
    
    assert employee.agent is None
    
    agent = Agent(
        id="tech_agent_2",
        name="Tech Agent 2",
        role="Executor",
        provider="ollama",
        model="llama3.2:3b",
    )
    
    employee.assign_agent(agent)
    assert employee.agent == agent

def test_employee_invalid_inputs():
    # Simple verification without pytest for the minimal runner
    try:
        Employee(id="", name="Name", role="Role")
        raise AssertionError("Should have raised ValueError for empty id")
    except ValueError as e:
        assert "Employee id cannot be empty" in str(e)

    try:
        Employee(id="id", name="", role="Role")
        raise AssertionError("Should have raised ValueError for empty name")
    except ValueError as e:
        assert "Employee name cannot be empty" in str(e)

    try:
        Employee(id="id", name="Name", role="")
        raise AssertionError("Should have raised ValueError for empty role")
    except ValueError as e:
        assert "Employee role cannot be empty" in str(e)

    try:
        Employee(id="id", name="Name", role="Role", responsibilities=["", " "])
        raise AssertionError("Should have raised ValueError for empty responsibilities")
    except ValueError as e:
        assert "All responsibilities must be non-empty strings" in str(e)

if __name__ == "__main__":
    # Simple runner for non-pytest environments
    try:
        test_employee_creation()
        test_employee_agent_assignment()
        test_employee_invalid_inputs()
        print("Employee tests passed!")
    except Exception as e:
        print(f"Employee tests failed: {e}")
        exit(1)
