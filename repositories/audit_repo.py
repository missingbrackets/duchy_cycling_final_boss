"""AuditLog repository."""
from __future__ import annotations

from sqlalchemy.orm import Session

from models.audit import AuditLog


def log_action(
    session: Session,
    user: str,
    action_type: str,
    entity_type: str,
    entity_id: str | None = None,
    before_json: str | None = None,
    after_json: str | None = None,
    notes: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        user=user,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before_json,
        after_json=after_json,
        notes=notes,
    )
    session.add(entry)
    return entry


def get_all_logs(session: Session) -> list[AuditLog]:
    return session.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
