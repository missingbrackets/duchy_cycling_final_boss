"""Coach repository — all DB operations for Coach."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from models.coach import Coach


def create_coach(session: Session, name: str, date_joined: date) -> Coach:
    coach = Coach(name=name, date_joined=date_joined)
    session.add(coach)
    session.commit()
    session.refresh(coach)
    return coach


def get_coach_by_id(session: Session, coach_id: int) -> Coach | None:
    return session.get(Coach, coach_id)


def get_coach_by_name(session: Session, name: str) -> Coach | None:
    return session.query(Coach).filter(Coach.name == name).first()


def get_all_coaches(session: Session) -> list[Coach]:
    return session.query(Coach).order_by(Coach.name).all()


def get_or_create_coach(session: Session, name: str, date_joined: date | None = None) -> Coach:
    coach = get_coach_by_name(session, name)
    if coach is None:
        coach = create_coach(session, name, date_joined or date.today())
    return coach


def delete_coach(session: Session, coach_id: int) -> str:
    """Delete a coach. Raises ValueError if they still have client versions."""
    from models.client import ClientVersion  # avoid circular at module load
    linked = session.query(ClientVersion).filter(
        ClientVersion.coach_id == coach_id
    ).count()
    if linked > 0:
        coach = session.get(Coach, coach_id)
        name = coach.name if coach else str(coach_id)
        raise ValueError(
            f"Cannot delete '{name}' — {linked} client version(s) still assigned. "
            "Reassign or delete those clients first."
        )
    coach = session.get(Coach, coach_id)
    if coach is None:
        raise ValueError(f"Coach id={coach_id} not found.")
    name = coach.name
    session.delete(coach)
    return name


def delete_coaches_by_ids(session: Session, coach_ids: list[int]) -> tuple[int, list[str]]:
    """Delete multiple coaches. Returns (deleted_count, list_of_error_strings)."""
    deleted, errors = 0, []
    for cid in coach_ids:
        try:
            delete_coach(session, cid)
            deleted += 1
        except ValueError as exc:
            errors.append(str(exc))
    return deleted, errors


def delete_all_coaches(session: Session) -> tuple[int, list[str]]:
    """Delete all coaches that have no client versions attached."""
    coaches = get_all_coaches(session)
    return delete_coaches_by_ids(session, [c.coach_id for c in coaches])


def update_coach(
    session: Session, coach_id: int, name: str, date_joined: date
) -> Coach:
    coach = session.get(Coach, coach_id)
    if coach is None:
        raise ValueError(f"Coach id={coach_id} not found.")
    duplicate = get_coach_by_name(session, name)
    if duplicate and duplicate.coach_id != coach_id:
        raise ValueError(f"Another coach named '{name}' already exists.")
    coach.name = name
    coach.date_joined = date_joined
    session.commit()
    session.refresh(coach)
    return coach
