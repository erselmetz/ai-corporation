from .models import Corporation

class CorporationRegistry:
    """
    Registry for managing Corporation identities.
    """
    def __init__(self):
        self._corporations: dict[str, Corporation] = {}

    def register(self, corporation: Corporation) -> None:
        """Registers a corporation identity."""
        if not isinstance(corporation, Corporation):
            raise TypeError("Only Corporation instances can be registered")
        
        if corporation.id in self._corporations:
            raise ValueError(f"Corporation already registered: {corporation.id}")
            
        self._corporations[corporation.id] = corporation

    def get(self, corporation_id: str) -> Corporation:
        """Retrieves a corporation by its ID."""
        try:
            return self._corporations[corporation_id]
        except KeyError:
            raise ValueError(f"Corporation not found: {corporation_id}")

    def exists(self, corporation_id: str) -> bool:
        """Checks if a corporation identity exists."""
        return corporation_id in self._corporations

    def all(self) -> list[Corporation]:
        """Returns all registered corporations."""
        return list(self._corporations.values())
