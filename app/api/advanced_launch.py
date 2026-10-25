"""Short-lived, one-use loopback bootstrap for the unchanged Advanced pages."""
import secrets
import threading
from typing import Literal
from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict

from .local_access import COOKIE, LocalSession
from .security import require_permission

PAGES = {
    'Employees': '/ui/employees', 'Positions': '/ui/positions', 'Workflows': '/ui/workflows',
    'Backup': '/ui/backup', 'Providers': '/ui/providers', 'Projects': '/ui/projects',
    'Tasks': '/ui/tasks', 'Agents': '/ui/agents', 'Software inventory': '/ui/inventory',
    'Brain settings': '/ui/memory', 'Privacy and capabilities': '/ui/settings/capabilities',
    'Online providers': '/ui/online-provider', 'Provider connections': '/ui/provider-connections',
    'Updates': '/ui/updates', 'Preferences': '/ui/preferences', 'Readiness': '/ui/readiness',
    'Automation': '/ui/automation', 'Structure': '/ui/structure',
}


class LaunchPage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    page: Literal[tuple(PAGES)]


def install_advanced_launch(application, backend):
    tickets = {}
    lock = threading.Lock()

    @application.post('/api/local/advanced-launch')
    def mint(body: LaunchPage, request: Request, principal=Depends(require_permission('chat:read'))):
        session = backend.session(request)
        if session is None:
            raise HTTPException(401, 'Sign in first')
        now = backend.clock()
        with lock:
            for token in list(tickets):
                if tickets[token][2] <= now:
                    del tickets[token]
            if len(tickets) >= 16:
                raise HTTPException(429, 'Too many pending page launches')
            token = secrets.token_urlsafe(32)
            tickets[token] = (session.session_id, PAGES[body.page], now + 30)
        return {'url': backend.origin + '/local/advanced-launch?token=' + token, 'expires_in': 30}

    @application.get('/local/advanced-launch', include_in_schema=False)
    def exchange(request: Request, token: str = ''):
        if not backend.request_allowed(request) or len(token) > 128:
            raise HTTPException(403, 'Page launch denied')
        with lock:
            ticket = tickets.pop(token, None)
        if ticket is None or ticket[2] <= backend.clock():
            raise HTTPException(403, 'Page launch expired; open it again from the app')
        with backend._lock:
            backend._prune()
            if not any(s.session_id == ticket[0] for s in backend._sessions.values()):
                raise HTTPException(403, 'The launching session ended')
            cookie = request.cookies.get(COOKIE)
            if cookie not in backend._sessions:
                if len(backend._sessions) >= backend.MAX_SESSIONS:
                    raise HTTPException(429, 'Session limit reached')
                cookie = secrets.token_urlsafe(32)
                backend._sessions[cookie] = LocalSession(secrets.token_urlsafe(32),
                    backend.clock() + backend.SESSION_SECONDS, secrets.token_urlsafe(24))
        response = RedirectResponse(ticket[1], status_code=303,
            headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
        response.set_cookie(COOKIE, cookie, max_age=backend.SESSION_SECONDS,
                            httponly=True, samesite='strict', path='/')
        return response
