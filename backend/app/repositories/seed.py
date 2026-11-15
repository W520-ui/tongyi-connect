import json
from datetime import UTC, datetime
from importlib.resources import files

from sqlalchemy import select

from app.core.db import Database
from app.domain.types import Product, ShippingRule
from app.repositories.models import Merchant, MetadataEntry, StoredProduct, StoredShippingRule


def seed_values():
    root = files("app.seed")
    return (
        json.loads(root.joinpath("catalog.json").read_text(encoding="utf-8")),
        json.loads(root.joinpath("shipping_rules.json").read_text(encoding="utf-8")),
    )


async def seed_missing(database: Database) -> None:
    products, rules = seed_values()
    async with database.transaction() as session:
        if await session.get(Merchant, "demo") is None:
            session.add(Merchant(id="demo"))
            await session.flush()
        if await session.get(MetadataEntry, "started_at") is None:
            session.add(MetadataEntry(key="started_at", value=datetime.now(UTC).isoformat()))
        if not await session.scalar(
            select(StoredProduct.id).where(StoredProduct.merchant_id == "demo").limit(1)
        ):
            session.add_all(StoredProduct(merchant_id="demo", **item) for item in products)
            await session.flush()
            session.add_all(StoredShippingRule(merchant_id="demo", **item) for item in rules)


def product_value(row: StoredProduct) -> Product:
    return Product(
        row.id,
        row.name,
        row.english_name,
        row.category,
        row.price_usd,
        row.stock,
        row.shipping_days,
        tuple(row.aliases),
        row.specs,
    )


def rule_value(row: StoredShippingRule) -> ShippingRule:
    return ShippingRule(
        row.product_id, row.destination_country, row.available, row.days_text, row.note
    )
