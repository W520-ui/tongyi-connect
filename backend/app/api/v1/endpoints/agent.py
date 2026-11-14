from fastapi import APIRouter, Depends, HTTPException, status

from app.agent.engine import AgentEngine, get_agent_engine
from app.agent.models import AgentError
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.services.agent import AgentService
from app.services.workflow import metrics

router = APIRouter(prefix="/agent", tags=["Agent"])


def get_agent_service(engine: AgentEngine = Depends(get_agent_engine)) -> AgentService:
    return AgentService(engine)


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    service: AgentService = Depends(get_agent_service),
) -> AgentChatResponse:
    try:
        return AgentChatResponse(**await service.chat(request))
    except AgentError as exc:
        metrics.record_failed_request()
        if exc.status_code and exc.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
