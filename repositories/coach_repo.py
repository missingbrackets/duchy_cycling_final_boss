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
