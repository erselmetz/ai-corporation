from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING
from uuid import uuid4

from app.agents import Agent, Employee, EmployeeManagement, EmployeeRegistry, ModelManagement
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


class CorporationApplicationService:
    """Interface-neutral use cases coordinating existing Corporation services."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        corporation: Corporation | None = None,
        node: Node | None = None,
        *,
        tool_registry: ToolRegistry | None = None,
    ):
        if tool_registry is not None and not isinstance(tool_registry, ToolRegistry):
            raise TypeError("tool_registry must be a ToolRegistry or None")
        self._orchestrator = orchestrator
        employees = getattr(orchestrator, "employees", None)
        self._positions = PositionRegistry(
            employees if isinstance(employees, EmployeeRegistry) else None
        )
        self._tool_registry = tool_registry
        self._corporation_chat = None
        self._owned_chat = None
        self._owned_chat_lock = Lock()
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
        self._corporation = corporation
        self._node = node

    def assess_model_resources(self, candidates):
        from app.resources.assessment import assess_model_resources
        snapshot = self._resource_manager.snapshot() if self._resource_manager is not None else None
        return assess_model_resources(candidates, snapshot=snapshot,
                                      registered_providers=self._orchestrator.providers.all())

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
    ) -> GitCheckpoint:
        return self._git_checkpoints.create(workspace_id, created_by=created_by)

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

    def execute_controlled_task(self, task_id):
        self.resource_manager()  # Reject missing configuration before touching Tasks.
        return self._task_summary(self._controlled_execution.execute(task_id))

    def execution_queue(self):
        if self._corporation is None:
            raise RuntimeError("Corporation identity is not configured")
        return self._orchestrator.execution_queue(self._corporation.id)

    def resource_manager(self, limits=None):
        from app.resources import ResourceManager
        if self._resource_manager is None:
            if limits is None:
                raise RuntimeError("Resource limits are not configured")
            self._resource_manager = ResourceManager(limits, self._orchestrator.providers)
            from .controlled_execution import ControlledExecution
            self._controlled_execution = ControlledExecution(self._orchestrator, self._resource_manager)
        elif limits is not None:
            raise ValueError("Resource manager is already configured")
        return self._resource_manager

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
        return ContextRetrievalService(self.memory_management())

    def memory_management(self):
        from .memory_management import MemoryManagementService
        return MemoryManagementService(self._orchestrator, self._corporation.id if self._corporation else None)

    def corporation_knowledge(self):
        if self._corporation is None:
            raise RuntimeError("Corporation runtime identity is not configured")
        from .corporation_knowledge import CorporationKnowledgeService
        return CorporationKnowledgeService(self._corporation.id, self._orchestrator)

    def project_knowledge(self):
        from .project_knowledge import ProjectKnowledgeService
        return ProjectKnowledgeService(self._orchestrator)

    def owned_chat(self):
        """Separate principal-owned HTTP chat facade, safely constructed once."""
        with self._owned_chat_lock:
            if self._owned_chat is None:
                if self._corporation is None:
                    raise ValueError("Corporation identity is required")
                from .corporation_chat import CorporationChatService
                from .owned_chat import OwnedChatService
                self._owned_chat = OwnedChatService(
                    CorporationChatService(self._corporation.id, self._orchestrator),
                    self.get_agent, self.get_provider)
            return self._owned_chat

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

    def register_local_provider(self, provider_id: str, provider) -> None:
        self._orchestrator.providers.register(provider_id, provider)

    def remove_local_provider(self, provider_id: str) -> None:
        self._orchestrator.providers.remove(provider_id)

    def select_local_model(self, agent_id: str, provider_id: str, model_id: str):
        from .owned_chat import ChatConflict, ChatUnavailable
        with self.owned_chat().configuration_change(agent_id):
            agent = self.get_agent(agent_id)
            if agent.provider != provider_id:
                raise ChatConflict("Coordinator provider changed; refresh inventory")
            inventory = self.local_model_inventory(provider_id)
            if not inventory.supported or inventory.state != "available":
                raise ChatUnavailable("Installed-model inventory unavailable; check the local provider")
            if model_id not in inventory.models:
                raise ChatConflict("Selected model is no longer installed; refresh inventory")
            return self.replace_model(agent_id, provider_id, model_id)

    def replace_model(
        self,
        agent_id: str,
        provider_id: str,
        model: str,
    ) -> ModelAssignmentSummary:
        agent = self._model_management().replace_model(
            agent_id,
            provider_id,
            model,
        )
        return ModelAssignmentSummary(
            agent_id=agent.id,
            provider_id=agent.provider,
            model_id=agent.model,
        )

    def assign_model(
        self,
        agent_id: str,
        provider_id: str,
        model: str,
    ) -> AgentSummary:
        agent = self._model_management().assign_model(agent_id, provider_id, model)
        return AgentSummary(
            id=agent.id,
            name=agent.name,
            role=agent.role,
            provider=agent.provider,
            model=agent.model,
            capabilities=tuple(agent.capabilities),
        )

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
