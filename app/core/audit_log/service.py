from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.contextvars import get_contextvars

from app.core.audit_log.models import AuditLog

SENSITIVE_FIELDS = {
    'shipping_address',
    'email',
}


class AuditLogService:
    """Service for creating and persisting audit log entries.

    Provides methods to log arbitrary events, compute field-level diffs
    between model snapshots, and record PII access events. Sensitive
    fields listed in ``SENSITIVE_FIELDS`` are masked in the diff output.
    """

    async def log_event(
        self,
        session: AsyncSession,
        actor_id: UUID,
        target_type: str,
        target_id: UUID,
        action: str,
        changes: dict[str, Any],
        extra_data: dict[str, Any] | None = None,
    ) -> None:
        """Persist a single audit log event to the database.

        Reads the current ``request_id`` and ``remote_ip`` from the
        Structlog context variables and attaches them to the log entry.
        Any ``extra_data`` is merged into the ``changes`` dictionary.

        Args:
            session: The async SQLAlchemy database session.
            actor_id: UUID of the user performing the action.
            target_type: Logical type of the target object (e.g., ``'order'``).
            target_id: UUID of the target object.
            action: Name of the action (e.g., ``'create'``, ``'update'``).
            changes: Dictionary describing the changes made.
            extra_data: Optional additional data to merge into ``changes``.
        """
        context = get_contextvars()
        request_id = context.get('request_id')
        remote_ip = context.get('remote_ip')
        if extra_data:
            changes.update(extra_data)
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
        """Compute a field-level diff between two Pydantic model snapshots.

        Compares the JSON-serialized data of ``old_model`` and ``new_model``
        and produces a dictionary mapping changed field names to
        ``[old_value, new_value]`` pairs. A ``None`` value for either model
        represents creation or deletion. Fields listed in
        ``SENSITIVE_FIELDS`` are masked with ``'[SENSITIVE_DATA_HIDDEN]'``.

        Args:
            old_model: The previous state of the model, or ``None`` if the
                object was newly created.
            new_model: The updated state of the model, or ``None`` if the
                object was deleted.

        Returns:
            A dictionary of field names to ``[old, new]`` value pairs for
            all fields that differ between the two models. Returns an empty
            dict if both models are ``None``.
        """
        diff: dict[str, Any] = {}
        if old_model is None and new_model is not None:
            data = new_model.model_dump(mode='json')
            return {
                k: [None, ('[SENSITIVE_DATA_HIDDEN]' if k in SENSITIVE_FIELDS else v)]
                for k, v in data.items()
            }

        if old_model is not None and new_model is None:
            data = old_model.model_dump(mode='json')
            return {
                k: [('[SENSITIVE_DATA_HIDDEN]' if k in SENSITIVE_FIELDS else v), None]
                for k, v in data.items()
            }

        if old_model is not None and new_model is not None:
            old_data = old_model.model_dump(mode='json')
            new_data = new_model.model_dump(mode='json')
            for key, value in new_data.items():
                old_val = old_data.get(key)
                if value != old_val:
                    if key in SENSITIVE_FIELDS:
                        diff[key] = [
                            '[SENSITIVE_DATA_HIDDEN]',
                            '[SENSITIVE_DATA_HIDDEN]',
                        ]
                    else:
                        diff[key] = [old_val, value]
            return diff
        return diff

    async def log_object_change(
        self,
        session: AsyncSession,
        actor_id: UUID,
        target_id: UUID,
        target_type: str,
        action: str,
        old_obj: BaseModel | None,
        new_obj: BaseModel | None,
        extra_data: dict[str, Any] | None = None,
    ) -> None:
        """Log a change to a domain object by computing and recording its diff.

        Computes the field-level difference between the old and new states
        of an object using :meth:`get_diff` and persists the result as an
        audit log entry only if there are actual changes.

        Args:
            session: The async SQLAlchemy database session.
            actor_id: UUID of the user performing the change.
            target_id: UUID of the target object.
            target_type: Logical type of the target object (e.g., ``'order'``).
            action: Name of the action (e.g., ``'update'``, ``'delete'``).
            old_obj: The previous Pydantic model state, or ``None`` on creation.
            new_obj: The updated Pydantic model state, or ``None`` on deletion.
            extra_data: Optional additional data to merge into the changes.
        """
        diff = self.get_diff(old_obj, new_obj)
        if diff:
            await self.log_event(
                session=session,
                actor_id=actor_id,
                target_type=target_type,
                target_id=target_id,
                action=action,
                changes=diff,
                extra_data=extra_data,
            )

    async def log_pii_access(
        self,
        session: AsyncSession,
        actor_id: UUID,
        target_id: UUID,
        target_type: str,
        reason: str | None = None,
    ) -> None:
        """Record an access event involving personally identifiable information.

        Creates an audit log entry with the action ``'pii_accessed'`` to
        track when a user views or accesses PII data, optionally recording
        the business justification.

        Args:
            session: The async SQLAlchemy database session.
            actor_id: UUID of the user accessing the PII.
            target_id: UUID of the target object containing PII.
            target_type: Logical type of the target object (e.g., ``'user'``).
            reason: Optional business justification for the access.
        """
        await self.log_event(
            session=session,
            actor_id=actor_id,
            target_id=target_id,
            target_type=target_type,
            action='pii_access',
            changes={'pii_accessed': True, 'reason': reason},
        )


audit_log_service = AuditLogService()
