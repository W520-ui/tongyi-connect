from fastapi import APIRouter

from app.api.v1.endpoints import agent, conversations, handoffs, health, status, workflow
from app.api.v1.schemas.errors import ERROR_RESPONSES

router = APIRouter(responses=ERROR_RESPONSES)
router.include_router(health.router)
router.include_router(agent.router)
router.include_router(workflow.router)
router.include_router(status.router)
router.include_router(conversations.router)
router.include_router(handoffs.router)
