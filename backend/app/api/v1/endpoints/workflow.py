from fastapi import APIRouter, HTTPException, Query

from app.services.workflow import list_products, metrics

router = APIRouter(tags=["Workflow"])


@router.get("/catalog/products")
async def catalog_products() -> dict:
    """Return the demo product knowledge base used by the service agent."""

    return {"status": "ok", "data": list_products()}


@router.get("/dashboard/overview")
async def dashboard_overview() -> dict:
    """Return persisted counters for the merchant dashboard."""

    return {"status": "ok", "data": metrics.snapshot()}


@router.get("/dashboard/recent")
async def dashboard_recent(limit: int = Query(default=8, ge=1, le=20)) -> dict:
    """Return compact recent summaries for the merchant archive panel."""

    return {"status": "ok", "data": metrics.recent_archive(limit)}


@router.post("/dashboard/handoffs/{record_id}/acknowledge")
async def acknowledge_handoff(record_id: str) -> dict:
    """Record that a merchant has accepted a handoff for follow-up."""

    if not metrics.acknowledge_handoff(record_id):
        raise HTTPException(status_code=404, detail="待接管记录不存在或已处理")
    return {"status": "ok", "data": {"record_id": record_id}}


@router.get("/dashboard/handoffs")
async def dashboard_handoffs(limit: int = Query(default=20, ge=1, le=50)) -> dict:
    """Return unresolved conversations that require a merchant follow-up."""

    return {"status": "ok", "data": metrics.recent_handoffs(limit)}
