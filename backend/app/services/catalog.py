import json
from importlib.resources import files

from app.domain.types import Product, ShippingRule


class CatalogService:
    def __init__(self, products: tuple[Product, ...], rules: tuple[ShippingRule, ...]) -> None:
        self.products = products
        self.rules = rules
        self._by_id = {product.id: product for product in products}

    @classmethod
    def load_seed(cls) -> "CatalogService":
        root = files("app.seed")
        products = json.loads(root.joinpath("catalog.json").read_text(encoding="utf-8"))
        rules = json.loads(root.joinpath("shipping_rules.json").read_text(encoding="utf-8"))
        return cls(
            tuple(Product(**{**item, "aliases": tuple(item["aliases"])}) for item in products),
            tuple(ShippingRule(**item) for item in rules),
        )

    async def get(self, product_id: str) -> Product | None:
        return self._by_id.get(product_id)

    async def search(self, query: str) -> tuple[Product, ...]:
        normalized = query.strip().lower()
        return tuple(
            product
            for product in self.products
            if normalized
            and any(
                normalized in value.lower()
                for value in (
                    product.name,
                    product.english_name,
                    *product.aliases,
                )
            )
        )

    async def shipping_rule(self, product_id: str, country: str) -> ShippingRule | None:
        return next(
            (
                rule
                for rule in self.rules
                if rule.destination_country == country and rule.product_id in (None, product_id)
            ),
            None,
        )
