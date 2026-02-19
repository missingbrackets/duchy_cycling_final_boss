"""Client repository — all DB operations for Client and ClientVersion."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from models.client import Client, ClientVersion


# ---------------------------------------------------------------------------
# Client (identity)
# ---------------------------------------------------------------------------

def create_client(session: Session, display_name: str) -> Client:
    client = Client(display_name=display_name)
    session.add(client)
    session.flush()  # get client_id without committing
    return client


def get_client_by_id(session: Session, client_id: int) -> Client | None:
    return (
        session.query(Client)
        .options(joinedload(Client.versions))
        .filter(Client.client_id == client_id)
        .first()
    )


def get_all_clients(session: Session) -> list[Client]:
    return (
        session.query(Client)
        .options(joinedload(Client.versions))
        .order_by(Client.display_name)
        .all()
    )


def find_client_by_name_and_phone(
    session: Session, display_name: str, phone: str | None
) -> Client | None:
    """De-dup strategy: match on (display_name + phone) or display_name alone if phone missing."""
    q = session.query(Client).filter(Client.display_name == display_name)
    if phone:
        # Try exact match with phone via version
        match = (
            session.query(Client)
            .join(Client.versions)
            .filter(Client.display_name == display_name, ClientVersion.client_phone == phone)
            .first()
        )
        if match:
            return match
    return q.first()


def find_client_by_email(session: Session, email: str) -> Client | None:
    return (
        session.query(Client)
        .join(Client.versions)
        .filter(ClientVersion.client_email == email)
        .first()
    )


# ---------------------------------------------------------------------------
# ClientVersion
# ---------------------------------------------------------------------------

def get_active_version(session: Session, client_id: int) -> ClientVersion | None:
    """Return the currently open version (effective_to IS NULL) for a client."""
    return (
        session.query(ClientVersion)
        .options(
            joinedload(ClientVersion.client),
            joinedload(ClientVersion.coach),
        )
        .filter(
            ClientVersion.client_id == client_id,
            ClientVersion.effective_to.is_(None),
        )
        .first()
    )


def get_active_version_at(
    session: Session, client_id: int, as_of: date
) -> ClientVersion | None:
    """Return the version effective on a specific date."""
    return (
        session.query(ClientVersion)
        .options(
            joinedload(ClientVersion.client),
            joinedload(ClientVersion.coach),
        )
        .filter(
            ClientVersion.client_id == client_id,
            ClientVersion.effective_from <= as_of,
            (ClientVersion.effective_to.is_(None)) | (ClientVersion.effective_to >= as_of),
        )
        .first()
    )


def create_initial_version(
    session: Session,
    client_id: int,
    coach_id: int,
    source: str,
    client_email: Optional[str],
    client_phone: Optional[str],
    monthly_rate_gbp: float,
    commission_pct: float,
    start_date: date,
    end_date: Optional[date] = None,
) -> ClientVersion:
    """Create the first version for a new client."""
    version = ClientVersion(
        client_id=client_id,
        coach_id=coach_id,
        source=source,
        client_email=client_email or None,
        client_phone=client_phone,
        monthly_rate_gbp=monthly_rate_gbp,
        commission_pct=commission_pct,
        start_date=start_date,
        end_date=end_date,
        effective_from=start_date,
        effective_to=None,
    )
    session.add(version)
    return version


def update_client_version(
    session: Session,
    client_id: int,
    coach_id: int,
    source: str,
    client_email: Optional[str],
    client_phone: Optional[str],
    monthly_rate_gbp: float,
    commission_pct: float,
    effective_from: date,
) -> ClientVersion:
    """Close the current open version and open a new one from effective_from."""
    current = get_active_version(session, client_id)
    if current is None:
        raise ValueError(f"No active version found for client_id={client_id}")

    # Close the current version: effective_to = effective_from - 1 day
    current.effective_to = effective_from - timedelta(days=1)

    new_version = ClientVersion(
        client_id=client_id,
        coach_id=coach_id,
        source=source,
        client_email=client_email or None,
        client_phone=client_phone,
        monthly_rate_gbp=monthly_rate_gbp,
        commission_pct=commission_pct,
        start_date=current.start_date,  # original start date preserved
        end_date=None,
        effective_from=effective_from,
        effective_to=None,
    )
    session.add(new_version)
    return new_version


def cancel_client(
    session: Session, client_id: int, end_date: date
) -> ClientVersion:
    """Set end_date on active version; also close effective_to on same day."""
    current = get_active_version(session, client_id)
    if current is None:
        raise ValueError(f"No active version found for client_id={client_id}")

    current.end_date = end_date
    current.effective_to = end_date  # version closes when client cancels
    return current


def get_all_versions(session: Session) -> list[ClientVersion]:
    return (
        session.query(ClientVersion)
        .options(
            joinedload(ClientVersion.client),
            joinedload(ClientVersion.coach),
        )
        .order_by(ClientVersion.client_id, ClientVersion.effective_from)
        .all()
    )
