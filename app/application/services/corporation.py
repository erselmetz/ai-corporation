from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, RLock
from typing import TYPE_CHECKING
from uuid import uuid4

from app.agents import Agent, Employee, EmployeeManagement, EmployeeRegistry, ModelManagement
from app.agents.registry import AgentAssignmentBusy
from app.agents.builtins import BUILTIN_AGENT_PROFILES
from app.corporation import Corporation
from app.node import Node
from app.orchestrator import Orchestrator, Project, Task
from app.orchestrator.dry_run import DryRunResult
from app.providers import ProviderManagement
from app.integrations import DockerSandboxBackend, SandboxImagePolicy
from app.tools import ToolRegistry
from app.positions import (
    CorporationPosition,
    PositionRegistry,
)
from app.capability_discovery import (
    CapabilityCandidate,
    CapabilityDiscoveryReport,
)
from app.capability_evaluation import (
    CapabilityEvaluationEvidence,
    CapabilityEvaluationReport,
)
from .code_review import CodeReviewReport, CodeReviewService
from .capability_integration import (
    CapabilityIntegrationPipelineReview,
    CapabilityIntegrationSnapshot,
    CapabilityIntegrationStage,
    CapabilityIntegrationStatus,
    CapabilityIntegrationWorkflowService,
)
from .diagnostics import DiagnosticEvidence, DiagnosticReport, DiagnosticService
from .failure_detection import (
    DetectedFailure,
    FailureDetectionReport,
    FailureDetectionService,
)
from .maintenance_proposals import MaintenanceProposal, MaintenanceProposalService
from .maintenance_approvals import (
    MaintenanceApprovalReview,
    MaintenanceApprovalService,
    MaintenanceApprovalSummary,
)
from .git_checkpoints import (
    GitCheckpoint,
    GitCheckpointService,
)
from .maintenance_sandbox import (
    MaintenanceSandboxReport,
    MaintenanceSandboxService,
)
from .maintenance_workflow import (
    MaintenanceWorkflowService,
    MaintenanceWorkflowSnapshot,
)
from .patch_development import PatchDevelopmentService, PatchWorkspace
from .system_monitoring import SystemMonitoringReport
from .testing_workflow import TestRunReport, TestingWorkflowService

if TYPE_CHECKING:
    from .platform_overview import PlatformOverviewReport


@dataclass(frozen=True)
class CorporationStatusSummary:
    corporation_id: str
    corporation_name: str
    node_id: str
    node_name: str


@dataclass(frozen=True)
class AgentSummary:
    id: str
    name: str
    role: str
    provider: str
    model: str
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class AgentProfileSummary:
    id: str
    name: str
    role: str
    provider: str
    model: str
    capabilities: tuple[str, ...]
    system_prompt: str = ""
    brain_scopes: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    builtin_key: str | None = None
    paused: bool = False
    model_route_preference: str = "manual"


@dataclass(frozen=True)
class EmployeeSummary:
    id: str
    name: str
    role: str
    responsibilities: tuple[str, ...]
    agent_id: str | None


@dataclass(frozen=True)
class ProjectSummary:
    id: str
    name: str
    description: str
    status: str


@dataclass(frozen=True)
class ActivitySummary:
    id: int
    task_id: str
    event: str
    created_at: str


@dataclass(frozen=True)
class ProviderSummary:
    id: str
    type_name: str


@dataclass(frozen=True)
class ModelSummary:
    provider: str
    model: str


@dataclass(frozen=True)
class ModelAssignmentSummary:
    agent_id: str
    provider_id: str
    model_id: str


@dataclass(frozen=True)
class TaskSummary:
    id: str
    title: str
    description: str
    project_id: str | None
    status: str
    result: str | None
    error: str | None
    assigned_agent: str | None
    required_role: str | None
    required_capability: str | None


@dataclass(frozen=True)
class DryRunSummary:
    task_id: str
    task_title: str
    task_description: str
    selected_agent_id: str
    selected_agent_name: str
    selected_agent_role: str
    selected_employee_id: str | None
    selected_employee_name: str | None
    provider: str | None
    model: str | None
    routing_method: str | None
    status: str


class BuiltinAgentProtected(ValueError):
    """Built-in organizational identities can be reset or paused, never removed."""


