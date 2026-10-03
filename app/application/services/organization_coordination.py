"""Review-only coordination over registered responsibilities and approved workflow records."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.agents import EmployeeRegistry
from app.approval import ApprovalStatus
from app.memory.models import _identifier, _time
from .capability_integration import (
    CapabilityIntegrationStage,
    CapabilityIntegrationStatus,
    CapabilityIntegrationWorkflowService,
)
from .maintenance_workflow import (
    MaintenanceWorkflowService,
    MaintenanceWorkflowStage,
    MaintenanceWorkflowStatus,
)
from .organization_planning import OrganizationPlan


def _text(value: str, label: str, maximum_bytes: int = 1024) -> None:
    try:
        valid = (
            isinstance(value, str)
            and bool(value.strip())
            and len(value.encode("utf-8")) <= maximum_bytes
        )
    except UnicodeEncodeError:
        valid = False
    if not valid:
        raise ValueError(f"{label} must be nonempty text of at most {maximum_bytes} UTF-8 bytes")


class OrganizationWorkflowSource(str, Enum):
    MAINTENANCE = "maintenance"
    CAPABILITY_INTEGRATION = "capability_integration"


@dataclass(frozen=True, slots=True)
class WorkflowReference:
    source: OrganizationWorkflowSource
    workflow_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, OrganizationWorkflowSource):
            raise TypeError("source must identify a supported workflow registry")
        _identifier(self.workflow_id, "workflow_id")


@dataclass(frozen=True, slots=True)
class ResponsibilitySelection:
    priority_id: str
    employee_id: str
    responsibility: str
    workflows: tuple[WorkflowReference, ...]

    def __post_init__(self) -> None:
        _identifier(self.priority_id, "priority_id")
        _identifier(self.employee_id, "employee_id")
        _text(self.responsibility, "responsibility")
        if not isinstance(self.workflows, tuple) or not 1 <= len(self.workflows) <= 10:
            raise ValueError("A responsibility selection requires 1 to 10 workflow references")
        if not all(isinstance(item, WorkflowReference) for item in self.workflows):
            raise TypeError("Expected WorkflowReference")
        keys = tuple((item.source, item.workflow_id) for item in self.workflows)
        if len(set(keys)) != len(keys):
            raise ValueError("Workflow references must be unique within a responsibility selection")


@dataclass(frozen=True, slots=True)
class CoordinatedWorkflow:
    source: OrganizationWorkflowSource
    workflow_id: str
    status: MaintenanceWorkflowStatus | CapabilityIntegrationStatus
    stage: MaintenanceWorkflowStage | CapabilityIntegrationStage
    approval_status: ApprovalStatus
    approval_request_id: str
    patch_sha256: str
    source_sha256: str
    checkpoint_id: str | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CoordinatedResponsibility:
    priority_id: str
    employee_id: str
    employee_name: str
    employee_role: str
    responsibility: str
    workflows: tuple[CoordinatedWorkflow, ...]


@dataclass(frozen=True, slots=True)
class OrganizationCoordinationReport:
    corporation_id: str
    observed_at: datetime
    plan: OrganizationPlan
    responsibilities: tuple[CoordinatedResponsibility, ...]
    limitations: tuple[str, ...] = (
        "Priority-to-responsibility and responsibility-to-workflow links are caller-selected; fit is not inferred.",
        "Approval status applies to the exact maintenance patch and source hashes, not capability adoption.",
        "Sources are read sequentially; the report is not an atomic cross-registry snapshot.",
        "The report does not schedule, dispatch, or execute work.",
    )


class OrganizationCoordinationService:
    """Summarize explicit responsibility links to current patch-approved workflows."""

    MAX_RESPONSIBILITIES = 100
    MAX_WORKFLOW_REFERENCES = 100

    def __init__(
        self,
        *,
        corporation_id: str,
        employees: EmployeeRegistry,
        maintenance_workflows: MaintenanceWorkflowService,
        capability_workflows: CapabilityIntegrationWorkflowService,
    ) -> None:
        _identifier(corporation_id, "corporation_id")
        if not isinstance(employees, EmployeeRegistry):
            raise TypeError("employees must be an EmployeeRegistry")
        if not isinstance(maintenance_workflows, MaintenanceWorkflowService):
            raise TypeError("maintenance_workflows must be a MaintenanceWorkflowService")
        if not isinstance(capability_workflows, CapabilityIntegrationWorkflowService):
            raise TypeError(
                "capability_workflows must be a CapabilityIntegrationWorkflowService"
            )
        self._corporation_id = corporation_id
        self._employees = employees
        self._maintenance_workflows = maintenance_workflows
        self._capability_workflows = capability_workflows

    def build(
        self,
        plan: OrganizationPlan,
        responsibilities: tuple[ResponsibilitySelection, ...],
        *,
        observed_at: datetime,
    ) -> OrganizationCoordinationReport:
        if not isinstance(plan, OrganizationPlan):
            raise TypeError("Expected OrganizationPlan")
        if plan.corporation_id != self._corporation_id:
            raise ValueError("Plan belongs to a different Corporation")
        _time(observed_at)
        if observed_at < plan.created_at:
            raise ValueError("Observation time precedes the organization plan")
        if not isinstance(responsibilities, tuple) or not (
            1 <= len(responsibilities) <= self.MAX_RESPONSIBILITIES
        ):
            raise ValueError("Supply 1 to 100 explicit responsibility selections")
        if not all(isinstance(item, ResponsibilitySelection) for item in responsibilities):
            raise TypeError("Expected ResponsibilitySelection")
        if sum(len(item.workflows) for item in responsibilities) > self.MAX_WORKFLOW_REFERENCES:
            raise ValueError("Workflow reference count exceeds its limit")

        priority_ids = {item.id for item in plan.priorities}
        linked = set()
        coordinated = []
        for selection in responsibilities:
            if selection.priority_id not in priority_ids:
                raise ValueError("Responsibility selection references an unknown plan priority")
            link_key = (
                selection.priority_id,
                selection.employee_id,
                selection.responsibility,
            )
            if link_key in linked:
                raise ValueError("Duplicate responsibility selection")
            linked.add(link_key)
            employee = self._employees.get(selection.employee_id)
            _text(employee.name, "employee name")
            _text(employee.role, "employee role")
            if selection.responsibility not in employee.responsibilities:
                raise ValueError("Responsibility is not registered to the selected Employee")
            workflows = tuple(self._workflow(reference) for reference in selection.workflows)
            coordinated.append(
                CoordinatedResponsibility(
                    selection.priority_id,
                    employee.id,
                    employee.name,
                    employee.role,
                    selection.responsibility,
                    workflows,
                )
            )

        return OrganizationCoordinationReport(
            self._corporation_id,
            observed_at,
            plan,
            tuple(coordinated),
        )

    def _workflow(self, reference: WorkflowReference) -> CoordinatedWorkflow:
        if reference.source is OrganizationWorkflowSource.MAINTENANCE:
            snapshot = self._maintenance_workflows.get(reference.workflow_id)
            if snapshot.approval_status is not ApprovalStatus.APPROVED:
                raise ValueError("Maintenance workflow has no approved exact-patch decision")
        else:
            snapshot = self._capability_workflows.get(reference.workflow_id)
            if snapshot.approval_status is not ApprovalStatus.APPROVED:
                raise ValueError("Capability workflow has no approved exact-patch decision")
        if (
            snapshot.approval_request_id is None
            or snapshot.patch_sha256 is None
            or snapshot.source_sha256 is None
        ):
            raise ValueError("Approved workflow is missing its exact-patch approval evidence")
        return CoordinatedWorkflow(
            reference.source,
            snapshot.workflow_id,
            snapshot.status,
            snapshot.stage,
            snapshot.approval_status,
            snapshot.approval_request_id,
            snapshot.patch_sha256,
            snapshot.source_sha256,
            snapshot.checkpoint_id,
            snapshot.updated_at,
        )
