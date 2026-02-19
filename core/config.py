"""Central configuration and constants."""
import os
from enum import Enum


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_database_url() -> str:
    """Return the SQLAlchemy database URL.

    Priority:
    1. DATABASE_URL env var
    2. Streamlit secrets (DATABASE_URL key)
    3. Local SQLite default
    """
    if url := os.environ.get("DATABASE_URL"):
        return url

    try:
        import streamlit as st  # type: ignore
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        pass

    return "sqlite:///./duchy_coaching.db"


# ---------------------------------------------------------------------------
# Domain enums / constants
# ---------------------------------------------------------------------------

class Source(str, Enum):
    GOOGLE_AD = "Google Ad"
    INSTAGRAM = "Instagram"
    ORGANIC = "Organic"
    REFERRAL = "Referral"
    STRAVA = "Strava"


SOURCE_OPTIONS: list[str] = [s.value for s in Source]


class ActionType(str, Enum):
    CREATE_CLIENT = "CREATE_CLIENT"
    UPDATE_COACH = "UPDATE_COACH"
    UPDATE_CLIENT = "UPDATE_CLIENT"
    CANCEL_CLIENT = "CANCEL_CLIENT"
    CREATE_COACH = "CREATE_COACH"
    IMPORT_CSV = "IMPORT_CSV"
    EXPORT_CSV = "EXPORT_CSV"


class EntityType(str, Enum):
    CLIENT = "CLIENT"
    COACH = "COACH"
    IMPORT = "IMPORT"


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_gbp(value: float | None) -> str:
    """Format a float as GBP currency string."""
    if value is None:
        return "£0.00"
    return f"£{value:,.2f}"


def fmt_pct(value: float | None) -> str:
    """Format a 0-1 decimal as percentage string."""
    if value is None:
        return "0.0%"
    return f"{value * 100:.1f}%"


APP_TITLE = "Duchy Coaching Manager"
DEFAULT_USER = "local"
