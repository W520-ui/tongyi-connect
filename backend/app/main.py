from contextlib import AsyncExitStack, asynccontextmanager
from importlib.resources import files

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent.analysis import PostAnalyzer
from app.agent.context import ContextBuilder
from app.agent.llm.base import LLMClient
from app.agent.llm.openai import OpenAICompatibleClient
from app.agent.registry import create_default_registry
from app.agent.runtime import AgentRunner
from app.api.router import api_router
from app.core.background import BackgroundTasks
from app.core.config import Settings
from app.core.db import Database
from app.core.errors import AppError
from app.core.locks import LocalConversationLocks
from app.core.logging import configure_logging
from app.repositories.conversations import ConversationRepository
from app.repositories.seed import seed_missing
from app.services.analytics import AnalyticsService
from app.services.catalog import CatalogService
from app.services.conversation import ConversationService
from app.services.handoff import HandoffService
from app.services.status import StatusService


def create_app(
    settings: Settings | None = None,
    *,
    llm_client: LLMClient | None = None,
    analysis_client: LLMClient | None = None,
) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging(
            settings.log_level,
            settings.llm_api_key.get_secret_value() if settings.llm_api_key else None,
        )
        async with AsyncExitStack() as resources:
            client = await resources.enter_async_context(httpx.AsyncClient())
            database = Database(settings.database_url)
            resources.push_async_callback(database.close)
            await database.migrate()
            await seed_missing(database)
            store = ConversationRepository(database, settings.merchant_id)
            catalog = CatalogService(database, settings.merchant_id)
            llm = llm_client if llm_client is not None else OpenAICompatibleClient(settings, client)
            analysis_settings = settings.model_copy(
                update={"llm_model": settings.analysis_model or settings.llm_model}
            )
            analysis_llm = (
                analysis_client
                if analysis_client is not None
                else (
                    llm_client
                    if llm_client is not None
                    else OpenAICompatibleClient(analysis_settings, client)
                )
            )
            runner = AgentRunner(
                settings, llm, create_default_registry(settings.tool_timeout_seconds)
            )
            context = ContextBuilder(
                files("app.agent.prompts").joinpath("system_v2.txt").read_text(encoding="utf-8"),
                catalog,
                settings.context_token_budget,
                settings.tool_result_max_chars,
            )
            analytics = AnalyticsService(database, settings.merchant_id)
            handoffs = HandoffService(database, store, settings.merchant_id)
            background = BackgroundTasks()
            resources.push_async_callback(background.close)
            analyzer = PostAnalyzer(
                analysis_llm, settings.analysis_enabled, settings.analysis_timeout_seconds
            )
            service = ConversationService(
                settings,
                runner,
                context,
                store,
                catalog,
                analytics,
                handoffs,
                LocalConversationLocks(),
                analyzer,
                background,
            )
            for name, value in {
                "settings": settings,
                "http_client": client,
                "database": database,
                "conversations": store,
                "catalog": catalog,
                "llm": llm,
                "runner": runner,
                "analytics": analytics,
                "handoffs": handoffs,
                "conversation_service": service,
                "background": background,
                "analyzer": analyzer,
                "status": StatusService(settings, llm, database),
            }.items():
                setattr(application.state, name, value)
            yield

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    @application.exception_handler(AppError)
    async def app_error(_request, error: AppError):
        return JSONResponse(
            status_code=error.status_code,
            content={
                "status": "error",
                "detail": error.message,
                "error": {"code": error.code, "message": error.message, "details": None},
            },
        )

    return application


class LazyApplication:
    """Preserve the launcher while allocating no resources at import time."""

    def __init__(self):
        self.application: FastAPI | None = None

    async def __call__(self, scope, receive, send):
        if self.application is None:
            self.application = create_app()
        await self.application(scope, receive, send)


app = LazyApplication()
