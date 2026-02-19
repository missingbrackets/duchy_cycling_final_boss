"""Audit service — thin wrapper for structured JSON audit logging."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from core.config import ActionType, EntityType, DEFAULT_USER
from repositories.audit_repo import log_action


def _to_json(obj: Any) -> str | None:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return json.dumps(obj, default=str)
    return json.dumps(obj, default=str)


def audit_create_coach(
    session: Session,
    coach_id: int,
    name: str,
    date_joined: str,
    user: str = DEFAULT_USER,
) -> None:
    log_action(
        session,
        user=user,
        action_type=ActionType.CREATE_COACH,
        entity_type=EntityType.COACH,
        entity_id=str(coach_id),
        after_json=_to_json({"coach_id": coach_id, "name": name, "date_joined": date_joined}),
    )


def audit_update_coach(
    session: Session,
    coach_id: int,
    before: dict,
    after: dict,
    user: str = DEFAULT_USER,
) -> None:
    log_action(
        session,
        user=user,
        action_type=ActionType.UPDATE_COACH,
        entity_type=EntityType.COACH,
        entity_id=str(coach_id),
        before_json=_to_json(before),
        after_json=_to_json(after),
    )


def audit_create_client(
    session: Session,
    client_id: int,
    after: dict,
    user: str = DEFAULT_USER,
) -> None:
    log_action(
        session,
        user=user,
        action_type=ActionType.CREATE_CLIENT,
        entity_type=EntityType.CLIENT,
        entity_id=str(client_id),
        after_json=_to_json(after),
    )


def audit_update_client(
    session: Session,
    client_id: int,
    before: dict,
    after: dict,
    user: str = DEFAULT_USER,
) -> None:
    log_action(
        session,
        user=user,
        action_type=ActionType.UPDATE_CLIENT,
        entity_type=EntityType.CLIENT,
        entity_id=str(client_id),
        before_json=_to_json(before),
        after_json=_to_json(after),
    )


def audit_cancel_client(
    session: Session,
    client_id: int,
    before: dict,
    end_date: str,
    user: str = DEFAULT_USER,
) -> None:
    log_action(
        session,
        user=user,
        action_type=ActionType.CANCEL_CLIENT,
        entity_type=EntityType.CLIENT,
        entity_id=str(client_id),
        before_json=_to_json(before),
        after_json=_to_json({"end_date": end_date}),
    )


def audit_import_csv(
    session: Session,
    filename: str,
    clients_created: int,
    coaches_created: int,
    versions_created: int,
    errors: int,
    user: str = DEFAULT_USER,
) -> None:
    log_action(
        session,
        user=user,
        action_type=ActionType.IMPORT_CSV,
        entity_type=EntityType.IMPORT,
        notes=(
            f"File: {filename} | "
            f"Clients created: {clients_created} | "
            f"Coaches created: {coaches_created} | "
            f"Versions created: {versions_created} | "
            f"Errors: {errors}"
        ),
    )
