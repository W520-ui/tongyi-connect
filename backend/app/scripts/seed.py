"""Rebuild only the configured demo database through Alembic."""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import Settings
from app.core.db import Database
from app.repositories.seed import seed_missing


async def rebuild(settings: Settings):
    database = Database(settings.database_url)
    try:
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).absolute().parents[2] / "migrations")
        )
        async with database.engine.begin() as connection:

            def reset(sync_connection):
                config.attributes["connection"] = sync_connection
                command.downgrade(config, "base")
                command.upgrade(config, "head")

            await connection.run_sync(reset)
        await seed_missing(database)
        return database.path
    finally:
        await database.close()


def main():
    print(asyncio.run(rebuild(Settings())))


if __name__ == "__main__":
    main()
