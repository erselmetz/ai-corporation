from dataclasses import dataclass
from typing import Protocol

from fastapi import Depends, HTTPException, Request

from app.application.services.capability_authorization import (
    CapabilityAuthorizationDenied,
    DEFAULT_CAPABILITY_AUTHORIZATION,
)


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    identity: str
    permissions: frozenset[str]

    def __post_init__(self) -> None:
        if not self.identity.strip():
            raise ValueError("Principal identity cannot be empty")
        if any(not permission.strip() for permission in self.permissions):
            raise ValueError("Principal permissions cannot be empty")


class AuthenticationBackend(Protocol):
    def authenticate(self, request: Request) -> AuthenticatedPrincipal | None:
        """Return the authenticated principal, or None when authentication fails."""
        ...


class RejectingAuthenticationBackend:
    """Secure default until an authentication backend is explicitly configured."""

    def authenticate(self, _request: Request) -> None:
        return None


def require_authenticated_principal(
    request: Request,
) -> AuthenticatedPrincipal:
    backend: AuthenticationBackend = request.app.state.authentication_backend
    principal = backend.authenticate(request)
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal


def require_permission(permission: str):
    if not permission.strip():
        raise ValueError("Permission cannot be empty")

    def dependency(
        request: Request,
        principal: AuthenticatedPrincipal = Depends(require_authenticated_principal),
    ) -> AuthenticatedPrincipal:
        authorizer = getattr(request.app.state, "capability_authorization_service",
                             DEFAULT_CAPABILITY_AUTHORIZATION)
        try:
            authorizer.require(identity=principal.identity, permissions=principal.permissions,
                               capability_id=permission, scope_type="principal",
                               scope_id=principal.identity)
        except CapabilityAuthorizationDenied:
            raise HTTPException(status_code=403, detail="Permission denied")
        return principal

    return dependency
