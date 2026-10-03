from datetime import datetime, timezone

import pytest

from app.application import (
    OrganizationPriority,
    OrganizationWorkflowSource,
    ResponsibilitySelection,
    WorkflowReference,
)
from app.orchestrator import Task, TaskFailureCategory, TaskStatus
from app.runtime.factory import create_corporation_runtime

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def _plan(runtime):
    return runtime.application_service.corporation_planning().build(
        (OrganizationPriority("priority", "Protect reliability", "Caller rationale", ("source-1",)),),
        (),
        now=NOW,
    )


def _failed_maintenance_workflow(runtime):
    runtime.tasks.register(
        Task(
            "failed-task",
            "Failed Task",
            "Existing failed work.",
            status=TaskStatus.FAILED,
            failure_category=TaskFailureCategory.EXECUTION,
        )
    )
    failure = runtime.application_service.detect_failures().failures[0]
    return runtime.application_service.start_maintenance_workflow(failure)


def test_unapproved_workflow_is_not_eligible_for_organization_coordination():
    runtime = create_corporation_runtime()
    workflow = _failed_maintenance_workflow(runtime)
    selection = ResponsibilitySelection(
        "priority",
        "local_employee",
        "General task execution",
        (WorkflowReference(OrganizationWorkflowSource.MAINTENANCE, workflow.workflow_id),),
    )

    with pytest.raises(ValueError, match="no approved exact-patch decision"):
        runtime.application_service.organization_coordination().build(
            _plan(runtime), (selection,), observed_at=NOW
        )


@pytest.mark.parametrize(
    "employee_id, responsibility, error",
    [
        ("missing-employee", "General task execution", "Employee not found"),
        ("local_employee", "Unregistered responsibility", "not registered"),
    ],
)
def test_coordination_requires_registered_responsibility_sources(
    employee_id, responsibility, error
):
    runtime = create_corporation_runtime()
    selection = ResponsibilitySelection(
        "priority",
        employee_id,
        responsibility,
        (WorkflowReference(OrganizationWorkflowSource.MAINTENANCE, "missing-workflow"),),
    )

    with pytest.raises(ValueError, match=error):
        runtime.application_service.organization_coordination().build(
            _plan(runtime), (selection,), observed_at=NOW
        )


def test_coordination_requires_matching_plan_and_configured_employee_registry():
    runtime = create_corporation_runtime()
    other_plan = OrganizationPriority("priority", "Protect reliability", "Caller rationale", ("source-1",))
    from app.application.services.organization_planning import OrganizationPlanningService

    plan = OrganizationPlanningService("another-corporation").build(
        (other_plan,), (), now=NOW
    )
    with pytest.raises(ValueError, match="different Corporation"):
        runtime.application_service.organization_coordination().build(
            plan,
            (
                ResponsibilitySelection(
                    "priority",
                    "local_employee",
                    "General task execution",
                    (WorkflowReference(OrganizationWorkflowSource.MAINTENANCE, "workflow"),),
                ),
            ),
            observed_at=NOW,
        )

    from app.application.services.corporation import CorporationApplicationService

    application = CorporationApplicationService(
        runtime.orchestrator, corporation=runtime.corporation
    )
    runtime.orchestrator.employees = None
    with pytest.raises(RuntimeError, match="Employee registry is not configured"):
        application.organization_coordination()


@pytest.mark.parametrize(
    "construct",
    [
        lambda: WorkflowReference("maintenance", "workflow"),
        lambda: ResponsibilitySelection("p", "e", "work", ()),
        lambda: ResponsibilitySelection("p", "e", "work", ["not a reference"]),
        lambda: ResponsibilitySelection(
            "p",
            "e",
            "work",
            (
                WorkflowReference(OrganizationWorkflowSource.MAINTENANCE, "same"),
                WorkflowReference(OrganizationWorkflowSource.MAINTENANCE, "same"),
            ),
        ),
    ],
)
def test_coordination_inputs_are_explicit_and_bounded(construct):
    with pytest.raises((TypeError, ValueError)):
        construct()
