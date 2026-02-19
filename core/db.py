"""Database engine and session management."""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

from core.config import get_database_url


class Base(DeclarativeBase):
    pass


def _get_engine():
    url = get_database_url()
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})
        # Enable WAL for better concurrent read performance with SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        return engine
    return create_engine(url)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _get_engine()
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def get_session() -> Session:
    factory = get_session_factory()
    return factory()


def init_db() -> None:
    """Create all tables if they do not exist."""
    # Import models so they register with Base.metadata
    import models.coach  # noqa: F401
    import models.client  # noqa: F401
    import models.audit  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
