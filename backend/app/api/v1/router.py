from fastapi import APIRouter

from app.api.v1.endpoints import agent, health, workflow

router = APIRouter()
router.include_router(health.router)
router.include_router(agent.router)
router.include_router(workflow.router)
