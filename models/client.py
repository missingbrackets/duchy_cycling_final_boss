"""Client and ClientVersion SQLAlchemy models (SCD Type-2 history)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import String, Date, DateTime, Numeric, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class Client(Base):
    """Stable identity for a client. Never mutated once created."""

    __tablename__ = "clients"

    client_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    versions: Mapped[list["ClientVersion"]] = relationship(
        "ClientVersion", back_populates="client", order_by="ClientVersion.effective_from"
    )

    def __repr__(self) -> str:
        return f"<Client id={self.client_id} name={self.display_name!r}>"


class ClientVersion(Base):
    """One effective-dated snapshot of a client's terms.

    Active version: effective_to IS NULL.
    Cancelled client: end_date IS NOT NULL on active version.

    How 'current active' is resolved for a given date D:
        effective_from <= D AND (effective_to IS NULL OR effective_to >= D)
        AND (end_date IS NULL OR end_date > D)
    """

    __tablename__ = "client_versions"

    client_version_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.client_id"), nullable=False)
    coach_id: Mapped[int] = mapped_column(ForeignKey("coaches.coach_id"), nullable=False)

    source: Mapped[str] = mapped_column(String(50), nullable=False)
    client_email: Mapped[str | None] = mapped_column(String(300), nullable=True)
    client_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    monthly_rate_gbp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    commission_pct: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # SCD2 effective dating
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    client: Mapped["Client"] = relationship("Client", back_populates="versions")
    coach: Mapped["Coach"] = relationship("Coach", back_populates="client_versions")

    # ------------------------------------------------------------------
    # Derived helpers (not stored)
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """True if this version is the current open version (not superseded)."""
        return self.effective_to is None

    @property
    def is_active(self) -> bool:
        """True if open AND not cancelled."""
        return self.is_open and self.end_date is None

    @property
    def monthly_commission_gbp(self) -> float:
        return float(self.monthly_rate_gbp) * float(self.commission_pct)

    @property
    def coach_income_gbp(self) -> float:
        return float(self.monthly_rate_gbp) - self.monthly_commission_gbp

    def __repr__(self) -> str:
        return (
            f"<ClientVersion id={self.client_version_id} "
            f"client={self.client_id} "
            f"eff={self.effective_from}..{self.effective_to}>"
        )
