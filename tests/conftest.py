import os
import socket
from urllib.parse import urlsplit

import pytest

from app.database import initialize_database
from app.database import connection as database_connection


@pytest.fixture
def require_ollama_service():
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    endpoint = urlsplit(base_url)
    if not endpoint.hostname:
        pytest.fail("OLLAMA_BASE_URL must contain a host")
    port = endpoint.port or (443 if endpoint.scheme == "https" else 80)
    try:
        with socket.create_connection((endpoint.hostname, port), timeout=0.5):
            pass
    except OSError as exc:
        pytest.skip(
            f"Ollama is unavailable at {endpoint.hostname}:{port}: {exc}"
        )
    from app.providers import OllamaProvider
    provider = OllamaProvider(base_url)
    inventory = provider.local_model_inventory()
    assert inventory.state == "available", "Live integration requires a bounded local model inventory"
    requested = os.environ.get("OLLAMA_TEST_MODEL")
    candidates = [name for name in inventory.models
                  if not name.casefold().endswith((":cloud", "-cloud"))
                  and not name.casefold().startswith("llama3.2:")]
    if requested:
        assert requested in candidates, "OLLAMA_TEST_MODEL must be an installed permitted local model"
        candidates = [requested]
    for name in candidates:
        if provider.supports_model_chat(name) is True:
            return name
    pytest.fail("No installed local chat model other than retiring llama3.2 is available; no download or fallback")


@pytest.fixture(autouse=True)
def isolate_database(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database_connection,
        "DATABASE_PATH",
        tmp_path / "ai_corporation.db",
    )
    initialize_database()
