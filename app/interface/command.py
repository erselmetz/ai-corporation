from __future__ import annotations
import shlex
from typing import Protocol, Any


from app.orchestrator import Orchestrator, TaskRegistry, ProjectRegistry
from app.agents import AgentRegistry, EmployeeRegistry
from app.corporation import Corporation
from app.node import Node

class CorporationContext:
    """
    Holds the active runtime components for the Corporation.
    """
    def __init__(
        self, 
        corp: Corporation, 
        node: Node, 
        orchestrator: Orchestrator, 
        agent_registry: AgentRegistry, 
        employee_registry: EmployeeRegistry,
        task_registry: TaskRegistry,
        project_registry: ProjectRegistry
    ):
        self.corp = corp
        self.node = node
        self.orchestrator = orchestrator
        self.agent_registry = agent_registry
        self.employee_registry = employee_registry
        self.task_registry = task_registry
        self.project_registry = project_registry

class CommandInterface:
    """
    Interactive command interface for ERSELMETZ AI CORPORATION.
    """
    def __init__(self, context: CorporationContext):
        self.context = context
        self._running = False

    def run(self):
        """Starts the interactive command loop."""
        self._running = True
        print("\n--- ERSELMETZ AI CORPORATION Interactive Shell ---")
        print("Type 'help' for available commands.")
        
        while self._running:
            try:
                user_input = input("> ").strip()
                if not user_input:
                    continue
                
                self.handle_command(user_input)
            except (EOFError, KeyboardInterrupt):
                self.exit_shell()
            except Exception as e:
                print(f"An unexpected error occurred: {e}")

    def handle_command(self, user_input: str):
        if not user_input:
            return

        try:
            parts = shlex.split(user_input)
        except ValueError as e:
            print(f"Shell Error: {e}")
            return

        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "help":
            self._cmd_help()
        elif cmd == "status":
            self._cmd_status()
        elif cmd == "employees":
            self._cmd_employees()
        elif cmd == "employee":
            self._cmd_employee(args)
        elif cmd == "providers":
            self._cmd_providers()
        elif cmd == "provider":
            self._cmd_provider(args)
        elif cmd == "model":
            self._cmd_model(args)
        elif cmd == "agents":
            self._cmd_agents()
        elif cmd == "task":
            self._cmd_task(" ".join(args))
        elif cmd == "dry-run":
            self._cmd_dry_run(" ".join(args))
        elif cmd in ("exit", "quit"):
            self.exit_shell()
        else:
            print(f"Unknown command: {cmd}")
            print("Type 'help' for available commands.")

    def _cmd_help(self):
        print("\nAvailable commands:")
        print("  help       - Show this help message")
        print("  status     - Show Corporation runtime status")
        print("  employees  - List all registered AI Employees")
        print("  employee   - Manage AI Employees (add, list, get, remove)")
        print("  providers  - List all registered AI Providers")
        print("  provider   - Manage AI Providers (add, list, get, remove)")
        print("  model      - Manage Agent Models (set, get, replace)")
        print("  agents     - List all registered AI Agents")
        print("  task <desc>- Create a new task")
        print("  dry-run <tid>- Perform a dry-run of the specified task")
        print("  exit/quit   - Terminate the shell")



        print()

    def _cmd_status(self):
        ctx = self.context
        print("\n--- Corporation Status ---")
        print(f"Corporation: {ctx.corp.name} ({ctx.corp.id})")
        print(f"Node:        {ctx.node.name} ({ctx.node.id})")
        print(f"Orchestrator: ONLINE")
        print("--------------------------\n")

    def _cmd_employees(self):
        self._cmd_employee(["list"])

    def _cmd_employee(self, args: list[str]):
        if not args:
            print("Error: Employee command requires a sub-command. Available: add, list, get, remove")
            return

        sub_cmd = args[0].lower()
        from app.agents import EmployeeManagement
        mgmt = EmployeeManagement(self.context.employee_registry)

        try:
            if sub_cmd == "add":
                if len(args) < 5:
                    print("Error: 'employee add' requires <id> <name> <role> <responsibilities>")
                    return
                
                emp_id = args[1]
                name = args[2]
                role = args[3]
                resp = args[4:]
                emp = mgmt.create_employee(emp_id, name, role, resp)
                print(f"Employee created: {emp.name} ({emp.id})")

            elif sub_cmd == "list":
                employees = mgmt.list_employees()
                if not employees:
                    print("No employees registered.")
                    return
                
                print("\nRegistered Employees:")
                print(f"{'ID':<15} | {'Name':<20} | {'Role':<20} | {'Agent ID':<15}")
                print("-" * 70)
                for emp in employees:
                    agent_id = emp.agent.id if emp.agent else "None"
                    print(f"{emp.id:<15} | {emp.name:<20} | {emp.role:<20} | {agent_id:<15}")
                print()

            elif sub_cmd == "get":
                if len(args) < 2:
                    print("Error: 'employee get' requires <id>")
                    return
                emp = mgmt.get_employee(args[1])
                agent_id = emp.agent.id if emp.agent else "None"
                print("\nEmployee Details:")
                print(f"ID:              {emp.id}")
                print(f"Name:            {emp.name}")
                print(f"Role:            {emp.role}")
                print(f"Responsibilities: {', '.join(emp.responsibilities)}")
                print(f"Assigned Agent:   {agent_id}")
                print()

            elif sub_cmd == "remove":
                if len(args) < 2:
                    print("Error: 'employee remove' requires <id>")
                    return
                mgmt.remove_employee(args[1])
                print(f"Employee {args[1]} removed successfully.")

            else:
                print(f"Unknown employee sub-command: {sub_cmd}")
                print("Available: add, list, get, remove")

        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An error occurred managing employees: {e}")

    def _cmd_providers(self):
        self._cmd_provider(["list"])

    def _cmd_provider(self, args: list[str]):
        if not args:
            print("Error: Provider command requires a sub-command. Available: add, list, get, remove")
            return

        sub_cmd = args[0].lower()
        from app.providers import ProviderManagement
        mgmt = ProviderManagement(self.context.provider_registry)

        try:
            if sub_cmd == "add":
                if len(args) < 3:
                    print("Error: 'provider add' requires <id> <name>")
                    return
                
                p_id = args[1]
                name = args[2]
                provider = mgmt.create_provider(p_id, name)
                print(f"Provider added: {provider.__class__.__name__} ({name})")

            elif sub_cmd == "list":
                providers = mgmt.list_providers()
                if not providers:
                    print("No providers registered.")
                    return
                
                print("\nRegistered Providers:")
                print(f"{'ID':<15} | {'Type':<20}")
                print("-" * 35)
                for p_id, p in providers.items():
                    print(f"{p_id:<15} | {p.__class__.__name__:<20}")
                print()

            elif sub_cmd == "get":
                if len(args) < 2:
                    print("Error: 'provider get' requires <id>")
                    return
                provider = mgmt.get_provider(args[1])
                print(f"\nProvider: {provider.__class__.__name__} (ID: {args[1]})")
                print()

            elif sub_cmd == "remove":
                if len(args) < 2:
                    print("Error: 'provider remove' requires <id>")
                    return
                mgmt.remove_provider(args[1])
                print(f"Provider {args[1]} removed successfully.")

            else:
                print(f"Unknown provider sub-command: {sub_cmd}")
                print("Available: add, list, get, remove")

        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An error occurred managing providers: {e}")

    def _cmd_provider(self, args: list[str]):
        if not args:
            print("Error: Provider command requires a sub-command. Available: add, list, get, remove")
            return

        sub_cmd = args[0].lower()
        from app.providers import ProviderManagement
        mgmt = ProviderManagement(self.context.provider_registry)

        try:
            if sub_cmd == "add":
                if len(args) < 3:
                    print("Error: 'provider add' requires <id> <name>")
                    return
                
                p_id = args[1]
                name = args[2]
                provider = mgmt.create_provider(p_id, name)
                print(f"Provider added: {provider.__class__.__name__} ({name})")

            elif sub_cmd == "list":
                providers = mgmt.list_providers()
                if not providers:
                    print("No providers registered.")
                    return
                
                print("\nRegistered Providers:")
                print(f"{'ID':<15} | {'Type':<20}")
                print("-" * 35)
                for p_id, p in providers.items():
                    print(f"{p_id:<15} | {p.__class__.__name__:<20}")
                print()

            elif sub_cmd == "get":
                if len(args) < 2:
                    print("Error: 'provider get' requires <id>")
                    return
                provider = mgmt.get_provider(args[1])
                print(f"\nProvider: {provider.__class__.__name__} (ID: {args[1]})")
                print()

            elif sub_cmd == "remove":
                if len(args) < 2:
                    print("Error: 'provider remove' requires <id>")
                    return
                mgmt.remove_provider(args[1])
                print(f"Provider {args[1]} removed successfully.")

            else:
                print(f"Unknown provider sub-command: {sub_cmd}")
                print("Available: add, list, get, remove")

        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An error occurred managing providers: {e}")

    def _cmd_model(self, args: list[str]):
        if not args:
            print("Error: Model command requires a sub-command. Available: set, get, replace")
            return

        sub_cmd = args[0].lower()
        from app.agents import ModelManagement
        mgmt = ModelManagement(self.context.agent_registry, self.context.provider_registry)

        try:
            if sub_cmd == "set" or sub_cmd == "replace":
                if len(args) < 4:
                    print(f"Error: 'model {sub_cmd}' requires <agent_id> <provider_id> <model>")
                    return
                
                agent_id = args[1]
                provider_id = args[2]
                model_name = args[3]
                
                mgmt.assign_model(agent_id, provider_id, model_name)
                print(f"Model updated for agent {agent_id}: {provider_id}/{model_name}")

            elif sub_cmd == "get":
                if len(args) < 2:
                    print("Error: 'model get' requires <agent_id>")
                    return
                
                info = mgmt.get_model(args[1])
                print(f"\nAgent: {args[1]}")
                print(f"Provider: {info['provider']}")
                print(f"Model:    {info['model']}")
                print()

            else:
                print(f"Unknown model sub-command: {sub_cmd}")
                print("Available: set, get, replace")

        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An error occurred managing models: {e}")

    def _cmd_agents(self):
        agents = self.context.agent_registry.all()
        if not agents:
            print("No agents registered.")
            return
        
        print("\nRegistered Agents:")
        print(f"{'Name':<20} | {'Role':<20} | {'Provider':<12} | {'Model':<15}")
        print("-" * 70)
        for agent in agents:
            print(f"{agent.name:<20} | {agent.role:<20} | {agent.provider:<12} | {agent.model:<15}")
            print(f"  Capabilities: {', '.join(agent.capabilities)}")
        print()

    def _cmd_task(self, description: str):
        if not description:
            print("Error: Task description is required. Example: 'task Research Python AI'")
            return
        
        # Use the existing Orchestrator to create a task.
        # Since we don't have a specific project ID from the command, 
        # we'll use a default project if one exists, or create one.
        proj_reg = self.context.project_registry
        projects = proj_reg.all()
        project_id = projects[0].id if projects else "default_proj"
        
        if not proj_reg.exists(project_id):
            from app.orchestrator.project import Project
            proj_reg.register(Project(id=project_id, name="General", description="Default Project", status="active"))
            
        task = self.context.orchestrator.create_task(
            title=description[:50], 
            description=description, 
            project_id=project_id
        )
        print(f"Task created: {task.id} - {task.title}")

    def _cmd_dry_run(self, task_id: str):
        if not task_id:
            print("Error: Task ID is required. Example: 'dry-run TASK-123'")
            return
        
        try:
            task = self.context.task_registry.get(task_id)
            # We execute a dry-run. 
            # Since the command doesn't provide role/capability, 
            # it relies on existing task assignment or default routing.
            result = self.context.orchestrator.execute_task(task, dry_run=True)
            print(f"\n{result}")
            print()
        except Exception as e:
            print(f"Error performing dry-run: {e}")

    def exit_shell(self):
        print("Exiting Corporation Shell...")
        self._running = False
