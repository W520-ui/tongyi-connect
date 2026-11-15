from fastapi import APIRouter, Depends, Query
from starlette.responses import StreamingResponse

from app.api.deps import get_conversation_service
from app.api.v1.presenters import present_public_workflow
from app.api.v1.schemas.agent import AgentWorkflowData
from app.api.v1.schemas.conversations import (
    Conversation,
    CreateConversation,
    HandoffResult,
    MessagePage,
    RequestHandoff,
    ResetConversation,
    SendMessageRequest,
    UpdateConversation,
)
from app.api.v1.schemas.stream import STREAM_SCHEMAS
from app.api.v1.schemas.workflow import Envelope
from app.api.v1.streaming import subscribe
from app.domain.types import InboundMessage
from app.services.conversation import ConversationService

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post("", status_code=201, response_model=Envelope[Conversation])
async def create_conversation(
    request: CreateConversation,
    service: ConversationService = Depends(get_conversation_service),
):
    return Envelope(data=Conversation(**await service.create(request.reply_language)))


@router.get("/{conversation_id}", response_model=Envelope[Conversation])
async def get_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    return Envelope(data=Conversation(**await service.describe(conversation_id)))


@router.patch("/{conversation_id}", response_model=Envelope[Conversation])
async def update_conversation(
    conversation_id: str,
    request: UpdateConversation,
    service: ConversationService = Depends(get_conversation_service),
):
    return Envelope(
        data=Conversation(**await service.update_language(conversation_id, request.reply_language))
    )


@router.get("/{conversation_id}/messages", response_model=Envelope[MessagePage])
async def get_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=200),
    before_seq: int | None = Query(None, ge=1),
    service: ConversationService = Depends(get_conversation_service),
):
    items, has_more = await service.history(conversation_id, limit, before_seq)
    for item in items:
        if item["workflow"]:
            item["workflow"] = present_public_workflow(item["workflow"])
    return Envelope(data=MessagePage(items=items, has_more=has_more))


@router.post("/{conversation_id}/messages", response_model=Envelope[AgentWorkflowData])
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    service: ConversationService = Depends(get_conversation_service),
):
    result = await service.handle_inbound(
        InboundMessage(
            request.content,
            conversation_id,
            client_message_id=request.client_message_id,
            legacy_session=False,
        )
    )
    return Envelope(data=present_public_workflow(result))


@router.post(
    "/{conversation_id}/messages/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
            "headers": {"Cache-Control": {"schema": {"type": "string"}}},
        }
    },
    openapi_extra={
        "x-sse-events": {
            name: {"$ref": f"#/components/schemas/{schema.__name__}"}
            for name, schema in STREAM_SCHEMAS.items()
        }
    },
)
async def stream_message(
    conversation_id: str,
    request: SendMessageRequest,
    service: ConversationService = Depends(get_conversation_service),
):
    events = await subscribe(
        service,
        InboundMessage(
            request.content,
            conversation_id,
            streaming=True,
            client_message_id=request.client_message_id,
            legacy_session=False,
        ),
    )
    return StreamingResponse(
        events, media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@router.post(
    "/{conversation_id}/reset", status_code=201, response_model=Envelope[ResetConversation]
)
async def reset_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    return Envelope(
        data=ResetConversation(
            previous_conversation_id=conversation_id,
            conversation=Conversation(**await service.reset(conversation_id)),
        )
    )


@router.post("/{conversation_id}/handoff", response_model=Envelope[HandoffResult])
async def request_handoff(
    conversation_id: str,
    request: RequestHandoff,
    service: ConversationService = Depends(get_conversation_service),
):
    conversation, ticket = await service.request_handoff(conversation_id, request.reason_text)
    return Envelope(data=HandoffResult(conversation=Conversation(**conversation), ticket=ticket))
