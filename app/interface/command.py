from __future__ import annotations
import shlex


from app.application import CorporationApplicationService, DryRunSummary
from app.orchestrator import Orchestrator, TaskRegistry, ProjectRegistry
from app.agents import AgentRegistry, EmployeeRegistry
from app.providers import ProviderRegistry
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
        project_registry: ProjectRegistry,
        provider_registry: ProviderRegistry | None = None
    ):
        self.corp = corp
        self.node = node
        self.orchestrator = orchestrator
        self.agent_registry = agent_registry
        self.employee_registry = employee_registry
        self.task_registry = task_registry
        self.project_registry = project_registry
        self.provider_registry = provider_registry

class CommandInterface:
    """
    Interactive command interface for ERSELMETZ AI CORPORATION.
    """
    def __init__(
        self,
        context: CorporationContext,
        application_service: CorporationApplicationService | None = None,
    ):
        self.context = context
        self.application_service = application_service or CorporationApplicationService(
            context.orchestrator
        )
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
        elif cmd == "chat":
            self._cmd_chat(args)
        elif cmd == "task":
            self._cmd_task(args)
        elif cmd == "dry-run":
            self._cmd_dry_run(args)
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
        print("  task <desc> [--agent <id> | --role <role> | --capability <capability>]")
        print("             - Create a new task with optional routing")
        print("  dry-run <task_id> [--agent <id> | --role <role> | --capability <capability>]")
        print("             - Perform a dry-run of the specified task")
        print("  chat start <id> <agent> | send <id> <text> | get <id> | close <id>")
        print("  exit/quit   - Terminate the shell")
        print()

    def _cmd_chat(self, args: list[str]):
        try:
            if not args:
                raise ValueError("chat requires start, send, get, or close")
            action = args[0]
            if action == "start" and len(args) == 3:
                result = self.application_service.corporation_chat().start(args[1], args[2])
            elif action == "send" and len(args) >= 3:
                result = self.application_service.corporation_chat().send(args[1], " ".join(args[2:]))
            elif action in ("get", "close") and len(args) == 2:
                service = self.application_service.corporation_chat()
                result = service.get(args[1]) if action == "get" else service.close(args[1])
            else:
                raise ValueError("Invalid chat command arguments")
            print(f"Corporation {result.corporation_id} chat {result.id}: {result.status.value}; coordinator {result.coordinator_agent_id}")
            for message in result.messages:
                print(f"{message.role.value} [{message.status.value}]: {message.content}")
        except Exception as exc:
            print(f"Chat error: {exc}")

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
        try:
            if sub_cmd == "add":
                if len(args) < 5:
                    print("Error: 'employee add' requires <id> <name> <role> <responsibilities>")
                    return
                
                emp_id = args[1]
                name = args[2]
                role = args[3]
                resp = args[4:]
                emp = self.application_service.create_employee(
                    emp_id, name, role, resp
                )
                print(f"Employee created: {emp.name} ({emp.id})")

            elif sub_cmd == "list":
                employees = self.application_service.list_employees()
                if not employees:
                    print("No employees registered.")
                    return
                
                print("\nRegistered Employees:")
                print(f"{'ID':<15} | {'Name':<20} | {'Role':<20} | {'Agent ID':<15}")
                print("-" * 70)
                for emp in employees:
                    agent_id = emp.agent_id or "None"
                    print(f"{emp.id:<15} | {emp.name:<20} | {emp.role:<20} | {agent_id:<15}")
                print()

            elif sub_cmd == "get":
                if len(args) < 2:
                    print("Error: 'employee get' requires <id>")
                    return
                emp = self.application_service.get_employee(args[1])
                agent_id = emp.agent_id or "None"
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
                self.application_service.remove_employee(args[1])
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
        try:
            if sub_cmd == "add":
                if len(args) < 3:
                    print("Error: 'provider add' requires <id> <name>")
                    return
                
                p_id = args[1]
                name = args[2]
                provider = self.application_service.create_provider(p_id, name)
                print(f"Provider added: {provider.type_name} ({name})")

            elif sub_cmd == "list":
                providers = self.application_service.list_providers()
                if not providers:
                    print("No providers registered.")
                    return
                
                print("\nRegistered Providers:")
                print(f"{'ID':<15} | {'Type':<20}")
                print("-" * 35)
                for provider in providers:
                    print(f"{provider.id:<15} | {provider.type_name:<20}")
                print()

            elif sub_cmd == "get":
                if len(args) < 2:
                    print("Error: 'provider get' requires <id>")
                    return
                provider = self.application_service.get_provider(args[1])
                print(f"\nProvider: {provider.type_name} (ID: {args[1]})")
                print()

            elif sub_cmd == "remove":
                if len(args) < 2:
                    print("Error: 'provider remove' requires <id>")
                    return
                self.application_service.remove_provider(args[1])
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
        try:
            if sub_cmd == "set" or sub_cmd == "replace":
                if len(args) < 4:
                    print(f"Error: 'model {sub_cmd}' requires <agent_id> <provider_id> <model>")
                    return
                
                agent_id = args[1]
                provider_id = args[2]
                model_name = args[3]
                
                self.application_service.assign_model(
                    agent_id, provider_id, model_name
                )
                print(f"Model updated for agent {agent_id}: {provider_id}/{model_name}")

            elif sub_cmd == "get":
                if len(args) < 2:
                    print("Error: 'model get' requires <agent_id>")
                    return
                
                info = self.application_service.get_model(args[1])
                print(f"\nAgent: {args[1]}")
                print(f"Provider: {info.provider}")
                print(f"Model:    {info.model}")
                print()

            else:
                print(f"Unknown model sub-command: {sub_cmd}")
                print("Available: set, get, replace")

        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An error occurred managing models: {e}")

    def _cmd_agents(self):
        agents = self.application_service.list_agents()
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

    def _parse_routing_args(self, args: list[str] | str) -> tuple[list[str], dict[str, str] | None, str | None]:
        if isinstance(args, str):
            try:
                tokens = shlex.split(args)
            except ValueError as e:
                return [], None, f"Shell Error: {e}"
        else:
            tokens = list(args)

        positionals: list[str] = []
        options: dict[str, str] = {}
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in ("--agent", "--role", "--capability"):
                opt_name = token[2:]
                if i + 1 >= len(tokens) or tokens[i + 1].startswith("--"):
                    return [], None, f"Error: '{token}' requires a value."
                if opt_name in options:
                    return [], None, f"Error: Duplicate '{token}' option."
                if not tokens[i + 1].strip():
                    return [], None, f"Error: '{token}' value cannot be empty."
                options[opt_name] = tokens[i + 1]
                i += 2
            elif token.startswith("--"):
                return [], None, f"Error: Unknown option '{token}'."
            else:
                positionals.append(token)
                i += 1

        routing_opts = [k for k in ("agent", "role", "capability") if k in options]
        if len(routing_opts) > 1:
            return [], None, "Error: Routing options (--agent, --role, --capability) are mutually exclusive."

        return positionals, options, None

    def _cmd_task(self, args: list[str] | str):
        positionals, options, error = self._parse_routing_args(args)
        if error:
            print(error)
            return

        if not positionals:
            print("Error: Task description is required. Example: 'task \"Research Python AI\"'")
            return

        description = " ".join(positionals)
        agent_id = options.get("agent")
        role = options.get("role")
        capability = options.get("capability")

        try:
            task = self.application_service.create_task(
                title=description[:50],
                description=description,
                agent_id=agent_id,
                role=role,
                capability=capability,
            )
            print(f"Task created: {task.id} - {task.title}")
        except Exception as e:
            print(f"Error creating task: {e}")

    def _cmd_dry_run(self, args: list[str] | str):
        positionals, options, error = self._parse_routing_args(args)
        if error:
            print(error)
            return

        if not positionals:
            print("Error: Task ID is required. Example: 'dry-run TASK-123'")
            return

        task_id = positionals[0]
        agent_id = options.get("agent")
        role = options.get("role")
        capability = options.get("capability")

        try:
            result = self.application_service.dry_run_task(
                task_id,
                role=role,
                capability=capability,
                agent_id=agent_id,
            )
            print(f"\n{self._format_dry_run(result)}")
            print()
        except Exception as e:
            print(f"Error performing dry-run: {e}")

    @staticmethod
    def _format_dry_run(result: DryRunSummary) -> str:
        return (
            "DRY RUN RESULT\n"
            f"Task: [{result.task_id}] {result.task_title}\n"
            f"Description: {result.task_description}\n"
            f"Employee: {result.selected_employee_name or 'N/A'}\n"
            f"Agent: {result.selected_agent_name} ({result.selected_agent_role})\n"
            f"Provider: {result.provider}\n"
            f"Model: {result.model}\n"
            f"Route: {result.routing_method}\n"
            f"Status: {result.status}"
        )

    def exit_shell(self):
        print("Exiting Corporation Shell...")
        self._running = False
