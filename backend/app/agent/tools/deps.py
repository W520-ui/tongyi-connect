from typing import Protocol

from app.domain.types import Product, ShippingRule


class CatalogPort(Protocol):
    async def get(self, product_id: str) -> Product | None: ...
    async def search(self, query: str) -> tuple[Product, ...]: ...
    async def shipping_rule(self, product_id: str, country: str) -> ShippingRule | None: ...


class ToolDeps(Protocol):
    @property
    def catalog(self) -> CatalogPort: ...
