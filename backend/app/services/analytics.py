from uuid import uuid4

from app.core.db import Database
from app.repositories.analytics import AnalyticsRepository
from app.repositories.conversations import now
from app.repositories.models import RequestFailure


class AnalyticsService:
    def __init__(self, database: Database, merchant_id="demo"):
        self.database, self.merchant_id = database, merchant_id
        self.repository = AnalyticsRepository(database, merchant_id)

    async def snapshot(self):
        return await self.repository.snapshot()

    async def recent(self, limit=8):
        return await self.repository.recent(limit)

    async def pending(self, limit=20):
        return await self.repository.pending(limit)

    async def record_failed_request(self, code, conversation_id=None):
        async with self.database.transaction() as transaction:
            transaction.add(
                RequestFailure(
                    id=str(uuid4()),
                    merchant_id=self.merchant_id,
                    conversation_id=conversation_id,
                    error_code=code,
                    created_at=now(),
                )
            )
