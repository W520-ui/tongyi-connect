from fastapi import APIRouter, Depends, Query

from app.api.deps import get_conversation_service, get_handoffs, require_merchant
from app.api.v1.schemas.conversations import HandoffList, HandoffTicket
from app.api.v1.schemas.workflow import Envelope
from app.core.errors import AppError
from app.services.conversation import ConversationService
from app.services.handoff import HandoffService

router = APIRouter(prefix="/handoffs", tags=["Handoffs"], dependencies=[Depends(require_merchant)])


@router.get("", response_model=Envelope[HandoffList])
async def list_handoffs(
    status: str = Query("open,acknowledged"),
    limit: int = Query(20, ge=1, le=50),
    handoffs: HandoffService = Depends(get_handoffs),
):
    statuses = status.split(",")
    if any(value not in {"open", "acknowledged", "resolved"} for value in statuses):
        raise AppError(
            "VALIDATION_ERROR",
            details=[
                {
                    "loc": ["query", "status"],
                    "msg": "状态只能为 open、acknowledged、resolved，以逗号分隔",
                }
            ],
        )
    return Envelope(data=HandoffList(items=await handoffs.list_tickets(statuses, limit)))


@router.post("/{ticket_id}/acknowledge", response_model=Envelope[HandoffTicket])
async def acknowledge(
    ticket_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    return Envelope(data=HandoffTicket.model_validate(await service.change_handoff(ticket_id)))


@router.post("/{ticket_id}/resolve", response_model=Envelope[HandoffTicket])
async def resolve(
    ticket_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    return Envelope(
        data=HandoffTicket.model_validate(await service.change_handoff(ticket_id, resolve=True))
    )
