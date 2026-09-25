from .employee import Employee

class EmployeeRegistry:
    """
    Registry for managing AI Employees within the Corporation.
    """
    def __init__(self):
        self._employees: dict[str, Employee] = {}

    def register(self, employee: Employee) -> None:
        """Registers an employee in the registry."""
        if not isinstance(employee, Employee):
            raise TypeError("Only Employee instances can be registered")
        
        if employee.id in self._employees:
            raise ValueError(f"Employee already registered: {employee.id}")
            
        self._employees[employee.id] = employee

    def get(self, employee_id: str) -> Employee:
        """Retrieves an employee by its ID."""
        try:
            return self._employees[employee_id]
        except KeyError:
            raise ValueError(f"Employee not found: {employee_id}")

    def exists(self, employee_id: str) -> bool:
        """Checks if an employee exists in the registry."""
        return employee_id in self._employees

    def remove(self, employee_id: str) -> None:
        """Removes an employee from the registry."""
        if not self.exists(employee_id):
            raise ValueError(f"Employee not found: {employee_id}")
        del self._employees[employee_id]

    def all(self) -> list[Employee]:
        """Returns all registered employees."""
        return list(self._employees.values())

    def find_by_role(self, role: str) -> list[Employee]:
        """Finds employees by their organizational role."""
        return [emp for emp in self._employees.values() if emp.role == role]
