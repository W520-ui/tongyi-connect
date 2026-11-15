from fastapi import Request

from app.core.config import Settings
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
