from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent.effects import FocusProducts, UpdateSlots
from app.agent.tools.base import FunctionTool, ToolOutput
from app.agent.tools.deps import ToolDeps
from app.agent.tools.outputs import error_output, output, product_data
from app.domain.countries import COUNTRY_CODES


class QueryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1)


class ProductArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    product_id: str = Field(min_length=1)


class QuoteArgs(ProductArgs):
    quantity: int | None = Field(default=None, ge=1)


class ShippingArgs(ProductArgs):
    destination: str = Field(
        pattern=r"^[A-Z]{2}$", description="ISO 3166-1 alpha-2 country code, such as ES"
    )

    @field_validator("destination")
    @classmethod
    def assigned_country(cls, country: str) -> str:
        if country not in COUNTRY_CODES:
            raise ValueError("Destination must be an assigned ISO 3166-1 alpha-2 country code")
        return country


async def search(args: QueryArgs, deps: ToolDeps) -> ToolOutput:
    products = await deps.catalog.search(args.query)
    return output(
        {"count": len(products), "products": [product_data(item) for item in products]},
        effects=(FocusProducts(tuple(item.id for item in products)),) if products else (),
    )


async def quote(args: QuoteArgs, deps: ToolDeps) -> ToolOutput:
    product = await deps.catalog.get(args.product_id)
    if product is None:
        return error_output("PRODUCT_NOT_FOUND", "Product not found; call catalog_search first")
    return output(
        {
            "product_id": product.id,
            "name": product.name,
            "price_usd": product.price_usd,
            "currency": "USD",
            "stock": product.stock,
        },
        effects=(FocusProducts((product.id,)), UpdateSlots(quantity=args.quantity)),
    )


async def shipping(args: ShippingArgs, deps: ToolDeps) -> ToolOutput:
    product = await deps.catalog.get(args.product_id)
    if product is None:
        return error_output("PRODUCT_NOT_FOUND", "Product not found; call catalog_search first")
    rule = await deps.catalog.shipping_rule(product.id, args.destination)
    effects = (FocusProducts((product.id,)), UpdateSlots(destination_country=args.destination))
    if rule is None:
        return output(
            {
                "product_id": product.id,
                "destination": args.destination,
                "availability": "unconfirmed",
                "note": "需商家确认，不得承诺可送达或配送时效",
            },
            effects=effects,
        )
    return output(
        {
            "product_id": product.id,
            "destination": args.destination,
            "availability": "available" if rule.available else "unavailable",
            "international_shipping": rule.available,
            "shipping_days": rule.days_text,
            "note": rule.note,
        },
        effects=effects,
    )


async def specs(args: ProductArgs, deps: ToolDeps) -> ToolOutput:
    product = await deps.catalog.get(args.product_id)
    if product is None:
        return error_output("PRODUCT_NOT_FOUND", "Product not found; call catalog_search first")
    return output(
        {"product_id": product.id, "name": product.name, "specs": product.specs},
        effects=(FocusProducts((product.id,)),),
    )


def catalog_tools(timeout: float) -> tuple[FunctionTool, ...]:
    return (
        FunctionTool(
            "catalog_search",
            "Search the product catalog by name or keyword",
            QueryArgs,
            search,
            timeout,
        ),
        FunctionTool(
            "catalog_quote",
            "Look up a product's single USD price and stock",
            QuoteArgs,
            quote,
            timeout,
        ),
        FunctionTool(
            "catalog_shipping",
            "Check verified shipping rules for an ISO country; "
            "unconfirmed requires merchant approval",
            ShippingArgs,
            shipping,
            timeout,
        ),
        FunctionTool(
            "catalog_specs", "Look up product specifications", ProductArgs, specs, timeout
        ),
    )
