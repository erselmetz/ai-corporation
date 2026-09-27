import pytest

from app.approval import ApprovalRegistry, ApprovalRequest, ApprovalStatus
from app.integrations import (
    IntegrationCapability,
    IntegrationExecutionRecord,
    IntegrationExecutionStatus,
    IntegrationProposal,
    IntegrationRegistry,
    IntegrationSource,
    IntegrationStatus,
)


def make_proposal() -> IntegrationProposal:
    return IntegrationProposal(
        id="proposal-1",
        source=IntegrationSource(
            source_type="github_repository",
            location="https://github.com/example/project",
            project_name="example-project",
        ),
        requested_purpose="Add repository analysis capability",
    )


def advance_to_review(proposal: IntegrationProposal) -> None:
    for status in (
        IntegrationStatus.ANALYZING,
        IntegrationStatus.EVALUATING,
        IntegrationStatus.PROPOSED,
        IntegrationStatus.SANDBOXED,
        IntegrationStatus.TESTED,
        IntegrationStatus.REVIEW_REQUIRED,
    ):
        proposal.transition(status)


def test_integration_proposal_creation_and_source_representation():
    proposal = make_proposal()

    assert proposal.status == IntegrationStatus.DISCOVERED
    assert proposal.source.source_type == "github_repository"
    assert proposal.source.location == "https://github.com/example/project"
    assert proposal.source.project_name == "example-project"
    assert proposal.requested_purpose == "Add repository analysis capability"
    assert proposal.approval_status is None
    assert proposal.created_at.tzinfo is not None
    assert proposal.updated_at.tzinfo is not None

    custom_source = IntegrationSource(
        source_type="future_adapter",
        location="local://workspace/project",
    )
    assert custom_source.source_type == "future_adapter"


@pytest.mark.parametrize(
    ("proposal_id", "purpose", "message"),
    [
        (" ", "Purpose", "id"),
        ("proposal", " ", "purpose"),
    ],
)
def test_integration_proposal_required_fields(proposal_id, purpose, message):
    with pytest.raises(ValueError, match=message):
        IntegrationProposal(
            proposal_id,
            IntegrationSource("git", "repo://example"),
            purpose,
        )


@pytest.mark.parametrize(
    ("source_type", "location", "message"),
    [
        (" ", "repo://example", "type"),
        ("git", " ", "location"),
    ],
)
def test_integration_source_required_fields(source_type, location, message):
    with pytest.raises(ValueError, match=message):
        IntegrationSource(source_type, location)


def test_proposal_lifecycle_transitions_are_controlled():
    proposal = make_proposal()
    proposal.transition(IntegrationStatus.ANALYZING)
    proposal.evaluation_information = "Source appears relevant."
    proposal.transition(IntegrationStatus.EVALUATING)
    proposal.proposed_approach = "Adapt its repository indexing component."
    proposal.risk_information = "External code must remain isolated."
    proposal.transition(IntegrationStatus.PROPOSED)
    proposal.transition(IntegrationStatus.SANDBOXED)
    proposal.transition(IntegrationStatus.TESTED)
    proposal.transition(IntegrationStatus.REVIEW_REQUIRED)

    with pytest.raises(ValueError, match="Invalid integration proposal transition"):
        proposal.transition(IntegrationStatus.INTEGRATED)
    with pytest.raises(AttributeError):
        proposal.status = IntegrationStatus.APPROVED


def test_approval_and_execution_are_separate_gated_states():
    proposal = make_proposal()
    advance_to_review(proposal)
    approvals = ApprovalRegistry()
    approval = ApprovalRequest(
        id="approval-1",
        action=proposal.approval_action,
        context=f"Review integration proposal {proposal.id}",
    )
    approvals.register(approval)
    proposal.attach_approval_request(approval)

    with pytest.raises(PermissionError, match="approved human ApprovalRequest"):
        proposal.transition(IntegrationStatus.APPROVED)
    with pytest.raises(PermissionError, match="approved proposal"):
        IntegrationExecutionRecord.for_approved_proposal("execution-1", proposal)
    with pytest.raises(PermissionError, match="approved proposal"):
        IntegrationExecutionRecord(id="execution-direct", proposal=proposal)

    approvals.approve(approval.id)
    proposal.transition(IntegrationStatus.APPROVED)
    assert proposal.status == IntegrationStatus.APPROVED
    assert proposal.approval_status == ApprovalStatus.APPROVED

    execution = IntegrationExecutionRecord.for_approved_proposal(
        "execution-1",
        proposal,
        frozenset(
            {
                IntegrationCapability.READ_SOURCE,
                IntegrationCapability.RUN_SANDBOX,
            }
        ),
    )
    assert execution.proposal_id == proposal.id
    assert execution.status == IntegrationExecutionStatus.PLANNED
    assert execution.requested_capabilities == frozenset(
        {
            IntegrationCapability.READ_SOURCE,
            IntegrationCapability.RUN_SANDBOX,
        }
    )

    execution.transition(IntegrationExecutionStatus.RUNNING)
    with pytest.raises(PermissionError, match="completed execution record"):
        proposal.transition(IntegrationStatus.INTEGRATED, execution=execution)
    execution.transition(IntegrationExecutionStatus.COMPLETED)
    proposal.transition(IntegrationStatus.INTEGRATED, execution=execution)
    assert proposal.status == IntegrationStatus.INTEGRATED

    with pytest.raises(ValueError, match="Invalid integration execution transition"):
        execution.transition(IntegrationExecutionStatus.FAILED)


def test_rejected_approval_rejects_proposal_and_blocks_execution():
    proposal = make_proposal()
    advance_to_review(proposal)
    approval = ApprovalRequest(
        id="approval-rejected",
        action=proposal.approval_action,
        context=f"Review integration proposal {proposal.id}",
    )
    approvals = ApprovalRegistry()
    approvals.register(approval)
    proposal.attach_approval_request(approval)
    approvals.reject(approval.id)

    assert approval.status == ApprovalStatus.REJECTED
    proposal.transition(IntegrationStatus.REJECTED)
    assert proposal.status == IntegrationStatus.REJECTED
    with pytest.raises(PermissionError, match="approved proposal"):
        IntegrationExecutionRecord.for_approved_proposal("execution-rejected", proposal)


def test_integration_registry_manages_proposals_without_execution():
    registry = IntegrationRegistry()
    proposal = make_proposal()
    registry.register(proposal)

    assert registry.exists(proposal.id)
    assert registry.get(proposal.id) is proposal
    assert registry.all() == [proposal]
    with pytest.raises(ValueError, match="already registered"):
        registry.register(proposal)
