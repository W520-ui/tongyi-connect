from fastapi import APIRouter, Depends, HTTPException, status

from app.clients.astrbot import AstrBotClient, AstrBotError
from app.core.config import Settings, get_settings
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.services.agent import AgentService
from app.services.workflow import metrics

router = APIRouter(prefix="/agent", tags=["Agent"])


def get_agent_service(settings: Settings = Depends(get_settings)) -> AgentService:
    return AgentService(AstrBotClient(settings))


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    service: AgentService = Depends(get_agent_service),
) -> AgentChatResponse:
    try:
        return AgentChatResponse(**await service.chat(request))
    except AstrBotError as exc:
        if exc.status_code in {401, 403}:
            metrics.record_failed_request()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AstrBot 鉴权失败，请检查 ASTRBOT_API_KEY 和 chat scope",
            ) from exc
        if exc.status_code and exc.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
