"""Run the explicitly configured single-owner local Web UI."""
import argparse
import getpass
import logging
import os
from pathlib import Path
import secrets
import threading
from datetime import datetime, timezone
import time

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.app import create_app
from app.api.local_access import COOKIE, LocalOwnerAuthentication


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=1024, repr=False)


class DesktopLockRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    password: str = Field(min_length=12, max_length=1024, repr=False)
    confirmation: str | None = Field(default=None, max_length=1024, repr=False)


LOGIN_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Owner sign-in — ERSELMETZ AI</title><link rel="stylesheet" href="/ui/static/style.css">
</head><body><main class="content login-content"><p class="eyebrow">YOUR LOCAL WORKSPACE</p><h1>Sign in to ERSELMETZ AI</h1>
<p>Use the owner password created when this app was first set up. Sign-in unlocks the pages and chat allowed for this local session.</p>
<form id="local-login"><label for="password">Owner password</label>
<input id="password" type="password" autocomplete="current-password" required maxlength="1024">
<button type="submit">Sign in</button></form>
<p id="login-state" role="status" aria-live="polite"></p>
<p class="login-links"><a href="/ui">Home</a><a href="/ui/chat">Chat</a><button id="local-logout" type="button">Sign out</button></p>
</main><script type="module" src="/ui/static/local-login.mjs"></script></body></html>"""


def create_local_app(*, password: str | None, origin: str = "http://127.0.0.1:8000", desktop_session_token: str | None = None,
                     application_service=None, clock=None, desktop_ui_dir=None,
                     desktop_mode: bool = False,
                     first_owner_run: bool = False,
                     voice_connection_manager=None, capability_authorization_service=None,
                     capability_grant_service=None, capability_audit_service=None,
                     emergency_stop_service=None, local_speech_provider=None,
                     data_portability_service=None, speech_model_catalog=None):
    if desktop_session_token is not None and desktop_mode is not True:
        raise ValueError("Passwordless session tokens are restricted to the desktop runtime")
    startup_started = time.perf_counter()
    app_started_at = datetime.now(timezone.utc)
    backend = LocalOwnerAuthentication(
        password, origin, startup_token=desktop_session_token, **({"clock": clock} if clock else {}),
        **({"capability_authorization_service": capability_authorization_service}
           if capability_authorization_service is not None else {}),
        **({"capability_grant_service": capability_grant_service}
           if capability_grant_service is not None else {}))
    if emergency_stop_service is None:
        from app.application.services.emergency_stop import EmergencyStopService
        emergency_stop_service = EmergencyStopService()
    application = create_app(application_service=application_service,
                             authentication_backend=backend,
                             capability_authorization_service=backend.capability_authorization_service,
                             capability_grant_service=backend.capability_grant_service,
                             capability_audit_service=capability_audit_service,
                             emergency_stop_service=emergency_stop_service,
                             with_builtin_agent_team=application_service is None)
    application.state.local_automation_registry_lock = threading.Lock()
    from app.application.services.owner_preferences import OwnerPreferencesService
    application.state.owner_preferences_service = OwnerPreferencesService()
    from app.api.local_preferences import router as local_preferences_router
    application.include_router(local_preferences_router)
    from app.application.services.owner_suggestions import OwnerSuggestionService
    application.state.owner_suggestion_service = OwnerSuggestionService()
    from app.api.local_suggestions import router as local_suggestions_router
    application.include_router(local_suggestions_router)
    from app.api.emergency_stop import create_emergency_stop_router
    application.include_router(create_emergency_stop_router())
    from app.api.local_models import router as local_models_router
    application.include_router(local_models_router)
    from app.api.assignment_policy import router as assignment_policy_router
    application.include_router(assignment_policy_router)
    from app.api.local_online_provider import create_local_online_provider_router
    from app.integrations.gemini_chat import GeminiConnectionManager
    connection_manager = voice_connection_manager or GeminiConnectionManager()
    application.state.gemini_connection_manager = connection_manager
    application.state.local_online_provider = None
    application.state.first_run_enabled = desktop_mode is True
    application.state.first_run_setup_store = None
    application.state.first_run_ollama_service = None
    application.state.first_run_secret_store = None
    application.state.first_run_reconnect_required = False
    if desktop_mode is True:
        from app.api.first_run import router as first_run_router
        from app.application.services.first_run_setup import FirstRunSetupStore, OllamaFirstRunService
        from app.local_owner_secret import LocalOwnerSecretStore, LocalOwnerSecretError

        setup_store = FirstRunSetupStore()
        application.state.first_run_setup_store = setup_store
        application.state.first_run_ollama_service = OllamaFirstRunService()
        try:
            application.state.first_run_secret_store = LocalOwnerSecretStore()
        except LocalOwnerSecretError:
            application.state.first_run_secret_store = None

        def restore_local_first_run(corporation):
            setup_store.initialize_for_new_owner(first_owner_run=first_owner_run is True)
            application.state.quick_setup_ready = False
            config = setup_store.get()
            if config is None:
                return
            try:
                if config.provider_type in {None, "none", "ollama"}:
                    ollama_setup = application.state.first_run_ollama_service
                    inventory = ollama_setup._provider.local_model_inventory()
                    if config.model_id:
                        model_id = config.model_id
                    else:
                        choices = ollama_setup.default_installed_chat_model()
                        model_id = choices[0] if choices else (config.model_id or OllamaFirstRunService.MODEL_ID)
                    replace_model = corporation.replace_model
                    if callable(getattr(corporation, "apply_builtin_default_routes", None)):
                        replace_model("local_worker", "ollama", model_id, manual=False)
                    else:
                        replace_model("local_worker", "ollama", model_id)
                    installed_and_selected = inventory.state == "available" and model_id in inventory.models
                    if installed_and_selected:
                        setup_store.complete_ollama(model_id)
                    limits_provider = "ollama"
                    limits_model = model_id
                elif config.provider_type == "gemini" and config.model_id:
                    if not config.completed:
                        return
                    secret_store = application.state.first_run_secret_store
                    credential = secret_store.load() if secret_store is not None else None
                    if not config.gemini_key_persisted or credential is None:
                        application.state.first_run_reconnect_required = True
                        return
                    connection_manager.restore_from_owner_configuration(
                        credential, config.gemini_models,
                    )
                    from app.application.services.local_online_provider import LocalOnlineProviderService
                    online = LocalOnlineProviderService(corporation, connection_manager)
                    application.state.local_online_provider = online
                    agent = corporation.get_agent("local_worker")
                    online.connect_from_discovery(
                        "local_worker", config.model_id,
                        expected_provider_id=agent.provider,
                        expected_model_id=agent.model,
                    )
                    limits_provider = "gemini"
                    limits_model = config.model_id
                    try:
                        ollama_inventory = application.state.first_run_ollama_service._provider.local_model_inventory()
                    except Exception:
                        ollama_inventory = None
                    del credential
                else:
                    application.state.first_run_reconnect_required = True
                    return
                apply_default_routes = getattr(corporation, "apply_builtin_default_routes", None)
                if callable(apply_default_routes):
                    available_models = (inventory.models if config.provider_type in {None, "none", "ollama"}
                                        and inventory.state == "available" else
                                        ollama_inventory.models if config.provider_type == "gemini"
                                        and ollama_inventory is not None
                                        and ollama_inventory.state == "available" else ())
                    apply_default_routes(limits_provider, limits_model, available_models)
                from app.resources import ModelLimit, ProviderLimit, ResourceLimits
                if config.provider_type == "gemini" or config.completed or installed_and_selected:
                    configure_agent_slots = getattr(corporation, "configure_agent_slots", None)
                    if callable(configure_agent_slots):
                        configure_agent_slots(global_slots=1)
                    else:
                        limits = ResourceLimits(
                            global_slots=config.global_slots,
                            providers=(ProviderLimit(limits_provider, config.provider_slots),),
                            models=(ModelLimit(limits_provider, limits_model, config.model_slots),),
                        )
                        corporation.resource_manager(limits)
                    application.state.quick_setup_ready = True
                application.state.first_run_reconnect_required = False
            except Exception:
                application.state.first_run_reconnect_required = True

        application.state.restore_local_first_run = restore_local_first_run
        application.include_router(first_run_router)
    application.include_router(create_local_online_provider_router(connection_manager))
    from app.api.local_voice import create_local_voice_router
    app_data = (Path(os.environ["LOCALAPPDATA"]) / "ERSELMETZ AI"
                if os.environ.get("LOCALAPPDATA") else
                Path.home() / ".local" / "share" / "ERSELMETZ AI")
    if local_speech_provider is None:
        from app.integrations.local_speech import FasterWhisperLocalProvider
        local_speech_provider = FasterWhisperLocalProvider(app_data / "speech-models")
    from app.integrations.local_speech_model import LocalSpeechModelCatalog
    speech_model_catalog = speech_model_catalog or LocalSpeechModelCatalog(
        getattr(local_speech_provider, "model_root", app_data / "speech-models"))
    from app.api.capability_packs import router as capability_packs_router
    from app.integrations.capability_packs import OptionalMediaPacks
    from app.integrations.local_tts import LocalPyttsx3Output
    media_packs = OptionalMediaPacks()
    local_speech_output = LocalPyttsx3Output(on_success=lambda: media_packs.mark_working("voice"))
    application.state.media_capability_packs = media_packs
    application.state.local_speech_output = local_speech_output
    application.state.local_speech_provider = local_speech_provider
    application.state.speech_model_catalog = speech_model_catalog
    application.include_router(create_local_voice_router(connection_manager,
                                                         local_speech=local_speech_provider,
                                                         speech_model_catalog=speech_model_catalog,
                                                         media_packs=media_packs,
                                                         local_output=local_speech_output))
    application.include_router(capability_packs_router)
    from app.api.local_automation import router as local_automation_router
    application.include_router(local_automation_router)
    from app.api.provider_connections import router as provider_connections_router
    application.include_router(provider_connections_router)
    from app.api.agent_profiles import router as agent_profiles_router, status_router as agent_status_router
    application.include_router(agent_profiles_router)
    application.include_router(agent_status_router)
    from app.api.inventory import router as inventory_router
    application.include_router(inventory_router)
    from app.api.managed_software import router as managed_software_router
    application.include_router(managed_software_router)
    from app.api.workflows import router as workflows_router
    application.include_router(workflows_router)
    from app.api.data_portability import router as data_portability_router
    if data_portability_service is None:
        from app.database.connection import DATABASE_PATH
        from app.portability.backups import DataPortabilityService
        data_portability_service = DataPortabilityService(DATABASE_PATH)
    application.state.data_portability_service = data_portability_service
    application.state.data_restore_requires_restart = False
    application.include_router(data_portability_router)
    from app.api.local_readiness import router as local_readiness_router
    application.state.local_app_started_at = app_started_at
    application.include_router(local_readiness_router)

    @application.middleware("http")
    async def protect_local_request(request: Request, call_next):
        if not backend.request_allowed(request):
            return JSONResponse({"detail": "Local request denied"}, status_code=403)
        if (application.state.data_restore_requires_restart
                and request.url.path.startswith("/api/")
                and request.url.path not in {"/api/health", "/api/local/logout"}):
            return JSONResponse({"detail": "Application data was restored. Restart ERSELMETZ AI before using the API."},
                                status_code=503)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin") != backend.origin:
                return JSONResponse({"detail": "Same-origin request required"}, status_code=403)
            # JSON login has no existing session. All other writes require CSRF.
            if request.url.path != "/api/local/login":
                try:
                    backend.require_csrf(request)
                except HTTPException as error:
                    return JSONResponse({"detail": error.detail}, status_code=error.status_code)
            content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
            voice_upload = (request.url.path in {"/api/local/voice/transcribe",
                                                 "/api/local/voice/transcribe-local"}
                            and content_type == "audio/wav")
            backup_upload = (request.url.path in {"/api/local/backup/inspect", "/api/local/backup/restore"}
                             and content_type == "multipart/form-data")
            knowledge_upload = (request.url.path == "/api/memory/owner/upload"
                                and content_type == "multipart/form-data")
            if backup_upload:
                from app.portability.backups import MAX_BACKUP_BYTES
                content_length = request.headers.get("content-length", "")
                if not content_length.isdecimal() or int(content_length) > MAX_BACKUP_BYTES + 1024 * 1024:
                    return JSONResponse({"detail": "Backup request exceeds the supported size"}, status_code=413)
            if knowledge_upload:
                content_length = request.headers.get("content-length", "")
                if not content_length.isdecimal() or int(content_length) > 1_048_576 + 16_384:
                    return JSONResponse({"detail": "Knowledge upload exceeds the 1 MiB file limit"}, status_code=413)
            if content_type != "application/json" and not voice_upload and not backup_upload and not knowledge_upload:
                return JSONResponse({"detail": "JSON request required"}, status_code=415)
            stopped = application.state.emergency_stop_service.stopped
            allowed_while_stopped = (
                request.url.path in {"/api/local/emergency-stop/stop", "/api/local/emergency-stop/resume",
                                     "/api/local/logout"}
                or (request.url.path.startswith("/api/capabilities/grants/")
                    and request.url.path.endswith("/revoke"))
            )
            if stopped and not allowed_while_stopped:
                return JSONResponse({"detail": "Emergency stop is active; new protected actions are blocked"},
                                    status_code=423)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "microphone=(self), camera=(self), display-capture=(self), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        return response

    @application.middleware("http")
    async def shared_local_navigation(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path != "/ui" and not path.startswith("/ui/"):
            return response
        if path == "/ui/chat":
            return response
        if not response.headers.get("content-type", "").lower().startswith("text/html"):
            return response
        body = getattr(response, "body", None)
        if not isinstance(body, bytes):
            body_parts = []
            async for chunk in response.body_iterator:
                body_parts.append(chunk)
            body = b"".join(body_parts)

        import re
        from app.webui.router import _navigation

        try:
            html = body.decode("utf-8")
        except UnicodeDecodeError:
            return response
        if re.search(r"<body\b[^>]*>", html, re.IGNORECASE) is None:
            return response

        # Replace page-local copies with one shared navigation shell so every
        # Python UI route, including post-wizard chat, has the same navigation.
        html = re.sub(
            r'<nav class="navigation" aria-label="Main navigation">.*?</nav>',
            "", html, count=1, flags=re.IGNORECASE | re.DOTALL,
        )
        navigation = _navigation(path, desktop_settings_available=desktop_ui_dir is not None).replace(
            '<nav class="navigation"',
            '<nav id="shared-navigation" class="navigation shared-navigation"', 1,
        )
        menu = ('<button id="shared-navigation-toggle" class="navigation-toggle" '
                'type="button" aria-controls="shared-navigation" aria-expanded="false">Menu</button>')
        module = '<script type="module" src="/ui/static/navigation.mjs"></script>'
        markup = menu + navigation + module

        def add_body_class(match):
            attributes = match.group(1)
            class_match = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', attributes, re.IGNORECASE)
            if class_match:
                value = class_match.group(2)
                attributes = (attributes[:class_match.start(2)] + value + " has-shared-navigation"
                              + attributes[class_match.end(2):])
            else:
                attributes += ' class="has-shared-navigation"'
            return "<body" + attributes + ">"

        html = re.sub(r"<body\b([^>]*)>", add_body_class, html, count=1, flags=re.IGNORECASE)
        html = re.sub(r"(<body\b[^>]*>)", lambda match: match.group(1) + markup,
                      html, count=1, flags=re.IGNORECASE)
        headers = {key: value for key, value in response.headers.items()
                   if key.lower() not in {"content-length", "content-type"}}
        return HTMLResponse(html, status_code=response.status_code, headers=headers)

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

    if desktop_mode:
        @application.get("/api/local/desktop-lock")
        def desktop_lock_state(request: Request):
            if backend.authenticate(request) is None:
                raise HTTPException(401, "Authentication required")
            from app.local_owner_credential import LocalOwnerCredentialStore
            return {"enabled": LocalOwnerCredentialStore().exists()}

        @application.post("/api/local/desktop-lock")
        async def update_desktop_lock(request: Request):
            principal = backend.authenticate(request)
            if principal is None or "owner-lock:manage" not in principal.permissions:
                raise HTTPException(403, "Permission denied")
            backend.require_csrf(request)
            payload = bytearray()
            async for chunk in request.stream():
                if len(payload) + len(chunk) > 4096:
                    raise HTTPException(413, "Password setting request too large")
                payload.extend(chunk)
            try:
                body = DesktopLockRequest.model_validate_json(bytes(payload))
            except ValueError:
                raise HTTPException(422, "Invalid password setting") from None
            from app.local_owner_credential import LocalOwnerCredentialStore, OwnerCredentialError
            store = LocalOwnerCredentialStore()
            try:
                if body.enabled:
                    if not isinstance(body.confirmation, str):
                        raise HTTPException(422, "Confirm the new owner password")
                    store.create(body.password, body.confirmation)
                else:
                    store.remove(body.password)
            except OwnerCredentialError as error:
                raise HTTPException(409, str(error)) from None
            return {"enabled": body.enabled}

    if desktop_ui_dir is not None:
        import base64
        import hashlib
        import re
        from fastapi.staticfiles import StaticFiles

        static_root = Path(desktop_ui_dir).resolve(strict=True)
        if not static_root.is_dir() or not (static_root / "index.html").is_file():
            raise ValueError("The exported desktop UI is unavailable")
        script_hashes = {}
        script_pattern = re.compile(rb"<script\b([^>]*)>(.*?)</script\s*>", re.I | re.S)
        for page in static_root.rglob("*.html"):
            relative = page.relative_to(static_root).as_posix()
            route = "/desktop/" if relative == "index.html" else "/desktop/" + relative[:-10].rstrip("/") + "/"
            hashes = []
            try:
                source = page.read_bytes()
            except OSError:
                raise ValueError("The exported desktop UI could not be read") from None
            for match in script_pattern.finditer(source):
                if re.search(rb"\bsrc\s*=", match.group(1), re.I):
                    continue
                digest = base64.b64encode(hashlib.sha256(match.group(2)).digest()).decode("ascii")
                hashes.append(f"'sha256-{digest}'")
            script_hashes[route] = " ".join(hashes)

        application.mount("/desktop", StaticFiles(directory=str(static_root), html=True),
                          name="desktop-static-ui")

        # Keep Next's statically generated bootstrap scripts under strict CSP by
        # authorizing only the exact hashes from the packaged HTML documents.
        @application.middleware("http")
        async def desktop_static_script_csp(request: Request, call_next):
            response = await call_next(request)
            route = request.url.path
            if route == "/desktop":
                route = "/desktop/"
            elif route.startswith("/desktop/") and not route.endswith("/") and "." not in route.rsplit("/", 1)[-1]:
                route += "/"
            hashes = script_hashes.get(route)
            if hashes:
                response.headers["Content-Security-Policy"] = (
                    "default-src 'self'; script-src 'self' " + hashes + "; "
                    "style-src 'self'; img-src 'self' data:; object-src 'none'; "
                    "base-uri 'none'; frame-ancestors 'none'")
            return response

    application.state.local_startup_setup_ms = max(0.0, (time.perf_counter() - startup_started) * 1000)
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
