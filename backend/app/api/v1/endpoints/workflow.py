from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import (
    get_analytics,
    get_catalog,
    get_conversation_service,
    get_handoffs,
    require_merchant,
)
from app.api.v1.schemas.agent import ProductSchema
from app.api.v1.schemas.workflow import (
    Acknowledgment,
    DashboardOverview,
    Envelope,
    RecentInquiry,
)
from app.core.errors import AppError
from app.services.analytics import AnalyticsService
from app.services.catalog import CatalogService
from app.services.conversation import ConversationService
from app.services.handoff import HandoffService

router = APIRouter(tags=["Workflow"])


@router.get("/catalog/products", response_model=Envelope[list[ProductSchema]])
async def catalog_products(catalog: CatalogService = Depends(get_catalog)):
    return Envelope(
        data=[ProductSchema.model_validate(product) for product in await catalog.list_products()]
    )


@router.get(
    "/dashboard/overview",
    response_model=Envelope[DashboardOverview],
    dependencies=[Depends(require_merchant)],
)
async def dashboard_overview(analytics: AnalyticsService = Depends(get_analytics)):
    return Envelope(data=DashboardOverview(**await analytics.snapshot()))


@router.get(
    "/dashboard/recent",
    response_model=Envelope[list[RecentInquiry]],
    dependencies=[Depends(require_merchant)],
)
async def dashboard_recent(
    limit: int = Query(default=8, ge=1, le=20), analytics: AnalyticsService = Depends(get_analytics)
):
    return Envelope(data=[RecentInquiry(**record) for record in await analytics.recent(limit)])


@router.post("/dashboard/handoffs/{record_id}/acknowledge", response_model=Envelope[Acknowledgment])
async def acknowledge_handoff(
    record_id: str, service: ConversationService = Depends(get_conversation_service)
):
    try:
        await service.change_handoff(record_id)
    except AppError as error:
        if error.code not in {"HANDOFF_NOT_FOUND", "INVALID_STATE"}:
            raise
        raise HTTPException(status_code=404, detail="待接管记录不存在或已处理") from None
    return Envelope(data=Acknowledgment(record_id=record_id))


@router.get("/dashboard/handoffs", response_model=Envelope[list[RecentInquiry]])
async def dashboard_handoffs(
    limit: int = Query(default=20, ge=1, le=50), handoffs: HandoffService = Depends(get_handoffs)
):
    return Envelope(data=[RecentInquiry(**record) for record in await handoffs.pending(limit)])
