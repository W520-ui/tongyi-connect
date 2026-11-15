from fastapi import APIRouter, Depends

from app.api.deps import get_settings
from app.api.v1.schemas.workflow import HealthResponse
from app.core.config import Settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", service="tongyi-connect-api", version=settings.app_version)
