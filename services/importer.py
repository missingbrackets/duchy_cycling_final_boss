"""CSV import service.

Import behaviour:
- De-dup strategy: match on (display_name + phone) first; fall back to email; fall back to name.
- Each row in the CSV creates one ClientVersion (sorted by start_date if multiple rows
  per client).
- Coaches are auto-created if missing (when auto_create_coaches=True).
- commission_pct is normalised to 0-1 (handles "20%", "0.20", "20").
- Dates parsed with UK-first heuristics (day-month-year).
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd
from dateutil import parser as dateutil_parser

from core.config import SOURCE_OPTIONS
from repositories.coach_repo import get_or_create_coach
from repositories.client_repo import (
    create_client,
    create_initial_version,
    find_client_by_email,
    find_client_by_name_and_phone,
)


# ---------------------------------------------------------------------------
# Column auto-mapping
# ---------------------------------------------------------------------------

COLUMN_ALIASES: dict[str, list[str]] = {
    "coach": ["coach", "coach_name", "trainer"],
    "name": ["name", "client_name", "client", "display_name"],
    "source": ["source", "acquisition", "lead_source", "channel"],
    "email": ["email", "client_email", "e-mail"],
    "phone": ["phone", "client_phone", "telephone", "mobile"],
    "monthly_rate": ["monthly_rate", "rate", "monthly_rate_gbp", "price", "fee"],
    "commission_pct": [
        "commission_pct", "commission", "commission_%", "commission_percent"
    ],
    "start_date": ["start_date", "start", "joined", "date_joined", "date_started"],
    "end_date": ["end_date", "end", "cancelled", "cancel_date", "date_ended"],
}


def auto_map_columns(columns: list[str]) -> dict[str, str]:
    """Return {canonical_name: actual_column} for best-effort auto-mapping."""
    lower = {c.lower().strip(): c for c in columns}
    mapping: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower:
                mapping[canonical] = lower[alias]
                break
    return mapping


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_date(val: str) -> date | None:
    if not val or pd.isna(val):
        return None
    val = str(val).strip()
    # Try ISO format first (YYYY-MM-DD) to avoid dayfirst ambiguity
    import re as _re
    if _re.match(r"^\d{4}-\d{2}-\d{2}$", val):
        try:
            return date.fromisoformat(val)
        except ValueError:
            pass
    try:
        # dayfirst=True for UK format (DD/MM/YYYY etc.)
        return dateutil_parser.parse(val, dayfirst=True).date()
    except Exception:
        return None


def _parse_commission(val) -> float | None:
    """Normalise commission to 0-1 decimal."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().replace("%", "").replace(",", "")
    try:
        f = float(s)
        return f / 100 if f > 1 else f
    except ValueError:
        return None


def _parse_rate(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().replace("£", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _norm_source(val: str | None) -> str:
    if not val:
        return "Organic"
    val = str(val).strip()
    for s in SOURCE_OPTIONS:
        if s.lower() == val.lower():
            return s
    return "Organic"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class ImportRow:
    row_number: int
    coach: str = ""
    name: str = ""
    source: str = ""
    email: str | None = None
    phone: str | None = None
    monthly_rate: float | None = None
    commission_pct: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


@dataclass
class ImportResult:
    total_rows: int = 0
    valid_rows: int = 0
    clients_created: int = 0
    coaches_created: int = 0
    versions_created: int = 0
    skipped_rows: int = 0
    errors: list[dict] = field(default_factory=list)


def parse_and_validate(df: pd.DataFrame, col_map: dict[str, str]) -> list[ImportRow]:
    rows: list[ImportRow] = []
    for idx, raw in df.iterrows():
        r = ImportRow(row_number=int(idx) + 2)  # +2 for 1-index + header

        def get(canonical: str) -> str:
            col = col_map.get(canonical)
            if col is None:
                return ""
            val = raw.get(col, "")
            return "" if pd.isna(val) else str(val).strip()

        r.coach = get("coach")
        r.name = get("name")
        r.source = _norm_source(get("source"))
        r.email = get("email") or None
        r.phone = get("phone") or None
        r.monthly_rate = _parse_rate(get("monthly_rate"))
        r.commission_pct = _parse_commission(get("commission_pct"))
        r.start_date = _parse_date(get("start_date"))
        r.end_date = _parse_date(get("end_date"))

        if not r.coach:
            r.errors.append("Missing: coach")
        if not r.name:
            r.errors.append("Missing: name")
        if r.monthly_rate is None:
            r.errors.append("Missing/invalid: monthly_rate")
        if r.commission_pct is None:
            r.errors.append("Missing/invalid: commission_pct")
        if r.start_date is None:
            r.errors.append("Missing/invalid: start_date")

        rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# Import execution
# ---------------------------------------------------------------------------

def execute_import(
    session,
    rows: list[ImportRow],
    auto_create_coaches: bool = True,
) -> ImportResult:
    result = ImportResult(total_rows=len(rows))

    coaches_cache: dict[str, int] = {}

    # Group valid rows by (name, phone/email) to detect multi-version clients
    from collections import defaultdict
    valid_rows = [r for r in rows if r.is_valid]
    result.valid_rows = len(valid_rows)

    # Sort valid rows by (name, start_date) for version ordering
    valid_rows.sort(key=lambda r: (r.name, r.start_date or date.min))

    for r in valid_rows:
        try:
            # Resolve coach
            if r.coach not in coaches_cache:
                existing_coaches_before = session.query(
                    __import__("models.coach", fromlist=["Coach"]).Coach
                ).count()
                coach = get_or_create_coach(session, r.coach)
                after_count = session.query(
                    __import__("models.coach", fromlist=["Coach"]).Coach
                ).count()
                if after_count > existing_coaches_before:
                    result.coaches_created += 1
                coaches_cache[r.coach] = coach.coach_id
            coach_id = coaches_cache[r.coach]

            # Resolve or create client (de-dup)
            client = None
            if r.email:
                client = find_client_by_email(session, r.email)
            if client is None:
                client = find_client_by_name_and_phone(session, r.name, r.phone)
            if client is None:
                client = create_client(session, r.name)
                session.flush()
                result.clients_created += 1

            # Create version
            create_initial_version(
                session=session,
                client_id=client.client_id,
                coach_id=coach_id,
                source=r.source,
                client_email=r.email,
                client_phone=r.phone,
                monthly_rate_gbp=r.monthly_rate,
                commission_pct=r.commission_pct,
                start_date=r.start_date,
                end_date=r.end_date,
            )
            result.versions_created += 1

        except Exception as exc:
            result.errors.append({"row": r.row_number, "name": r.name, "error": str(exc)})
            result.skipped_rows += 1

    for r in rows:
        if not r.is_valid:
            result.skipped_rows += 1
            for err in r.errors:
                result.errors.append({"row": r.row_number, "name": r.name, "error": err})

    return result


def read_csv_bytes(data: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(data))
