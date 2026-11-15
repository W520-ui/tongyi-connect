from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.db import Database


def test_default_database_path_is_backend_anchored(monkeypatch):
    monkeypatch.delenv("DATABASE_URL")
    settings = Settings(_env_file=None)
    assert (
        Path(make_url(settings.database_url).database)
        == Path(__file__).absolute().parents[1] / "data" / "app.db"
    )


def test_relative_database_url_is_backend_anchored(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None, database_url="sqlite+aiosqlite:///local/demo.db")
    assert (
        Path(make_url(settings.database_url).database)
        == Path(__file__).absolute().parents[1] / "local" / "demo.db"
    )


async def test_conversation_and_analytics_share_one_database(runtime_factory):
    runtime = runtime_factory()
    assert runtime.service.store.database is runtime.database
    assert runtime.service.analytics.database is runtime.database
    async with runtime.database.sessions() as transaction:
        filename = (await transaction.execute(text("PRAGMA database_list"))).first()[2]
        assert Path(filename) == runtime.database.path
        assert await transaction.scalar(text("PRAGMA journal_mode")) == "wal"
        assert await transaction.scalar(text("PRAGMA foreign_keys")) == 1
    assert isinstance(runtime.database, Database)
