from fastapi import APIRouter, Depends, Request

from app.api.v1.schemas.workflow import Envelope, SystemStatus
from app.services.status import StatusService

router = APIRouter()


def get_status_service(request: Request) -> StatusService:
    return request.app.state.status


@router.get("/status", response_model=Envelope[SystemStatus], tags=["Status"])
async def system_status(service: StatusService = Depends(get_status_service)):
    return Envelope(data=SystemStatus(**service.snapshot()))
