from fastapi import APIRouter, Depends

from app.api.deps import get_conversation_service
from app.api.v1.presenters import present_workflow
from app.api.v1.schemas.agent import AgentChatRequest, AgentChatResponse
from app.domain.types import InboundMessage
from app.services.conversation import ConversationService

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest, service: ConversationService = Depends(get_conversation_service)
) -> AgentChatResponse:
    result = await service.handle_inbound(
        InboundMessage(
            request.message,
            request.session_id,
            request.username,
            request.locale,
            request.flags.enable_streaming,
        )
    )
    return AgentChatResponse(status="ok", data=present_workflow(result))