class CorporationApplicationService:
    """Interface-neutral use cases coordinating existing Corporation services."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        corporation: Corporation | None = None,
        node: Node | None = None,
        *,
        tool_registry: ToolRegistry | None = None,
        capability_authorization_service=None,
    ):
        if tool_registry is not None and not isinstance(tool_registry, ToolRegistry):
            raise TypeError("tool_registry must be a ToolRegistry or None")
        self._orchestrator = orchestrator
        employees = getattr(orchestrator, "employees", None)
        self._operator_state_store = None
        if corporation is not None:
            from .operator_state_store import OperatorStateStore
            self._operator_state_store = OperatorStateStore(corporation.id)
        self._positions = PositionRegistry(
            employees if isinstance(employees, EmployeeRegistry) else None,
            persistence=self._operator_state_store,
        )
        self._tool_registry = tool_registry
        if capability_authorization_service is None:
            from .capability_authorization import DEFAULT_CAPABILITY_AUTHORIZATION
            capability_authorization_service = DEFAULT_CAPABILITY_AUTHORIZATION
        self._capability_authorization_service = capability_authorization_service
        from .capability_approvals import CapabilityApprovalService
        self._capability_approval_service = CapabilityApprovalService(
            self._capability_authorization_service)
        self._corporation_chat = None
        self._owned_chat = None
        self._owned_employee_chat = None
        self._owned_chat_lock = RLock()
        self._chat_task_proposals = None
        self._chat_task_proposal_lock = Lock()
        self._task_dispatch = None
        self._task_dispatch_lock = Lock()
        self._workflow_review = None
        self._workflow_review_lock = Lock()
        self._assignment_policy = None
        self._assignment_policy_lock = Lock()
        self._task_collaboration = None
        self._capability_integration_workflow: CapabilityIntegrationWorkflowService | None = None
        self._maintenance_proposals = MaintenanceProposalService()
        self._patch_development = PatchDevelopmentService()
        self._maintenance_approvals = MaintenanceApprovalService(
            self._patch_development
        )
        self._git_checkpoints = GitCheckpointService(
            self._patch_development,
            self._maintenance_approvals,
        )
        self._maintenance_workflow: MaintenanceWorkflowService | None = None
        self._testing_workflow = TestingWorkflowService()
        self._resource_manager = None
        self._controlled_execution = None
        self._resource_manager_lock = RLock()
        self._semantic_memory_index = None
        self._semantic_memory_lock = Lock()
        self._knowledge_proposals = None
        self._knowledge_proposals_lock = Lock()
        self._corporation = corporation
        self._node = node
        self._restore_agent_profiles()

    @staticmethod
    def _profile_record(agent: Agent, employee_id: str | None) -> dict:
        return {
            "id": agent.id, "employee_id": employee_id, "name": agent.name,
            "role": agent.role, "provider": agent.provider, "model": agent.model,
            "capabilities": list(agent.capabilities), "permissions": list(agent.permissions),
            "system_prompt": agent.system_prompt, "brain_scopes": list(agent.brain_scopes),
            "allowed_tools": list(agent.allowed_tools), "builtin_key": agent.builtin_key,
            "paused": agent.paused, "model_route_preference": agent.model_route_preference,
        }

    def _employee_for_agent(self, agent_id: str):
        employees = getattr(self._orchestrator, "employees", None)
        if isinstance(employees, EmployeeRegistry):
            return next((item for item in employees.all() if item.agent and item.agent.id == agent_id), None)
        return None

    def _save_agent_profile(self, agent: Agent, employee_id: str | None = None) -> None:
        if self._operator_state_store is None:
            return
        employee = self._employee_for_agent(agent.id)
        persistent_employee_id = employee.id if employee else employee_id
        self._operator_state_store.save_agent_profile(
            agent.id, self._profile_record(agent, persistent_employee_id),
        )

    def _restore_agent_profiles(self) -> None:
        if self._operator_state_store is None:
            return
        for record in self._operator_state_store.load_agent_profiles():
            required = {"id", "employee_id", "name", "role", "provider", "model", "capabilities",
                        "permissions", "system_prompt", "brain_scopes", "allowed_tools", "builtin_key",
                        "paused", "model_route_preference"}
            if not isinstance(record, dict) or set(record) != required:
                raise RuntimeError("Stored Agent profile failed validation")
            try:
                candidate = Agent(
                    id=record["id"], name=record["name"], role=record["role"],
                    provider=record["provider"], model=record["model"],
                    capabilities=record["capabilities"], permissions=record["permissions"],
                    system_prompt=record["system_prompt"], brain_scopes=record["brain_scopes"],
                    allowed_tools=record["allowed_tools"], builtin_key=record["builtin_key"],
                    paused=record["paused"], model_route_preference=record["model_route_preference"],
                )
                current = self._orchestrator.agents.get(candidate.id) if self._orchestrator.agents.exists(candidate.id) else None
                # Generic runtimes intentionally preserve the legacy one-Agent
                # baseline. Keep persisted built-in profiles dormant until the
                # configured local app provisions those identities.
                if candidate.builtin_key is not None and current is None:
                    continue
                if current is not None and ((candidate.builtin_key is None) != (current.builtin_key is None)):
                    continue
                if current is not None:
                    if current.builtin_key != candidate.builtin_key:
                        raise ValueError("Built-in identity changed")
                    current.__dict__.update(candidate.__dict__)
                    candidate = current
                else:
                    if candidate.builtin_key is not None or not candidate.id.startswith("custom_"):
                        raise ValueError("Unknown Agent identity")
                    self._orchestrator.agents.register(candidate)
                employees = getattr(self._orchestrator, "employees", None)
                if not isinstance(employees, EmployeeRegistry):
                    raise ValueError("Employee registry is unavailable")
                employee_id = record["employee_id"]
                if employee_id is None:
                    continue
                if not isinstance(employee_id, str) or not employee_id:
                    raise ValueError("Employee identity is invalid")
                if employees.exists(employee_id):
                    employee = employees.get(employee_id)
                    employee.name, employee.role = candidate.name, candidate.role
                    employee.responsibilities, employee.agent = [candidate.system_prompt or candidate.role], candidate
                else:
                    if not employee_id.startswith("custom_employee_"):
                        raise ValueError("Unknown Employee identity")
                    employees.register(Employee(employee_id, candidate.name, candidate.role,
                                                [candidate.system_prompt or candidate.role], candidate))
            except (TypeError, ValueError, KeyError):
                raise RuntimeError("Stored Agent profile failed validation") from None

    def update_agent_profile(self, agent_id: str, *, name: str, role: str,
                              system_prompt: str, brain_scopes: list[str],
                              allowed_tools: list[str], permissions: list[str]) -> AgentProfileSummary:
        allowed_tools_set = {tool for profile in BUILTIN_AGENT_PROFILES for tool in profile.tools}
        allowed_permissions = {permission for profile in BUILTIN_AGENT_PROFILES for permission in profile.permissions}
        if (not isinstance(name, str) or not name.strip() or len(name) > 128
                or not isinstance(role, str) or not role.strip() or len(role) > 256
                or not isinstance(system_prompt, str) or len(system_prompt.encode("utf-8")) > 2000
                or not isinstance(brain_scopes, list) or any(scope != "owner" for scope in brain_scopes)
                or len(brain_scopes) > 8
                or not isinstance(allowed_tools, list) or len(allowed_tools) > 12
                or any(tool not in allowed_tools_set for tool in allowed_tools)
                or not isinstance(permissions, list) or len(permissions) > 12
                or any(permission not in allowed_permissions for permission in permissions)):
            raise ValueError("Agent role profile exceeds supported scope")
        with self.agent_assignment_change(agent_id):
            agent = self._orchestrator.agents.get(agent_id)
            before = self._profile_record(agent, None)
            employee = self._employee_for_agent(agent_id)
            employee_before = ((employee.name, employee.role, list(employee.responsibilities))
                               if employee else None)
            try:
                agent.name, agent.role = name.strip(), role.strip()
                agent.system_prompt = system_prompt.strip()
                agent.brain_scopes, agent.allowed_tools = list(brain_scopes), list(allowed_tools)
                agent.permissions = list(permissions)
                if employee:
                    employee.name, employee.role = agent.name, agent.role
                    employee.responsibilities = [agent.system_prompt or agent.role]
                self._save_agent_profile(agent)
            except Exception:
                agent.__dict__.update({key: value for key, value in before.items() if key in agent.__dict__})
                if employee and employee_before:
                    employee.name, employee.role, employee.responsibilities = employee_before
                raise
            return self._agent_profile_summary(agent)

    def set_agent_paused(self, agent_id: str, paused: bool) -> AgentProfileSummary:
        if type(paused) is not bool:
            raise ValueError("Pause state must be boolean")
        with self.agent_assignment_change(agent_id):
            agent = self._orchestrator.agents.get(agent_id)
            previous = agent.paused
            agent.paused = paused
            try:
                self._save_agent_profile(agent)
            except Exception:
                agent.paused = previous
                raise
            return self._agent_profile_summary(agent)

    def reset_builtin_agent(self, agent_id: str) -> AgentProfileSummary:
        from app.agents.builtins import _apply_default, profile_for
        with self.agent_assignment_change(agent_id):
            agent = self._orchestrator.agents.get(agent_id)
            if agent.builtin_key is None:
                raise ValueError("Only a built-in Agent can be reset")
            profile = profile_for(agent.builtin_key)
            before = self._profile_record(agent, None)
            employee = self._employee_for_agent(agent_id)
            employee_before = ((employee.name, employee.role, list(employee.responsibilities))
                               if employee else None)
            coordinator = self._orchestrator.agents.get("local_worker")
            provider_id, model_id = coordinator.provider, coordinator.model
            coder = None
            try:
                inventory = self._orchestrator.providers.get("ollama").local_model_inventory()
                coder = next((model for model in inventory.models if "coder" in model.casefold()), None) \
                    if inventory.state == "available" else None
            except (ValueError, AttributeError):
                pass
            _apply_default(agent, profile, provider_id, model_id, coder if profile.prefer_coder else None)
            employee = self._employee_for_agent(agent_id)
            if employee:
                employee.name, employee.role = agent.name, agent.role
                employee.responsibilities = [agent.system_prompt]
            try:
                self._save_agent_profile(agent)
            except Exception:
                agent.__dict__.update({key: value for key, value in before.items() if key in agent.__dict__})
                if employee and employee_before:
                    employee.name, employee.role, employee.responsibilities = employee_before
                raise
            return self._agent_profile_summary(agent)

    def duplicate_agent(self, agent_id: str, new_id: str, name: str) -> AgentProfileSummary:
        if (not isinstance(new_id, str) or not new_id.startswith("custom_") or len(new_id) > 64
                or not isinstance(name, str) or not name.strip() or len(name) > 128):
            raise ValueError("Custom Agent identity or name is invalid")
        source = self._orchestrator.agents.get(agent_id)
        employee_id = f"custom_employee_{new_id.removeprefix('custom_')}"
        if self._orchestrator.agents.exists(new_id):
            raise ValueError("Agent already exists")
        employee_registry = getattr(self._orchestrator, "employees", None)
        if not isinstance(employee_registry, EmployeeRegistry) or employee_registry.exists(employee_id):
            raise ValueError("Employee identity already exists")
        copy = Agent(
            id=new_id, name=name.strip(), role=source.role, provider=source.provider, model=source.model,
            capabilities=list(source.capabilities), permissions=list(source.permissions),
            system_prompt=source.system_prompt, brain_scopes=list(source.brain_scopes),
            allowed_tools=list(source.allowed_tools), builtin_key=None, paused=False,
            model_route_preference="manual",
        )
        if self._operator_state_store is not None:
            self._operator_state_store.save_agent_profile(
                copy.id, self._profile_record(copy, employee_id),
            )
        self._orchestrator.agents.register(copy)
        employee_registry.register(Employee(employee_id, copy.name, copy.role,
                                            [copy.system_prompt or copy.role], copy))
        return self._agent_profile_summary(copy)

    def authorize_capability(self, *, identity: str, permissions: frozenset[str],
                             capability_id: str, scope_type: str, scope_id: str,
                             session_grants: frozenset[tuple[str, str, str]] = frozenset()):
        """Enforce the shared capability policy at trusted application-service boundaries."""
        return self._capability_authorization_service.require(
            identity=identity, permissions=permissions, capability_id=capability_id,
            scope_type=scope_type, scope_id=scope_id, session_grants=session_grants)

    def capability_approvals(self):
        """Return the bounded process-local review service for exact protected actions."""
        return self._capability_approval_service

    def assess_model_resources(self, candidates):
        from app.resources.assessment import assess_model_resources
        snapshot = self._resource_manager.snapshot() if self._resource_manager is not None else None
        return assess_model_resources(candidates, snapshot=snapshot,
                                      registered_providers=self._orchestrator.providers.all())

    def assignment_policy(self):
        """Return the process-local, non-mutating owner assignment policy service."""
        with self._assignment_policy_lock:
            if self._assignment_policy is None:
                from .assignment_policy import AssignmentPolicyService
                self._assignment_policy = AssignmentPolicyService(self)
            return self._assignment_policy

    def check_provider_availability(self, provider_id):
        """Explicitly check a registered provider without changing runtime state."""
        return self._orchestrator.providers.get(provider_id).check_availability()

    def select_model_candidate(self, candidates, constraints):
        from app.resources import ModelRoutingConstraints, RoutingCandidate
        from app.resources.routing import select_model_candidate
        if not isinstance(candidates, tuple) or not 1 <= len(candidates) <= 100:
            raise ValueError("Supply an immutable tuple of 1 to 100 routing candidates")
        if not all(isinstance(candidate, RoutingCandidate) for candidate in candidates):
            raise TypeError("Expected RoutingCandidate")
        if not isinstance(constraints, ModelRoutingConstraints):
            raise TypeError("Expected ModelRoutingConstraints")
        admission = self.assess_model_resources(
            tuple(candidate.candidate for candidate in candidates)
        )
        return select_model_candidate(
            candidates,
            constraints,
            admission_assessments=admission,
        )

    def task_collaboration(self):
        """Return the local caller-driven Agent collaboration service."""
        if self._task_collaboration is None:
            from app.orchestrator.collaboration import TaskCollaborationService
            self._task_collaboration = TaskCollaborationService(
                agents=self._orchestrator.agents,
                tasks=self._orchestrator.tasks,
                logger=self._orchestrator.logger,
            )
        return self._task_collaboration

    def monitor_system(self) -> SystemMonitoringReport:
        """Return an on-demand report without probing Providers or changing state."""
        from .system_monitoring import SystemMonitoringService
        return SystemMonitoringService(
            tasks=self._orchestrator.tasks,
            providers=self._orchestrator.providers,
            resource_manager=self._resource_manager,
        ).report()

    def discover_capabilities(
        self,
        candidates: tuple[CapabilityCandidate, ...],
    ) -> CapabilityDiscoveryReport:
        """Record caller-supplied candidates without external discovery or activation."""
        from app.capability_discovery import CapabilityDiscoveryService
        return CapabilityDiscoveryService().discover(candidates)

    def evaluate_capability(
        self,
        candidate: CapabilityCandidate,
        evidence: tuple[CapabilityEvaluationEvidence, ...],
    ) -> CapabilityEvaluationReport:
        """Group caller-supplied evaluation evidence without validating its claims."""
        from app.capability_evaluation import CapabilityEvaluationService
        return CapabilityEvaluationService().evaluate(candidate, evidence)

    def start_capability_integration_workflow(
        self,
        candidate: CapabilityCandidate,
        evaluation: CapabilityEvaluationReport,
        workspace_id: str,
    ) -> CapabilityIntegrationSnapshot:
        """Record a caller-asserted candidate/workspace link without integrating it."""
        return self._get_capability_integration_workflow().start(
            candidate,
            evaluation,
            workspace_id,
        )

    def record_capability_integration_test_result(
        self,
        workflow_id: str,
        report: TestRunReport | MaintenanceSandboxReport,
    ) -> CapabilityIntegrationSnapshot:
        return self._get_capability_integration_workflow().record_test_result(
            workflow_id,
            report,
        )

    def record_capability_integration_review(
        self,
        workflow_id: str,
        report: CodeReviewReport,
        evidence: tuple[DiagnosticEvidence, ...],
    ) -> CapabilityIntegrationSnapshot:
        return self._get_capability_integration_workflow().record_review(
            workflow_id,
            report,
            evidence,
        )

    def record_capability_integration_approval(
        self,
        workflow_id: str,
        request_id: str,
    ) -> CapabilityIntegrationSnapshot:
        return self._get_capability_integration_workflow().record_approval(
            workflow_id,
            request_id,
        )

    def record_capability_integration_checkpoint(
        self,
        workflow_id: str,
        checkpoint_id: str,
    ) -> CapabilityIntegrationSnapshot:
        return self._get_capability_integration_workflow().record_checkpoint(
            workflow_id,
            checkpoint_id,
        )

    def get_capability_integration_workflow(
        self,
        workflow_id: str,
    ) -> CapabilityIntegrationSnapshot:
        return self._get_capability_integration_workflow().get(workflow_id)

    def list_capability_integration_workflows(
        self,
    ) -> tuple[CapabilityIntegrationSnapshot, ...]:
        return self._get_capability_integration_workflow().list()

    def review_capability_integration_pipeline(
        self,
    ) -> CapabilityIntegrationPipelineReview:
        """Report recorded capability-workflow progress and artifact consistency."""
        return self._get_capability_integration_workflow().review_pipeline()

    def detect_failures(self) -> FailureDetectionReport:
        """Return bounded Task failure categories without exception details."""
        return FailureDetectionService(tasks=self._orchestrator.tasks).report()

    def diagnose_failure(
        self,
        agent_id: str,
        failure: DetectedFailure,
        evidence: tuple[DiagnosticEvidence, ...],
    ) -> DiagnosticReport:
        """Run one explicit diagnostic Agent call over supplied evidence only."""
        return DiagnosticService(
            agents=self._orchestrator.agents,
            orchestrator=self._orchestrator,
        ).diagnose(agent_id, failure, evidence)

    def review_proposed_changes(
        self,
        agent_id: str,
        evidence: tuple[DiagnosticEvidence, ...],
    ) -> CodeReviewReport:
        """Review supplied evidence through the selected Agent's configured Provider.

        Callers must sanitize the evidence and authorize its disclosure.
        """
        return CodeReviewService(
            agents=self._orchestrator.agents,
            orchestrator=self._orchestrator,
        ).review(agent_id, evidence)

    def create_maintenance_proposal(
        self,
        proposal_id: str,
        diagnostic: DiagnosticReport,
        *,
        title: str,
        proposed_change: str,
        scope: str,
        risk: str,
    ) -> MaintenanceProposal:
        """Record an immutable caller-authored proposal; perform no changes."""
        return self._maintenance_proposals.create(
            proposal_id,
            diagnostic,
            title=title,
            proposed_change=proposed_change,
            scope=scope,
            risk=risk,
        )

    def get_maintenance_proposal(self, proposal_id: str) -> MaintenanceProposal:
        return self._maintenance_proposals.get(proposal_id)

    def list_maintenance_proposals(self) -> tuple[MaintenanceProposal, ...]:
        return self._maintenance_proposals.all()

    def develop_patch(
        self,
        proposal_id: str,
        source_root: str | Path,
        selected_files: tuple[str, ...],
        unified_diff: str,
    ) -> PatchWorkspace:
        proposal = self._maintenance_proposals.get(proposal_id)
        return self._patch_development.develop(
            proposal,
            source_root,
            selected_files,
            unified_diff,
        )

    def get_patch_workspace(self, workspace_id: str) -> PatchWorkspace:
        return self._patch_development.get(workspace_id)

    def dispose_patch_workspace(self, workspace_id: str) -> None:
        self._patch_development.dispose(workspace_id)

    def request_maintenance_approval(
        self,
        workspace_id: str,
    ) -> MaintenanceApprovalReview:
        return self._maintenance_approvals.request_review(workspace_id)

    def list_pending_maintenance_approvals(
        self,
    ) -> tuple[MaintenanceApprovalSummary, ...]:
        return self._maintenance_approvals.list_pending()

    def get_maintenance_approval(
        self,
        request_id: str,
    ) -> MaintenanceApprovalReview:
        return self._maintenance_approvals.get_review(request_id)

    def approve_maintenance_workspace(
        self,
        request_id: str,
        *,
        approver_id: str,
        patch_sha256: str,
        source_sha256: str,
    ) -> MaintenanceApprovalReview:
        return self._maintenance_approvals.approve(
            request_id,
            approver_id=approver_id,
            patch_sha256=patch_sha256,
            source_sha256=source_sha256,
        )

    def reject_maintenance_workspace(
        self,
        request_id: str,
        *,
        approver_id: str,
        patch_sha256: str,
        source_sha256: str,
    ) -> MaintenanceApprovalReview:
        return self._maintenance_approvals.reject(
            request_id,
            approver_id=approver_id,
            patch_sha256=patch_sha256,
            source_sha256=source_sha256,
        )

    def require_approved_maintenance_workspace(
        self,
        workspace_id: str,
    ) -> MaintenanceApprovalReview:
        """Fail closed unless a human approved this exact patch and source."""
        return self._maintenance_approvals.require_approved(workspace_id)

    def create_maintenance_checkpoint(
        self,
        workspace_id: str,
        *,
        created_by: str,
        source_root: Path | None = None,
        approval_request_id: str | None = None,
    ) -> GitCheckpoint:
        return self._git_checkpoints.create(
            workspace_id,
            created_by=created_by,
            source_root=source_root,
            approval_request_id=approval_request_id,
        )

    def activate_maintenance_checkpoint(
        self, checkpoint_id: str, *, source_root: Path
    ) -> GitCheckpoint:
        return self._git_checkpoints.activate(checkpoint_id, source_root=source_root)

    def recover_maintenance_activation(
        self, checkpoint_id: str, *, source_root: Path
    ) -> GitCheckpoint:
        return self._git_checkpoints.recover_activation(
            checkpoint_id, source_root=source_root
        )

    def list_maintenance_checkpoints(self) -> tuple[GitCheckpoint, ...]:
        return self._git_checkpoints.list()

    def get_maintenance_checkpoint(self, checkpoint_id: str) -> GitCheckpoint:
        return self._git_checkpoints.get(checkpoint_id)

    def start_maintenance_workflow(
        self,
        failure: DetectedFailure,
    ) -> MaintenanceWorkflowSnapshot:
        """Record an existing Task failure without invoking any workflow stage."""
        return self._get_maintenance_workflow_service().start(failure)

    def get_maintenance_workflow(
        self,
        workflow_id: str,
    ) -> MaintenanceWorkflowSnapshot:
        return self._get_maintenance_workflow_service().get(workflow_id)

    def list_maintenance_workflows(
        self,
    ) -> tuple[MaintenanceWorkflowSnapshot, ...]:
        return self._get_maintenance_workflow_service().list()

    def record_maintenance_diagnostic(
        self,
        workflow_id: str,
        report: DiagnosticReport,
    ) -> MaintenanceWorkflowSnapshot:
        return self._get_maintenance_workflow_service().record_diagnostic(
            workflow_id,
            report,
        )

    def record_maintenance_proposal(
        self,
        workflow_id: str,
        proposal_id: str,
    ) -> MaintenanceWorkflowSnapshot:
        return self._get_maintenance_workflow_service().record_proposal(
            workflow_id,
            proposal_id,
        )

    def record_maintenance_patch(
        self,
        workflow_id: str,
        workspace_id: str,
    ) -> MaintenanceWorkflowSnapshot:
        return self._get_maintenance_workflow_service().record_patch(
            workflow_id,
            workspace_id,
        )

    def record_maintenance_test_result(
        self,
        workflow_id: str,
        report: TestRunReport | MaintenanceSandboxReport,
    ) -> MaintenanceWorkflowSnapshot:
        return self._get_maintenance_workflow_service().record_test_result(
            workflow_id,
            report,
        )

    def record_maintenance_review(
        self,
        workflow_id: str,
        report: CodeReviewReport,
        evidence: tuple[DiagnosticEvidence, ...],
    ) -> MaintenanceWorkflowSnapshot:
        return self._get_maintenance_workflow_service().record_review(
            workflow_id,
            report,
            evidence,
        )

    def record_maintenance_approval(
        self,
        workflow_id: str,
        request_id: str,
    ) -> MaintenanceWorkflowSnapshot:
        return self._get_maintenance_workflow_service().record_approval(
            workflow_id,
            request_id,
        )

    def record_maintenance_checkpoint(
        self,
        workflow_id: str,
        checkpoint_id: str,
    ) -> MaintenanceWorkflowSnapshot:
        return self._get_maintenance_workflow_service().record_checkpoint(
            workflow_id,
            checkpoint_id,
        )

    def _get_maintenance_workflow_service(self) -> MaintenanceWorkflowService:
        if self._maintenance_workflow is None:
            self._maintenance_workflow = MaintenanceWorkflowService(
                tasks=self._orchestrator.tasks,
                proposals=self._maintenance_proposals,
                workspaces=self._patch_development,
                approvals=self._maintenance_approvals,
                checkpoints=self._git_checkpoints,
                logger=self._orchestrator.logger,
            )
        return self._maintenance_workflow

    def _get_capability_integration_workflow(
        self,
    ) -> CapabilityIntegrationWorkflowService:
        if self._capability_integration_workflow is None:
            self._capability_integration_workflow = (
                CapabilityIntegrationWorkflowService(
                    workspaces=self._patch_development,
                    approvals=self._maintenance_approvals,
                    checkpoints=self._git_checkpoints,
                )
            )
        return self._capability_integration_workflow

    def run_selected_tests(
        self,
        workspace_id: str,
        selected_tests: tuple[str, ...],
    ) -> TestRunReport:
        workspace = self._patch_development.get(workspace_id)
        return self._testing_workflow.run(workspace, selected_tests)

    def run_sandboxed_tests(
        self,
        workspace_id: str,
        selected_tests: tuple[str, ...],
        image_policy: SandboxImagePolicy,
        *,
        timeout_seconds: int = MaintenanceSandboxService.MAX_TIMEOUT_SECONDS,
    ) -> MaintenanceSandboxReport:
        """Run selected tests only in an approved isolated Docker image."""
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or not 1 <= timeout_seconds <= MaintenanceSandboxService.MAX_TIMEOUT_SECONDS
        ):
            raise ValueError("timeout_seconds must be from 1 to 60")
        workspace = self._patch_development.get(workspace_id)
        backend = DockerSandboxBackend(
            image_policy,
            client_timeout_seconds=timeout_seconds + 10,
        )
        return MaintenanceSandboxService(backend).run(
            workspace,
            selected_tests,
            timeout_seconds=timeout_seconds,
        )

    def execute_controlled_task(
        self,
        task_id,
        *,
        expected_agent_id=None,
        expected_provider=None,
        expected_model=None,
    ):
        self.resource_manager()  # Reject missing configuration before touching Tasks.
        return self._task_summary(
            self._controlled_execution.execute(
                task_id,
                expected_agent_id=expected_agent_id,
                expected_provider=expected_provider,
                expected_model=expected_model,
            )
        )

    def execution_queue(self):
        if self._corporation is None:
            raise RuntimeError("Corporation identity is not configured")
        return self._orchestrator.execution_queue(self._corporation.id)

    def workflow_review(self):
        with self._workflow_review_lock:
            if self._workflow_review is None:
                from .workflow_review import WorkflowReviewService
                self._workflow_review = WorkflowReviewService(self._run_workflow_destination)
            return self._workflow_review

    def _run_workflow_destination(self, destination, prompt):
        provider = self._orchestrator.providers.get(destination.provider_id)
        return provider.generate(destination.model_id, prompt)

    def task_dispatch(self):
        with self._task_dispatch_lock:
            if self._task_dispatch is None:
                from .task_dispatch import TaskDispatchService
                self._task_dispatch = TaskDispatchService(self)
            return self._task_dispatch

    def is_loopback_ollama_provider(self, provider_id):
        from urllib.parse import urlsplit
        from app.providers import OllamaProvider

        if provider_id != "ollama":
            return False
        try:
            provider = self._orchestrator.providers.get(provider_id)
        except ValueError:
            return False
        if not isinstance(provider, OllamaProvider):
            return False
        try:
            endpoint = urlsplit(provider.base_url)
            port = endpoint.port
        except (TypeError, ValueError):
            return False
        return (
            endpoint.scheme == "http"
            and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
            and endpoint.username is None
            and endpoint.password is None
            and endpoint.path == ""
            and endpoint.query == ""
            and endpoint.fragment == ""
            and (port is None or 1 <= port <= 65535)
        )

    def resource_manager(self, limits=None):
        from app.resources import ModelLimit, ProviderLimit, ResourceLimits, ResourceManager
        with self._resource_manager_lock:
            if self._resource_manager is None:
                if limits is None and self._operator_state_store is not None:
                    stored = self._operator_state_store.load_resource_limits()
                    if stored is not None:
                        try:
                            limits = ResourceLimits(
                                stored["global_slots"],
                                tuple(ProviderLimit(item["provider_id"], item["slots"])
                                      for item in stored["providers"]),
                                tuple(ModelLimit(item["provider_id"], item["model_id"], item["slots"])
                                      for item in stored["models"]),
                            )
                        except (KeyError, TypeError, ValueError):
                            raise RuntimeError("Stored resource limits failed validation") from None
                if limits is None:
                    raise RuntimeError("Resource limits are not configured")
                manager = ResourceManager(limits, self._orchestrator.providers)
                if self._operator_state_store is not None:
                    self._operator_state_store.save_resource_limits({
                        "global_slots": limits.global_slots,
                        "providers": [{"provider_id": item.provider_id, "slots": item.slots}
                                      for item in limits.providers],
                        "models": [{"provider_id": item.provider_id, "model_id": item.model_id,
                                    "slots": item.slots} for item in limits.models],
                    })
                self._resource_manager = manager
                from .controlled_execution import ControlledExecution
                self._controlled_execution = ControlledExecution(self._orchestrator, self._resource_manager)
            elif limits is not None:
                raise ValueError("Resource manager is already configured")
            return self._resource_manager

    def configure_agent_slots(self, *, global_slots: int = 1):
        """Configure shared slots for the routes assigned to existing Agents."""
        from app.resources import ModelLimit, ProviderLimit, ResourceLimits
        with self._resource_manager_lock:
            if self._resource_manager is not None:
                return self._resource_manager
            providers = self._orchestrator.providers
            assignments = {(agent.provider, agent.model) for agent in self._orchestrator.agents.all()
                           if providers.exists(agent.provider) and agent.model}
            if not assignments:
                raise RuntimeError("No registered Agent model routes are available for resource slots")
            provider_ids = sorted({provider_id for provider_id, _model in assignments})
            limits = ResourceLimits(
                global_slots=global_slots,
                providers=tuple(ProviderLimit(provider_id, 1) for provider_id in provider_ids),
                models=tuple(ModelLimit(provider_id, model_id, 1)
                             for provider_id, model_id in sorted(assignments)),
            )
            return self.resource_manager(limits)

    @contextmanager
    def owned_chat_agent_execution(self, agent_id: str):
        """Reserve the shared ResourceManager slot for an owner-directed Agent turn."""
        from uuid import uuid4
        from app.resources import ResourceCapacityError
        from .owned_chat import ChatConflict
        try:
            agent = self._orchestrator.agents.get(agent_id)
        except ValueError:
            with self._orchestrator.agents.execution(agent_id):
                yield
            return
        manager = self._resource_manager or self.configure_agent_slots(global_slots=1)
        with self._orchestrator.agents.execution(agent_id):
            allocation_id = f"chat_{uuid4().hex}"
            if not self._orchestrator.providers.exists(agent.provider):
                yield
                return
            try:
                manager.ensure_route(provider_id=agent.provider, model_id=agent.model)
                manager.allocate(allocation_id, provider_id=agent.provider, model_id=agent.model)
            except ResourceCapacityError:
                from .owned_chat import ChatLimit
                raise ChatLimit("request-slot capacity is exhausted") from None
            try:
                yield
            finally:
                manager.release(allocation_id)

    def image_processing(self):
        """Return an optional image adapter without loading Pillow at startup."""
        from app.integrations.image_processing import PillowImageProcessingAdapter
        return PillowImageProcessingAdapter()

    def ocr(self, provider=None, *, timeout_seconds=2.0):
        """Construct OCR lazily; an optional local Tesseract path is owner-configured."""
        if provider is None:
            import os
            executable = os.environ.get("ERSELMETZ_TESSERACT_PATH")
            if executable:
                from app.integrations.tesseract_ocr import TesseractLocalProvider
                provider = TesseractLocalProvider(
                    executable,
                    tessdata_directory=os.environ.get("ERSELMETZ_TESSDATA_PATH") or None,
                )
        from app.integrations.ocr import OcrService
        return OcrService(provider, timeout_seconds=timeout_seconds)

    def task_planning(self):
        from .task_planning import TaskPlanningService
        return TaskPlanningService(self._orchestrator, self.context_retrieval())

    def corporation_planning(self):
        if self._corporation is None:
            raise RuntimeError("Corporation identity is not configured")
        from .organization_planning import OrganizationPlanningService
        return OrganizationPlanningService(self._corporation.id)

    def organization_coordination(self):
        if self._corporation is None:
            raise RuntimeError("Corporation identity is not configured")
        if self._orchestrator.employees is None:
            raise RuntimeError("Employee registry is not configured")
        from .organization_coordination import OrganizationCoordinationService
        return OrganizationCoordinationService(
            corporation_id=self._corporation.id,
            employees=self._orchestrator.employees,
            maintenance_workflows=self._get_maintenance_workflow_service(),
            capability_workflows=self._get_capability_integration_workflow(),
        )

    def workforce_review(self):
        if self._corporation is None:
            raise RuntimeError("Corporation identity is not configured")
        if self._orchestrator.employees is None:
            raise RuntimeError("Employee registry is not configured")
        from .workforce_review import WorkforceReviewService
        return WorkforceReviewService(
            self._corporation.id,
            self._orchestrator.employees,
        )

    def context_retrieval(self):
        from .context_retrieval import ContextRetrievalService
        return ContextRetrievalService(self.memory_management(), semantic_provider=self.semantic_memory)

    def memory_management(self):
        from .memory_management import MemoryManagementService
        return MemoryManagementService(self._orchestrator, self._corporation.id if self._corporation else None,
                                       semantic_invalidator=self.invalidate_semantic_memory)

    def invalidate_semantic_memory(self, memory_id, *, scope, scope_id):
        service = self._semantic_memory_index
        if service is not None:
            service.invalidate_all_owners(memory_id, scope=scope, scope_id=scope_id)

    def semantic_memory(self):
        """Return the optional local semantic capability; it never downloads a model."""
        with self._semantic_memory_lock:
            if self._semantic_memory_index is not None:
                return self._semantic_memory_index
            from app.knowledge import SemanticMemoryService
            import importlib.util
            import os
            from pathlib import Path

            ollama_model = os.environ.get("ERSELMETZ_KNOWLEDGE_OLLAMA_MODEL", "").strip()
            model_path = os.environ.get("ERSELMETZ_KNOWLEDGE_EMBEDDING_MODEL", "").strip()
            vector_path = os.environ.get("ERSELMETZ_KNOWLEDGE_VECTOR_DIR", "").strip()
            manager = self.memory_management()
            if not vector_path:
                from app.knowledge.faiss_pack import application_data_root, activate_faiss_pack
                pack_root = application_data_root() / "capability-packs" / "faiss-cpu"
                if (pack_root / "site-packages").is_dir() and not pack_root.is_symlink():
                    try:
                        activate_faiss_pack(pack_root / "site-packages")
                        from app.knowledge.providers import OllamaEmbeddingProvider
                        from app.knowledge.vector_store import FaissVectorStore
                        self._semantic_memory_index = SemanticMemoryService(
                            manager,
                            OllamaEmbeddingProvider(ollama_model or "nomic-embed-text"),
                            FaissVectorStore(str(application_data_root() / "brain" / "vectors")),
                        )
                    except Exception:
                        self._semantic_memory_index = SemanticMemoryService(
                            manager, unavailable_reason="The installed local FAISS capability could not be initialized.")
                    return self._semantic_memory_index
            if not vector_path:
                self._semantic_memory_index = SemanticMemoryService(manager)
                return self._semantic_memory_index
            if ollama_model:
                from app.knowledge.providers import OllamaEmbeddingProvider
                from app.knowledge.vector_store import ChromaVectorStore
                try:
                    provider = OllamaEmbeddingProvider(ollama_model)
                    store = ChromaVectorStore(vector_path)
                except Exception:
                    self._semantic_memory_index = SemanticMemoryService(
                        manager, unavailable_reason="The configured local Ollama embedding capability could not be initialized.")
                    return self._semantic_memory_index
                self._semantic_memory_index = SemanticMemoryService(manager, provider, store)
                return self._semantic_memory_index
            if not model_path:
                self._semantic_memory_index = SemanticMemoryService(manager)
                return self._semantic_memory_index
            if not Path(model_path).expanduser().is_dir():
                self._semantic_memory_index = SemanticMemoryService(
                    manager, unavailable_reason="The configured local embedding model directory is unavailable.")
                return self._semantic_memory_index
            if importlib.util.find_spec("sentence_transformers") is None or importlib.util.find_spec("chromadb") is None:
                self._semantic_memory_index = SemanticMemoryService(
                    manager, unavailable_reason="Install the optional knowledge requirements to enable local semantic retrieval.")
                return self._semantic_memory_index

            from app.knowledge.providers import SentenceTransformerEmbeddingProvider
            from app.knowledge.vector_store import ChromaVectorStore
            try:
                provider = SentenceTransformerEmbeddingProvider(model_path)
                store = ChromaVectorStore(vector_path)
            except Exception:
                self._semantic_memory_index = SemanticMemoryService(
                    manager, unavailable_reason="The configured local semantic capability could not be initialized.")
                return self._semantic_memory_index
            self._semantic_memory_index = SemanticMemoryService(manager, provider, store)
            return self._semantic_memory_index

    def configure_semantic_memory(self, service):
        """Install an explicitly configured semantic adapter for deterministic hosts/tests."""
        from app.knowledge import SemanticMemoryService
        if not isinstance(service, SemanticMemoryService):
            raise TypeError("Expected a SemanticMemoryService")
        with self._semantic_memory_lock:
            if self._semantic_memory_index is not None and self._semantic_memory_index is not service:
                raise RuntimeError("Semantic memory is already configured for this application run")
            self._semantic_memory_index = service
        return service

    def reset_semantic_memory(self):
        """Refresh lazy optional knowledge adapters after an owner-confirmed pack install."""
        with self._semantic_memory_lock:
            self._semantic_memory_index = None

    def generate_local_knowledge_proposal(self, agent_id: str, prompt: str) -> str:
        """Generate one proposal only through the configured loopback Ollama Agent."""
        from app.providers import OllamaProvider
        agent = self._orchestrator.agents.get(agent_id)
        if agent.provider != "ollama" or not self.is_loopback_ollama_provider(agent.provider):
            raise ValueError("Knowledge proposals support only the configured loopback Ollama provider")
        provider = self._orchestrator.providers.get(agent.provider)
        if not isinstance(provider, OllamaProvider):
            raise ValueError("Knowledge proposals support only the configured loopback Ollama provider")
        if not agent.model or not isinstance(prompt, str) or len(prompt.encode("utf-8")) > 32768:
            raise ValueError("Knowledge proposal request is invalid or exceeds its bound")
        return self._orchestrator.run_agent(
            agent_id, prompt, expected_assignment=(agent.provider, agent.model)
        )

    def knowledge_proposals(self):
        """Return the bounded process-local proposal review service."""
        with self._knowledge_proposals_lock:
            if self._knowledge_proposals is None:
                from .knowledge_proposals import KnowledgeProposalService
                self._knowledge_proposals = KnowledgeProposalService(self)
            return self._knowledge_proposals

    def corporation_knowledge(self):
        if self._corporation is None:
            raise RuntimeError("Corporation runtime identity is not configured")
        from .corporation_knowledge import CorporationKnowledgeService
        return CorporationKnowledgeService(self._corporation.id, self._orchestrator,
                                           semantic_invalidator=self.invalidate_semantic_memory)

    def project_knowledge(self):
        from .project_knowledge import ProjectKnowledgeService
        return ProjectKnowledgeService(self._orchestrator,
                                       semantic_invalidator=self.invalidate_semantic_memory)

    def owned_chat(self):
        """Separate principal-owned HTTP chat facade, safely constructed once."""
        with self._owned_chat_lock:
            if self._owned_chat is None:
                if self._corporation is None:
                    raise ValueError("Corporation identity is required")
                from .corporation_chat import CorporationChatService
                from .owned_chat import OwnedChatService
                chat = CorporationChatService(self._corporation.id, self._orchestrator)
                chat.history = self.chat_history()
                self._owned_chat = OwnedChatService(
                    chat,
                    self.get_agent,
                    self._orchestrator.providers.get,
                    self.owned_chat_agent_execution,
                )
            return self._owned_chat

    def chat_history(self):
        with self._owned_chat_lock:
            if getattr(self, "_chat_history", None) is None:
                if self._corporation is None:
                    raise ValueError("Corporation identity is required")
                from .chat_history import ChatHistoryService
                self._chat_history = ChatHistoryService(self._corporation.id)
            return self._chat_history

    def chat_knowledge(self):
        with self._owned_chat_lock:
            if getattr(self, "_chat_knowledge", None) is None:
                from .chat_knowledge import ChatKnowledgeService
                self._chat_knowledge = ChatKnowledgeService(self)
            return self._chat_knowledge

    def chat_task_proposals(self):
        """Return the bounded owner-scoped review service for coordinator proposals."""
        self.owned_chat()
        with self._chat_task_proposal_lock:
            if self._chat_task_proposals is None:
                from .chat_task_proposals import ChatTaskProposalService
                self._chat_task_proposals = ChatTaskProposalService(
                    self, persistence=self._operator_state_store
                )
            return self._chat_task_proposals

    def operator_state_store(self):
        """Expose the local persistence boundary to application services only."""
        return self._operator_state_store

    def owned_employee_chat(self):
        """Return the principal-owned Employee chat facade for this app run."""
        employees = self._orchestrator.employees
        if employees is None:
            raise RuntimeError("Employee chat is not configured")
        owned_chat = self.owned_chat()
        with self._owned_chat_lock:
            if self._owned_employee_chat is None:
                from .owned_employee_chat import OwnedEmployeeChatService
                self._owned_employee_chat = OwnedEmployeeChatService(
                    employees,
                    self._orchestrator.agents,
                    self._orchestrator.providers,
                    self._orchestrator,
                    owned_chat.agent_request,
                    persistence=self._operator_state_store,
                )
            return self._owned_employee_chat

    def corporation_chat(self):
        """Local-only facade; no HTTP exposure or new permission grant."""
        if self._corporation is None:
            raise RuntimeError("Corporation runtime identity is not configured")
        if self._corporation_chat is None:
            from .corporation_chat import CorporationChatService
            self._corporation_chat = CorporationChatService(self._corporation.id, self._orchestrator)
        return self._corporation_chat

    def get_corporation_status(self) -> CorporationStatusSummary:
        if self._corporation is None or self._node is None:
            raise RuntimeError("Corporation runtime identity is not configured")
        return CorporationStatusSummary(
            corporation_id=self._corporation.id,
            corporation_name=self._corporation.name,
            node_id=self._node.id,
            node_name=self._node.name,
        )

    def platform_overview(self) -> "PlatformOverviewReport":
        """Return a bounded read-only snapshot of current platform sources."""
        from .platform_overview import PlatformOverviewService

        identity = (
            self.get_corporation_status()
            if self._corporation is not None and self._node is not None
            else None
        )
        return PlatformOverviewService(
            self._orchestrator,
            identity,
            self._tool_registry,
        ).report()

    def list_agents(self) -> list[AgentSummary]:
        return [
            self._agent_summary(agent)
            for agent in self._orchestrator.agents.all()
        ]

    def get_agent(self, agent_id: str) -> AgentSummary:
        return self._agent_summary(self._orchestrator.agents.get(agent_id))

    def get_agent_profile(self, agent_id: str) -> AgentProfileSummary:
        return self._agent_profile_summary(self._orchestrator.agents.get(agent_id))

    def agent_runtime_statuses(self) -> tuple[dict, ...]:
        """Return an on-demand status snapshot from registry state and provider checks."""
        providers = {}
        inventories = {}
        results = []
        for agent in self._orchestrator.agents.all()[:100]:
            reason = None
            if agent.paused:
                state = "paused"
            elif self._orchestrator.agents.is_executing(agent.id):
                state = "working"
            elif not self._orchestrator.providers.exists(agent.provider):
                state, reason = "unavailable", "Assigned provider is not registered."
            else:
                provider = self._orchestrator.providers.get(agent.provider)
                availability = providers.get(agent.provider)
                if availability is None:
                    try:
                        availability = provider.check_availability()
                    except Exception:
                        availability = None
                    providers[agent.provider] = availability
                if availability is None or getattr(getattr(availability, "state", None), "value", None) == "unknown":
                    state, reason = "error", "Provider availability could not be confirmed."
                elif availability.state.value == "unavailable":
                    state, reason = "unavailable", "Assigned provider is unavailable."
                else:
                    inventory = inventories.get(agent.provider)
                    if inventory is None and getattr(provider, "is_local", False) is True:
                        try:
                            inventory = provider.local_model_inventory()
                        except Exception:
                            inventory = None
                        inventories[agent.provider] = inventory
                    if getattr(provider, "is_local", False) is True:
                        if inventory is None or inventory.state != "available":
                            state, reason = "error", "Installed model inventory could not be confirmed."
                        elif agent.model not in inventory.models:
                            state, reason = "unavailable", "Assigned model is not installed."
                        else:
                            state = "error" if self._orchestrator.agents.last_failed(agent.id) else "idle"
                    else:
                        state = "error" if self._orchestrator.agents.last_failed(agent.id) else "idle"
                    if state == "error" and reason is None:
                        reason = "The last Agent run failed; review its activity before retrying."
            results.append({"agent_id": agent.id, "status": state, "reason": reason,
                            "provider_id": agent.provider, "model_id": agent.model,
                            "last_active": self._orchestrator.agents.last_active(agent.id)})
        return tuple(results)

    def list_employees(self) -> list[EmployeeSummary]:
        return [
            self._employee_summary(employee)
            for employee in self._employee_management().list_employees()
        ]

    def get_employee(self, employee_id: str) -> EmployeeSummary:
        employee = self._employee_management().get_employee(employee_id)
        return self._employee_summary(employee)

    def create_employee(
        self,
        employee_id: str,
        name: str,
        role: str,
        responsibilities: list[str],
    ) -> EmployeeSummary:
        employee = self._employee_management().create_employee(
            employee_id, name, role, responsibilities
        )
        return self._employee_summary(employee)

    def remove_employee(self, employee_id: str) -> None:
        employee = self._employee_management().get_employee(employee_id)
        if employee.agent is not None and employee.agent.builtin_key is not None:
            raise BuiltinAgentProtected("Built-in Employees cannot be removed; reset the Agent profile instead")
        with self._positions.employee_reference_guard(employee_id):
            self._employee_management().remove_employee(employee_id)

    def list_positions(self) -> tuple[CorporationPosition, ...]:
        return self._positions.list()

    def get_position(self, position_id: str) -> CorporationPosition:
        return self._positions.get(position_id)

    def create_position(
        self,
        title: str,
        responsibilities: list[str],
        reports_to_position_id: str | None = None,
        employee_id: str | None = None,
    ) -> CorporationPosition:
        return self._positions.create(
            title,
            responsibilities,
            reports_to_position_id,
            employee_id,
        )

    def update_position(
        self,
        position_id: str,
        expected_revision: int,
        title: str,
        responsibilities: list[str],
        reports_to_position_id: str | None,
        employee_id: str | None,
    ) -> CorporationPosition:
        return self._positions.update(
            position_id,
            expected_revision,
            title,
            responsibilities,
            reports_to_position_id,
            employee_id,
        )

    def deactivate_position(
        self, position_id: str, expected_revision: int
    ) -> CorporationPosition:
        return self._positions.deactivate(position_id, expected_revision)

    def remove_position(self, position_id: str) -> None:
        self._positions.remove(position_id)

    def list_projects(self) -> list[ProjectSummary]:
        return [
            self._project_summary(project)
            for project in self._orchestrator.projects.all()
        ]

    def get_project(self, project_id: str) -> ProjectSummary:
        return self._project_summary(self._orchestrator.projects.get(project_id))

    def create_project(
        self,
        name: str,
        description: str = "",
    ) -> ProjectSummary:
        project = Project(
            id=f"PROJECT-{uuid4().hex[:8].upper()}",
            name=name,
            description=description,
        )
        self._orchestrator.projects.register(project)
        return self._project_summary(project)

    def list_activity(
        self,
        limit: int = 100,
        task_id: str | None = None,
    ) -> list[ActivitySummary]:
        return [
            ActivitySummary(
                id=record["id"],
                task_id=record["task_id"],
                event=record["event"],
                created_at=record["created_at"],
            )
            for record in self._orchestrator.logger.list_activity(
                limit=limit,
                task_id=task_id,
            )
        ]

    def list_providers(self) -> list[ProviderSummary]:
        return [
            ProviderSummary(id=provider_id, type_name=provider.__class__.__name__)
            for provider_id, provider in self._provider_management()
            .list_providers()
            .items()
        ]

    def get_provider(self, provider_id: str) -> ProviderSummary:
        provider = self._provider_management().get_provider(provider_id)
        return ProviderSummary(
            id=provider_id,
            type_name=provider.__class__.__name__,
        )

    def create_provider(self, provider_id: str, name: str) -> ProviderSummary:
        provider = self._provider_management().create_provider(provider_id, name)
        return ProviderSummary(
            id=provider_id,
            type_name=provider.__class__.__name__,
        )

    def remove_provider(self, provider_id: str) -> None:
        self._provider_management().remove_provider(provider_id)

    def list_models(self) -> list[ModelAssignmentSummary]:
        return [
            ModelAssignmentSummary(
                agent_id=agent.id,
                provider_id=agent.provider,
                model_id=agent.model,
            )
            for agent in self._orchestrator.agents.all()
        ]

    def get_model_assignment(self, agent_id: str) -> ModelAssignmentSummary:
        agent = self._orchestrator.agents.get(agent_id)
        return ModelAssignmentSummary(
            agent_id=agent.id,
            provider_id=agent.provider,
            model_id=agent.model,
        )

    def get_model(self, agent_id: str) -> ModelSummary:
        assignment = self._model_management().get_model(agent_id)
        return ModelSummary(
            provider=assignment["provider"],
            model=assignment["model"],
        )

    def local_model_inventory(self, provider_id: str):
        """Provider abstraction supplies bounded local installed-model evidence."""
        return self._orchestrator.providers.get(provider_id).local_model_inventory()

    def provider_exists(self, provider_id: str) -> bool:
        return self._orchestrator.providers.exists(provider_id)

    def provider_is_local(self, provider_id: str) -> bool:
        return getattr(self._orchestrator.providers.get(provider_id), "is_local", False) is True

    def provider_requires_explicit_cloud_consent(self, provider_id: str) -> bool:
        if provider_id == "gemini" or provider_id.startswith("gemini-"):
            return True
        try:
            provider = self._orchestrator.providers.get(provider_id)
        except ValueError:
            return False
        return (
            getattr(provider, "requires_explicit_cloud_consent", False) is True
        )

    def register_local_provider(self, provider_id: str, provider) -> None:
        self._orchestrator.providers.register(provider_id, provider)

    def remove_local_provider(self, provider_id: str) -> None:
        self._orchestrator.providers.remove(provider_id)

    def select_local_model(
        self,
        agent_id: str,
        provider_id: str,
        model_id: str,
        *,
        expected_model_id: str | None = None,
    ):
        from .owned_chat import ChatConflict, ChatUnavailable
        with self.agent_assignment_change(agent_id):
            agent = self.get_agent(agent_id)
            if agent.provider != provider_id:
                raise ChatConflict("Agent provider changed; refresh assignment")
            if expected_model_id is not None and agent.model != expected_model_id:
                raise ChatConflict("Agent assignment changed; refresh before selecting")
            inventory = self.local_model_inventory(provider_id)
            if not inventory.supported or inventory.state != "available":
                raise ChatUnavailable("Installed-model inventory unavailable; check the local provider")
            if model_id not in inventory.models:
                raise ChatConflict("Selected model is no longer installed; refresh inventory")
            return self._replace_model_unchecked(agent_id, provider_id, model_id)

    @contextmanager
    def agent_assignment_change(self, agent_id: str):
        """Keep all Agent generation idle while an authorized assignment changes."""
        from .owned_chat import ChatConflict
        try:
            with self._orchestrator.agents.assignment_change(agent_id):
                # Model management also supports runtimes without chat identity.
                # Such runtimes cannot create owned chat, but still require the
                # registry execution guard while changing an assignment.
                with (self.owned_chat().configuration_change(agent_id)
                      if self._corporation is not None else nullcontext()):
                    yield
        except AgentAssignmentBusy:
            raise ChatConflict(
                "Agent is busy with active work; wait before changing its connection"
            ) from None

    def _replace_model_unchecked(
        self, agent_id: str, provider_id: str, model: str
    ) -> ModelAssignmentSummary:
        agent = self._model_management().replace_model(agent_id, provider_id, model)
        return ModelAssignmentSummary(
            agent_id=agent.id,
            provider_id=agent.provider,
            model_id=agent.model,
        )

    def replace_model(
        self,
        agent_id: str,
        provider_id: str,
        model: str,
        *,
        manual: bool = True,
    ) -> ModelAssignmentSummary:
        with self.agent_assignment_change(agent_id):
            agent = self._orchestrator.agents.get(agent_id)
            previous = (agent.provider, agent.model, agent.model_route_preference)
            result = self._replace_model_unchecked(agent_id, provider_id, model)
            if manual:
                agent.model_route_preference = "manual"
            try:
                self._save_agent_profile(agent)
            except Exception:
                agent.provider, agent.model, agent.model_route_preference = previous
                raise
            return result

    def assign_model(
        self,
        agent_id: str,
        provider_id: str,
        model: str,
    ) -> AgentSummary:
        with self.agent_assignment_change(agent_id):
            agent = self._orchestrator.agents.get(agent_id)
            previous = (agent.provider, agent.model, agent.model_route_preference)
            agent = self._model_management().assign_model(agent_id, provider_id, model, agent=agent)
            agent.model_route_preference = "manual"
            try:
                self._save_agent_profile(agent)
            except Exception:
                agent.provider, agent.model, agent.model_route_preference = previous
                raise
            return self._agent_summary(agent)

    def list_tasks(self) -> list[TaskSummary]:
        return [
            self._task_summary(task)
            for task in self._orchestrator.tasks.all()
        ]

    def get_task(self, task_id: str) -> TaskSummary:
        return self._task_summary(self._orchestrator.tasks.get(task_id))

    def create_task(
        self,
        title: str,
        description: str,
        project_id: str | None = None,
        agent_id: str | None = None,
        role: str | None = None,
        capability: str | None = None,
    ) -> TaskSummary:
        resolved_project_id = (
            self._default_project_id() if project_id is None else project_id
        )
        routing = {
            key: value
            for key, value in (
                ("agent_id", agent_id),
                ("role", role),
                ("capability", capability),
            )
            if value is not None
        }
        task = self._orchestrator.create_task(
            title=title,
            description=description,
            project_id=resolved_project_id,
            **routing,
        )
        return self._task_summary(task)

    def execute_task(
        self,
        task_id: str,
        role: str | None = None,
        capability: str | None = None,
        agent_id: str | None = None,
    ) -> TaskSummary:
        task = self._orchestrator.tasks.get(task_id)
        routing = {
            key: value
            for key, value in (
                ("role", role),
                ("capability", capability),
                ("agent_id", agent_id),
            )
            if value is not None
        }
        result = self._orchestrator.execute_task(
            task,
            **routing,
        )
        if not isinstance(result, Task):
            raise RuntimeError("Task execution returned an unexpected result")
        return self._task_summary(result)

    def dry_run_task(
        self,
        task_id: str,
        role: str | None = None,
        capability: str | None = None,
        agent_id: str | None = None,
    ) -> DryRunSummary:
        task = self._orchestrator.tasks.get(task_id)
        routing = {
            key: value
            for key, value in (
                ("role", role),
                ("capability", capability),
                ("agent_id", agent_id),
            )
            if value is not None
        }
        result = self._orchestrator.execute_task(
            task,
            dry_run=True,
            **routing,
        )
        if not isinstance(result, DryRunResult):
            raise RuntimeError("Dry-run returned an unexpected result")

        employee = result.selected_employee
        agent = result.selected_agent
        return DryRunSummary(
            task_id=result.task_id,
            task_title=result.task_title,
            task_description=result.task_description,
            selected_agent_id=agent.id,
            selected_agent_name=agent.name,
            selected_agent_role=agent.role,
            selected_employee_id=employee.id if employee else None,
            selected_employee_name=employee.name if employee else None,
            provider=result.provider,
            model=result.model,
            routing_method=result.routing_method,
            status=result.status,
        )

    def _employee_management(self) -> EmployeeManagement:
        if self._orchestrator.employees is None:
            raise RuntimeError("Employee management is not configured")
        return EmployeeManagement(self._orchestrator.employees)

    def _provider_management(self) -> ProviderManagement:
        return ProviderManagement(self._orchestrator.providers)

    def _model_management(self) -> ModelManagement:
        return ModelManagement(
            self._orchestrator.agents,
            self._orchestrator.providers,
        )

    def _default_project_id(self) -> str:
        projects = self._orchestrator.projects.all()
        if projects:
            return projects[0].id

        project = Project(
            id="default_proj",
            name="General",
            description="Default Project",
            status="active",
        )
        self._orchestrator.projects.register(project)
        return project.id

    @staticmethod
    def _employee_summary(employee: Employee) -> EmployeeSummary:
        return EmployeeSummary(
            id=employee.id,
            name=employee.name,
            role=employee.role,
            responsibilities=tuple(employee.responsibilities),
            agent_id=employee.agent.id if employee.agent else None,
        )

    @staticmethod
    def _agent_summary(agent: Agent) -> AgentSummary:
        return AgentSummary(
            id=agent.id,
            name=agent.name,
            role=agent.role,
            provider=agent.provider,
            model=agent.model,
            capabilities=tuple(agent.capabilities),
        )

    @staticmethod
    def _agent_profile_summary(agent: Agent) -> AgentProfileSummary:
        return AgentProfileSummary(
            id=agent.id, name=agent.name, role=agent.role, provider=agent.provider,
            model=agent.model, capabilities=tuple(agent.capabilities),
            system_prompt=agent.system_prompt, brain_scopes=tuple(agent.brain_scopes),
            allowed_tools=tuple(agent.allowed_tools), permissions=tuple(agent.permissions),
            builtin_key=agent.builtin_key, paused=agent.paused,
            model_route_preference=agent.model_route_preference,
        )

    def apply_builtin_default_routes(self, provider_id: str, model_id: str,
                                     installed_ollama_models=()) -> None:
        """Apply first-run default routes while preserving owner-selected manual routes."""
        coder_model = next((item for item in sorted(installed_ollama_models, key=str.casefold)
                            if isinstance(item, str) and "coder" in item.casefold()), None)
        for agent in self._orchestrator.agents.all():
            if agent.builtin_key is None or agent.model_route_preference == "manual":
                continue
            route = ("ollama", coder_model) if agent.model_route_preference == "installed-coder" and coder_model else (provider_id, model_id)
            if (agent.provider, agent.model) != route:
                with self.agent_assignment_change(agent.id):
                    previous = (agent.provider, agent.model)
                    self._replace_model_unchecked(agent.id, route[0], route[1])
                    try:
                        self._save_agent_profile(agent)
                    except Exception:
                        agent.provider, agent.model = previous
                        raise

    @staticmethod
    def _task_summary(task: Task) -> TaskSummary:
        return TaskSummary(
            id=task.id,
            title=task.title,
            description=task.description,
            project_id=task.project_id,
            status=task.status.value,
            result=task.result,
            error=task.error,
            assigned_agent=task.assigned_agent,
            required_role=task.required_role,
            required_capability=task.required_capability,
        )

    @staticmethod
    def _project_summary(project: Project) -> ProjectSummary:
        return ProjectSummary(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
        )
