"""Run the explicitly configured single-owner local Web UI."""
import argparse
import getpass
import logging
import secrets

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.app import create_app
from app.api.local_access import COOKIE, LocalOwnerAuthentication


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=1024, repr=False)


LOGIN_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Local sign-in - ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
</head><body><main class="content"><h1>ERSELMETZ AI - Local access</h1>
<p>Sign in with the owner password entered when starting this local app.</p>
<form id="local-login"><label for="password">Owner password</label>
<input id="password" type="password" autocomplete="current-password" required maxlength="1024">
<button type="submit">Sign in</button></form>
<p id="login-state" role="status" aria-live="polite"></p>
<a href="/ui">Dashboard</a> <a href="/ui/chat">Coordinator chat</a> <button id="local-logout" type="button">Sign out</button>
<p>Local mode provides read access and separately authorized coordinator chat. Separate chat-task:create and task:dispatch permissions support reviewed Task proposals and owner-confirmed local dispatch; general task:create remains unavailable. Dispatch requires configured slot budgets and does not use cloud Providers or Tools. Other management actions remain separately authorized.</p>
</main><script type="module" src="/ui/static/local-login.mjs"></script></body></html>"""


def create_local_app(*, password: str, origin: str = "http://127.0.0.1:8000",
                     application_service=None, clock=None):
    backend = LocalOwnerAuthentication(password, origin, **({"clock": clock} if clock else {}))
    application = create_app(application_service=application_service,
                             authentication_backend=backend)
    from app.api.local_models import router as local_models_router
    application.include_router(local_models_router)
    from app.api.assignment_policy import router as assignment_policy_router
    application.include_router(assignment_policy_router)
    from app.api.local_online_provider import create_local_online_provider_router
    from app.integrations.gemini_chat import GeminiConnectionManager
    connection_manager = GeminiConnectionManager()
    application.state.gemini_connection_manager = connection_manager
    application.state.local_online_provider = None
    application.include_router(create_local_online_provider_router(connection_manager))
    from app.api.provider_connections import router as provider_connections_router
    application.include_router(provider_connections_router)
    from app.api.workflows import router as workflows_router
    application.include_router(workflows_router)

    @application.middleware("http")
    async def protect_local_request(request: Request, call_next):
        if not backend.request_allowed(request):
            return JSONResponse({"detail": "Local request denied"}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin") != backend.origin:
                return JSONResponse({"detail": "Same-origin request required"}, status_code=403)
            # JSON login has no existing session. All other writes require CSRF.
            if request.url.path != "/api/local/login":
                try:
                    backend.require_csrf(request)
                except HTTPException as error:
                    return JSONResponse({"detail": error.detail}, status_code=error.status_code)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"detail": "JSON request required"}, status_code=415)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        return response

    @application.exception_handler(422)
    async def sanitized_validation(_request, _error):
        return JSONResponse({"detail": "Invalid request fields"}, status_code=422)

    @application.get("/ui/login", response_class=HTMLResponse)
    def login_page():
        return LOGIN_HTML

    @application.post("/api/local/login")
    async def login(request: Request):
        payload = bytearray()
        async for chunk in request.stream():
            if len(payload) + len(chunk) > 8192:
                raise HTTPException(413, "Sign-in request too large")
            payload.extend(chunk)
        try:
            body = LoginRequest.model_validate_json(bytes(payload))
        except ValueError:
            raise HTTPException(422, "Invalid request fields") from None
        token = backend.login(body.password)
        response = JSONResponse({"signed_in": True})
        response.set_cookie(COOKIE, token, max_age=backend.SESSION_SECONDS,
                            httponly=True, samesite="strict", path="/")
        return response

    @application.get("/api/local/session")
    def session(request: Request):
        record = backend.session(request)
        if record is None:
            raise HTTPException(401, "Authentication required")
        return {"identity": backend.principal.identity,
                "permissions": sorted(backend.principal.permissions), "csrf": record.csrf}

    @application.post("/api/local/logout")
    def logout(request: Request):
        backend.logout(request)
        response = JSONResponse({"signed_in": False})
        response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
        return response

    return application


def main():
    parser = argparse.ArgumentParser(description="Local ERSELMETZ AI owner Web UI")
    parser.add_argument("--port", type=int, default=8000)
    options = parser.parse_args()
    if not 1 <= options.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    password = getpass.getpass("Choose owner password for this run (12+ characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if not secrets.compare_digest(password.encode("utf-8"), confirmation.encode("utf-8")):
        parser.error("Passwords do not match")
    application = create_local_app(password=password,
                                   origin=f"http://127.0.0.1:{options.port}")
    del password, confirmation
    import uvicorn
    logging.getLogger("uvicorn").info("Local sign-in: http://127.0.0.1:%s/ui/login", options.port)
    print(f"Open http://127.0.0.1:{options.port}/ui/login - Ctrl+C stops the local app")
    uvicorn.run(application, host="127.0.0.1", port=options.port,
                proxy_headers=False, workers=1)


if __name__ == "__main__":
    main()
