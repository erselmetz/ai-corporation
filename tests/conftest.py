import pytest

from app.database import initialize_database
from app.database import connection as database_connection


@pytest.fixture(autouse=True)
def isolate_database(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database_connection,
        "DATABASE_PATH",
        tmp_path / "ai_corporation.db",
    )
    initialize_database()
