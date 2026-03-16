from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.contextvars import get_contextvars

from app.core.audit_log.models import AuditLog


class AuditLogService:
    async def log_event(
        self,
        session: AsyncSession,
        actor_id: UUID,
        target_type: str,
        target_id: UUID,
        action: str,
        changes: dict[str, Any],
    ) -> None:
        context = get_contextvars()
        request_id = context.get('request_id')
        remote_ip = context.get('remote_ip')

        log = AuditLog(
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            action=action,
            changes=changes,
            request_id=request_id,
            remote_ip=remote_ip,
        )
        session.add(log)
        await session.flush()

    @staticmethod
    def get_diff(
        old_model: BaseModel | None,
        new_model: BaseModel | None,
    ) -> dict[str, Any]:
        if old_model is None and new_model is not None:
            return {k: [None, v] for k, v in new_model.model_dump(mode='json').items()}
        if old_model is not None and new_model is None:
            return {k: [v, None] for k, v in old_model.model_dump(mode='json').items()}
        if old_model is not None and new_model is not None:
            old_data = old_model.model_dump(mode='json')
            new_data = new_model.model_dump(mode='json')
            diff = {}
            for key, value in new_data.items():
                old_val = old_data.get(key)
                if value != old_val:
                    diff[key] = [old_val, value]
            return diff
        return {}

    async def log_object_change(
        self,
        session: AsyncSession,
        actor_id: UUID,
        target_id: UUID,
        target_type: str,
        action: str,
        old_obj: BaseModel | None,
        new_obj: BaseModel | None,
    ) -> None:
        diff = self.get_diff(old_obj, new_obj)
        if diff:
            await self.log_event(
                session=session,
                actor_id=actor_id,
                target_type=target_type,
                target_id=target_id,
                action=action,
                changes=diff,
            )


audit_log_service = AuditLogService()
