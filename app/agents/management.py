from app.agents import Employee, EmployeeRegistry

class EmployeeManagement:
    """
    Service layer for managing AI Employees within the Corporation.
    Handles the business logic of creating, retrieving, listing, and removing employees.
    """
    def __init__(self, registry: EmployeeRegistry):
        self.registry = registry

    def create_employee(self, employee_id: str, name: str, role: str, responsibilities: list[str]) -> Employee:
        """
        Creates and registers a new AI Employee.
        """
        employee = Employee(
            id=employee_id,
            name=name,
            role=role,
            responsibilities=responsibilities
        )
        self.registry.register(employee)
        return employee

    def get_employee(self, employee_id: str) -> Employee:
        """
        Retrieves an employee by ID.
        """
        return self.registry.get(employee_id)

    def list_employees(self) -> list[Employee]:
        """
        Returns all registered employees.
        """
        return self.registry.all()

    def remove_employee(self, employee_id: str) -> None:
        """
        Removes an employee from the registry.
        The associated Agent remains registered in the AgentRegistry.
        """
        self.registry.remove(employee_id)

