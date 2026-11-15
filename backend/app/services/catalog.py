from sqlalchemy import or_, select

from app.core.db import Database
from app.domain.types import Product, ShippingRule
from app.repositories.models import StoredProduct, StoredShippingRule
from app.repositories.seed import product_value, rule_value


class CatalogService:
    def __init__(self, database: Database, merchant_id: str = "demo") -> None:
        self.database, self.merchant_id = database, merchant_id

    async def list_products(self) -> tuple[Product, ...]:
        async with self.database.sessions() as session:
            rows = (
                await session.scalars(
                    select(StoredProduct)
                    .where(StoredProduct.merchant_id == self.merchant_id)
                    .order_by(StoredProduct.id)
                )
            ).all()
            return tuple(product_value(row) for row in rows)

    async def get(self, product_id: str) -> Product | None:
        async with self.database.sessions() as session:
            row = await session.get(StoredProduct, (product_id, self.merchant_id))
            return product_value(row) if row else None

    async def search(self, query: str) -> tuple[Product, ...]:
        normalized = query.strip().lower()
        return tuple(
            product
            for product in await self.list_products()
            if normalized
            and any(
                normalized in value.lower()
                for value in (product.name, product.english_name, *product.aliases)
            )
        )

    async def shipping_rule(self, product_id: str, country: str) -> ShippingRule | None:
        async with self.database.sessions() as session:
            row = await session.scalar(
                select(StoredShippingRule)
                .where(
                    StoredShippingRule.merchant_id == self.merchant_id,
                    StoredShippingRule.destination_country == country,
                    or_(
                        StoredShippingRule.product_id == product_id,
                        StoredShippingRule.product_id.is_(None),
                    ),
                )
                .order_by(StoredShippingRule.product_id.is_(None))
                .limit(1)
            )
            return rule_value(row) if row else None
