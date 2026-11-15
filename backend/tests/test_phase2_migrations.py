import subprocess
import sys
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.repositories.conversations import ConversationRepository
from app.repositories.models import Base, Merchant, StoredProduct
from app.repositories.seed import seed_values
from app.scripts.seed import rebuild
from app.services.analytics import AnalyticsService
from app.services.catalog import CatalogService
from tests.support import Decision, ScriptedProvider


async def test_migration_matches_models_and_legacy_tables_are_absent(runtime_factory):
    runtime = runtime_factory()
    async with runtime.database.engine.connect() as connection:

        def compare(sync_connection):
            assert set(inspect(sync_connection).get_table_names()) == set(Base.metadata.tables) | {
                "alembic_version"
            }
            assert (
                compare_metadata(MigrationContext.configure(sync_connection), Base.metadata) == []
            )

        await connection.run_sync(compare)
        assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
        assert await connection.scalar(text("PRAGMA journal_mode")) == "wal"


async def test_seed_rebuild_discards_conversations_and_restores_catalog(runtime_factory):
    runtime = runtime_factory(ScriptedProvider([Decision(reply="Hello")]))
    from app.domain.types import InboundMessage

    await runtime.service.handle_inbound(InboundMessage("Hello", "seed"))
    assert runtime.snapshot()["total_conversations"] == 1
    path = await rebuild(runtime.app.state.settings)
    assert path == runtime.database.path and runtime.snapshot()["total_conversations"] == 0
    products, rules = seed_values()
    stored = await runtime.service.catalog.list_products()
    assert {product.id: product.price_usd for product in stored} == {
        item["id"]: item["price_usd"] for item in products
    }
    for rule in rules:
        value = await runtime.service.catalog.shipping_rule(
            rule["product_id"], rule["destination_country"]
        )
        assert value.days_text == rule["days_text"]
    assert len(runtime.rows(Merchant)) == 1 and runtime.rows(Merchant)[0].id == "demo"


def test_seed_cli_uses_temporary_database_and_can_run_twice(runtime_factory):
    runtime = runtime_factory()
    import os

    environment = dict(os.environ, DATABASE_URL=runtime.database.url, PYTHONIOENCODING="utf-8")
    for _index in range(2):
        completed = subprocess.run(
            [sys.executable, "-m", "app.scripts.seed"],
            cwd=Path(__file__).absolute().parents[1],
            env=environment,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert str(runtime.database.path) in completed.stdout
    assert len(runtime.rows(StoredProduct)) == 3


async def test_merchant_scopes_catalog_conversations_and_statistics(runtime_factory):
    runtime = runtime_factory()
    async with runtime.database.transaction() as transaction:
        transaction.add(Merchant(id="other"))
        await transaction.flush()
        template = seed_values()[0][0]
        transaction.add(StoredProduct(**{**template, "price_usd": 1}, merchant_id="other"))
    assert (await CatalogService(runtime.database, "other").get("headset-pro")).price_usd == 1
    assert (await runtime.service.catalog.get("headset-pro")).price_usd == 39
    demo = await runtime.service.store.resolve("same-alias")
    other_store = ConversationRepository(runtime.database, "other")
    other = await other_store.resolve("same-alias")
    assert demo.session_id != other.session_id
    with pytest.raises(AppError) as error:
        await other_store.get(demo.session_id)
    assert error.value.code == "CONVERSATION_NOT_FOUND"
    other_analytics = AnalyticsService(runtime.database, "other")
    await other_analytics.record_failed_request("LLM_TIMEOUT", other.session_id)
    assert (await other_analytics.snapshot())["failed_requests"] == 1
    assert runtime.snapshot()["failed_requests"] == 0


async def test_only_one_unclosed_ticket_can_exist_in_database(runtime_factory):
    from app.domain.types import InboundMessage
    from app.repositories.models import HandoffTicket

    runtime = runtime_factory()
    await runtime.service.handle_inbound(InboundMessage("/handoff", "tickets"))
    ticket = runtime.rows(HandoffTicket)[0]
    with pytest.raises(IntegrityError):
        async with runtime.database.transaction() as transaction:
            transaction.add(
                HandoffTicket(
                    id="another",
                    merchant_id="demo",
                    conversation_id=ticket.conversation_id,
                    status="open",
                    reason_code="user_request",
                    reason_text="Another",
                    created_at=ticket.created_at,
                    customer_message="/handoff",
                    language_label="中文",
                    intent_label="综合咨询",
                )
            )
    assert len(runtime.rows(HandoffTicket)) == 1
