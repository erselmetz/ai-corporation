from .models import IntegrationProposal


class IntegrationRegistry:
    """In-memory registry for integration proposals."""

    def __init__(self) -> None:
        self._proposals: dict[str, IntegrationProposal] = {}

    def register(self, proposal: IntegrationProposal) -> None:
        if not isinstance(proposal, IntegrationProposal):
            raise TypeError("Only IntegrationProposal instances can be registered")
        if proposal.id in self._proposals:
            raise ValueError(f"Integration proposal already registered: {proposal.id}")
        self._proposals[proposal.id] = proposal

    def get(self, proposal_id: str) -> IntegrationProposal:
        try:
            return self._proposals[proposal_id]
        except KeyError:
            raise ValueError(f"Integration proposal not found: {proposal_id}")

    def exists(self, proposal_id: str) -> bool:
        return proposal_id in self._proposals

    def all(self) -> list[IntegrationProposal]:
        return list(self._proposals.values())
