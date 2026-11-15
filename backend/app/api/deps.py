import secrets

from fastapi import Depends, Header, Request

from app.core.config import Settings
from app.core.errors import AppError
from app.services.analytics import AnalyticsService
from app.services.catalog import CatalogService
from app.services.conversation import ConversationService
from app.services.handoff import HandoffService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_conversation_service(request: Request) -> ConversationService:
    return request.app.state.conversation_service


def get_catalog(request: Request) -> CatalogService:
    return request.app.state.catalog


def get_analytics(request: Request) -> AnalyticsService:
    return request.app.state.analytics


def get_handoffs(request: Request) -> HandoffService:
    return request.app.state.handoffs


def require_merchant(
    settings: Settings = Depends(get_settings),
    merchant_key: str | None = Header(default=None, alias="X-Merchant-Key"),
) -> None:
    configured = settings.merchant_api_key
    expected = configured.get_secret_value() if configured else ""
    if expected and (
        merchant_key is None
        or not secrets.compare_digest(merchant_key.encode("utf-8"), expected.encode("utf-8"))
    ):
        raise AppError("UNAUTHORIZED")
