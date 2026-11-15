"""Owned async database resources, without importing ORM models here."""

from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


class Database:
    def __init__(self, url: str) -> None:
        self.url, self.closed = url, False
        parsed = make_url(url)
        if parsed.drivername != "sqlite+aiosqlite" or not parsed.database:
            raise ValueError("This demo requires a file-backed SQLite database")
        self.path = Path(parsed.database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

        @event.listens_for(self.engine.sync_engine, "connect")
        def configure(connection, _record):
            connection.isolation_level = None
            cursor = connection.cursor()
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        @event.listens_for(self.engine.sync_engine, "begin")
        def begin(connection):
            connection.exec_driver_sql("BEGIN")

    async def migrate(self) -> None:
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).absolute().parents[2] / "migrations")
        )
        async with self.engine.begin() as connection:

            def upgrade(sync_connection):
                config.attributes["connection"] = sync_connection
                command.upgrade(config, "head")

            await connection.run_sync(upgrade)

    @asynccontextmanager
    async def transaction(self):
        async with self.sessions.begin() as session:
            yield session

    async def ping(self) -> bool:
        if self.closed:
            return False
        try:
            async with self.sessions() as session:
                return await session.scalar(text("SELECT 1")) == 1
        except Exception:
            return False

    async def close(self) -> None:
        self.closed = True
        await self.engine.dispose()
