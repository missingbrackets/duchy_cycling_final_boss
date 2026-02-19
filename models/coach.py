"""Coach SQLAlchemy model."""
from __future__ import annotations

from datetime import date

from sqlalchemy import String, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class Coach(Base):
    __tablename__ = "coaches"

    coach_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    date_joined: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationship back to client versions
    client_versions: Mapped[list["ClientVersion"]] = relationship(  # noqa: F821
        "ClientVersion", back_populates="coach"
    )

    def __repr__(self) -> str:
        return f"<Coach id={self.coach_id} name={self.name!r}>"
