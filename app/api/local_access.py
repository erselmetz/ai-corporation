"""Explicit single-owner loopback access; never enabled by the default API."""
from dataclasses import dataclass, field
import hashlib
import hmac
import secrets
import threading
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from .security import AuthenticatedPrincipal

COOKIE = "ersel_local_session"
READ_PERMISSIONS = frozenset({
    "corporation:read", "employee:read", "agent:read", "provider:read",
    "provider-connection:read",
    "model:read", "task:read", "project:read", "activity:read",
    "documentation:read", "updates:read", "memory:read",
    "position:read", "github:read",
    "assignment-policy:read",
})

CHAT_PERMISSIONS = frozenset({"chat:read", "chat:start", "chat:send", "chat:close"})
LOCAL_MODEL_PERMISSIONS = frozenset({"local-model:select"})
ONLINE_PROVIDER_PERMISSIONS = frozenset({"online-provider:connect", "online-provider:disconnect"})
POSITION_MANAGEMENT_PERMISSIONS = frozenset({"position:manage"})
EMPLOYEE_CHAT_PERMISSIONS = frozenset({
    "employee-chat:read", "employee-chat:start",
    "employee-chat:send", "employee-chat:close",
})
ASSIGNMENT_POLICY_PERMISSIONS = frozenset({"assignment-policy:manage"})
PROVIDER_CONNECTION_MANAGEMENT_PERMISSIONS = frozenset({"provider-connection:manage"})
MODEL_RUNTIME_PERMISSIONS = frozenset({"model-runtime:manage"})
CHAT_TASK_PERMISSIONS = frozenset({"chat-task:create"})
CHAT_HISTORY_PERMISSIONS = frozenset({"chat-history:manage"})
CHAT_KNOWLEDGE_PERMISSIONS = frozenset({"chat-knowledge:retain", "chat-knowledge:withdraw"})
TASK_DISPATCH_PERMISSIONS = frozenset({"task:dispatch"})
WORKFLOW_PERMISSIONS = frozenset({"workflow:read", "workflow:manage"})


@dataclass(frozen=True)
class LocalSession:
    csrf: str = field(repr=False)
    expires: float


class LocalOwnerAuthentication:
    SESSION_SECONDS = 3600
    MAX_SESSIONS = 8
    MAX_FAILURES = 5
    LOCKOUT_SECONDS = 300

    def __init__(self, password: str, origin: str, *, clock=time.monotonic):
        if not isinstance(password, str) or not 12 <= len(password) <= 1024:
            raise ValueError("Local password must contain 12 to 1024 characters")
        endpoint = urlsplit(origin)
        if (endpoint.scheme != "http" or endpoint.hostname not in {"127.0.0.1", "localhost"}
                or endpoint.username or endpoint.password or endpoint.path
                or endpoint.query or endpoint.fragment or not endpoint.port
                or origin != f"http://{endpoint.hostname}:{endpoint.port}"):
            raise ValueError("Local origin must be an explicit loopback HTTP origin with a port")
        self.origin = origin
        self.authority = endpoint.netloc
        self.clock = clock
        self._salt = secrets.token_bytes(32)
        self._digest = self._hash(password)
        self._sessions: dict[str, LocalSession] = {}
        self._failures: list[float] = []
        self._lock = threading.RLock()
        self.principal = AuthenticatedPrincipal(
            "local-owner", READ_PERMISSIONS | CHAT_PERMISSIONS
            | LOCAL_MODEL_PERMISSIONS | ONLINE_PROVIDER_PERMISSIONS
            | POSITION_MANAGEMENT_PERMISSIONS | EMPLOYEE_CHAT_PERMISSIONS
            | ASSIGNMENT_POLICY_PERMISSIONS | CHAT_TASK_PERMISSIONS | CHAT_KNOWLEDGE_PERMISSIONS | CHAT_HISTORY_PERMISSIONS
            | TASK_DISPATCH_PERMISSIONS | PROVIDER_CONNECTION_MANAGEMENT_PERMISSIONS
            | MODEL_RUNTIME_PERMISSIONS | WORKFLOW_PERMISSIONS)

    def _hash(self, password: str) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), self._salt, 600_000)

    def request_allowed(self, request: Request) -> bool:
        return (request.client is not None and request.client.host in {"127.0.0.1", "::1"}
                and request.headers.get("host") == self.authority
                and request.url.scheme == "http"
                and request.headers.get("origin", self.origin) == self.origin)

    def _prune(self):
        now = self.clock()
        self._sessions = {key: session for key, session in self._sessions.items()
                          if session.expires > now}
        self._failures = [stamp for stamp in self._failures
                          if stamp > now - self.LOCKOUT_SECONDS]

    def login(self, password: str) -> str:
        with self._lock:
            self._prune()
            if len(self._failures) >= self.MAX_FAILURES:
                raise HTTPException(429, "Too many sign-in attempts; try again later")
            if not hmac.compare_digest(self._hash(password), self._digest):
                self._failures.append(self.clock())
                raise HTTPException(401, "Invalid credentials")
            if len(self._sessions) >= self.MAX_SESSIONS:
                raise HTTPException(429, "Session limit reached; sign out another session")
            token = secrets.token_urlsafe(32)
            self._sessions[token] = LocalSession(secrets.token_urlsafe(32),
                                                 self.clock() + self.SESSION_SECONDS)
            return token

    def session(self, request: Request) -> LocalSession | None:
        if not self.request_allowed(request):
            return None
        with self._lock:
            self._prune()
            return self._sessions.get(request.cookies.get(COOKIE, ""))

    def authenticate(self, request: Request):
        return self.principal if self.session(request) is not None else None

    def require_csrf(self, request: Request):
        session = self.session(request)
        if session is None:
            raise HTTPException(401, "Authentication required")
        if not hmac.compare_digest(request.headers.get("x-local-csrf", "").encode("utf-8"),
                                   session.csrf.encode("ascii")):
            raise HTTPException(403, "Invalid request verification")

    def logout(self, request: Request):
        with self._lock:
            self._sessions.pop(request.cookies.get(COOKIE, ""), None)
