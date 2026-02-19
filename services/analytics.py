"""Analytics service.

Definitions (documented assumptions):
- A client is considered **active in a given calendar month** if:
    effective_from <= last_day_of_month
    AND (effective_to IS NULL OR effective_to >= first_day_of_month)
    AND (end_date IS NULL OR end_date >= first_day_of_month)
  i.e. active at ANY point during the month (no proration).

- Monthly Revenue for a client-month = monthly_rate_gbp (no proration).
- Monthly Commission = monthly_rate_gbp * commission_pct.
- Coach Income = monthly_rate_gbp - commission.

All functions return plain Python structures (no SQLAlchemy objects) so they
are unit-testable without a live DB session.
"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class VersionSnapshot:
    """Minimal snapshot of a ClientVersion row for analytics."""
    client_id: int
    client_name: str
    coach_id: int
    coach_name: str
    monthly_rate_gbp: float
    commission_pct: float
    start_date: date
    end_date: date | None
    effective_from: date
    effective_to: date | None


@dataclass
class MonthlyRow:
    year: int
    month: int
    coach_id: int
    coach_name: str
    client_id: int
    client_name: str
    monthly_rate_gbp: float
    commission_gbp: float
    coach_income_gbp: float


@dataclass
class MonthlySummary:
    year: int
    month: int
    coach_id: int
    coach_name: str
    active_clients: int = 0
    total_mrr_gbp: float = 0.0
    total_commission_gbp: float = 0.0
    total_coach_income_gbp: float = 0.0
    new_clients: int = 0
    dropped_clients: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return first, last


def _is_active_in_month(v: VersionSnapshot, year: int, month: int) -> bool:
    first, last = _month_bounds(year, month)
    if v.effective_from > last:
        return False
    if v.effective_to is not None and v.effective_to < first:
        return False
    if v.end_date is not None and v.end_date < first:
        return False
    return True


def _month_range(start: date, end: date) -> list[tuple[int, int]]:
    """Yield (year, month) tuples from start to end inclusive."""
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return months


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_monthly_rows(
    versions: list[VersionSnapshot],
    from_month: tuple[int, int],
    to_month: tuple[int, int],
) -> list[MonthlyRow]:
    """Build a flat list of (month, coach, client, financials) rows."""
    all_months = _month_range(
        date(from_month[0], from_month[1], 1),
        date(to_month[0], to_month[1], 1),
    )
    rows: list[MonthlyRow] = []
    for year, month in all_months:
        for v in versions:
            if _is_active_in_month(v, year, month):
                commission = v.monthly_rate_gbp * v.commission_pct
                rows.append(
                    MonthlyRow(
                        year=year,
                        month=month,
                        coach_id=v.coach_id,
                        coach_name=v.coach_name,
                        client_id=v.client_id,
                        client_name=v.client_name,
                        monthly_rate_gbp=v.monthly_rate_gbp,
                        commission_gbp=commission,
                        coach_income_gbp=v.monthly_rate_gbp - commission,
                    )
                )
    return rows


def aggregate_monthly_summary(
    versions: list[VersionSnapshot],
    from_month: tuple[int, int],
    to_month: tuple[int, int],
) -> list[MonthlySummary]:
    """Aggregate monthly rows into per-coach per-month summaries including churn."""
    all_months = _month_range(
        date(from_month[0], from_month[1], 1),
        date(to_month[0], to_month[1], 1),
    )

    # Key: (year, month, coach_id)
    summaries: dict[tuple, MonthlySummary] = {}

    # Initialise for all coaches that appear in any version
    coaches: dict[int, str] = {v.coach_id: v.coach_name for v in versions}

    for year, month in all_months:
        for coach_id, coach_name in coaches.items():
            key = (year, month, coach_id)
            summaries[key] = MonthlySummary(
                year=year, month=month, coach_id=coach_id, coach_name=coach_name
            )

    # Active clients and financials
    for year, month in all_months:
        first, last = _month_bounds(year, month)
        for v in versions:
            if _is_active_in_month(v, year, month):
                key = (year, month, v.coach_id)
                s = summaries[key]
                commission = v.monthly_rate_gbp * v.commission_pct
                s.active_clients += 1
                s.total_mrr_gbp += v.monthly_rate_gbp
                s.total_commission_gbp += commission
                s.total_coach_income_gbp += v.monthly_rate_gbp - commission

            # New clients: start_date falls in this month
            if v.start_date.year == year and v.start_date.month == month:
                key = (year, month, v.coach_id)
                if key in summaries:
                    summaries[key].new_clients += 1

            # Dropped clients: end_date falls in this month
            if v.end_date and v.end_date.year == year and v.end_date.month == month:
                key = (year, month, v.coach_id)
                if key in summaries:
                    summaries[key].dropped_clients += 1

    return sorted(summaries.values(), key=lambda s: (s.year, s.month, s.coach_name))


# ---------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------

def current_mrr(versions: list[VersionSnapshot], as_of: date) -> float:
    """Sum of monthly_rate_gbp for all active versions as of today."""
    return sum(
        v.monthly_rate_gbp
        for v in versions
        if _is_active_in_month(v, as_of.year, as_of.month)
    )


def project_yearly_method_a(versions: list[VersionSnapshot], as_of: date) -> float:
    """Method A: 12 * current month MRR."""
    return 12 * current_mrr(versions, as_of)


def _trailing_avg_mrr(
    versions: list[VersionSnapshot], as_of: date, n_months: int
) -> float:
    """Average MRR over the trailing n_months months (inclusive of current)."""
    total = 0.0
    months_counted = 0
    y, m = as_of.year, as_of.month
    for _ in range(n_months):
        total += sum(
            v.monthly_rate_gbp for v in versions if _is_active_in_month(v, y, m)
        )
        months_counted += 1
        if m == 1:
            y -= 1
            m = 12
        else:
            m -= 1
    return total / max(months_counted, 1)


def project_yearly_method_b(versions: list[VersionSnapshot], as_of: date) -> float:
    """Method B: trailing 3-month average MRR * 12."""
    return 12 * _trailing_avg_mrr(versions, as_of, 3)


def project_yearly_method_c(versions: list[VersionSnapshot], as_of: date) -> float:
    """Method C: trailing 6-month average MRR * 12."""
    return 12 * _trailing_avg_mrr(versions, as_of, 6)


def _trailing_avg_metric(
    versions: list[VersionSnapshot], as_of: date, n_months: int, use_commission: bool
) -> float:
    """Generalised trailing average over n_months for either revenue or commission."""
    total = 0.0
    y, m = as_of.year, as_of.month
    for _ in range(n_months):
        for v in versions:
            if _is_active_in_month(v, y, m):
                total += (
                    v.monthly_rate_gbp * v.commission_pct
                    if use_commission
                    else v.monthly_rate_gbp
                )
        if m == 1:
            y -= 1
            m = 12
        else:
            m -= 1
    return total / max(n_months, 1)


def projection_series(
    versions: list[VersionSnapshot],
    from_month: tuple[int, int],
    to_month: tuple[int, int],
    use_commission: bool = False,
) -> list[dict]:
    """For every month in [from_month, to_month] compute all 3 projections.

    use_commission=False → project MRR (total revenue)
    use_commission=True  → project commission total (duchy income)

    Returns a list of dicts with keys: Month, Method A, Method B, Method C.
    """
    all_months = _month_range(
        date(from_month[0], from_month[1], 1),
        date(to_month[0], to_month[1], 1),
    )
    result = []
    for year, month in all_months:
        as_of = date(year, month, 1)
        result.append({
            "Month": f"{year}-{month:02d}",
            "Method A (12×current)": round(12 * _trailing_avg_metric(versions, as_of, 1, use_commission), 2),
            "Method B (3-mo avg)":   round(12 * _trailing_avg_metric(versions, as_of, 3, use_commission), 2),
            "Method C (6-mo avg)":   round(12 * _trailing_avg_metric(versions, as_of, 6, use_commission), 2),
        })
    return result


def churn_summary_by_coach(
    versions: list[VersionSnapshot],
    from_month: tuple[int, int],
    to_month: tuple[int, int],
) -> list[dict]:
    """Per-coach totals of new / dropped / net clients in the date range.

    Returns list of dicts: coach, new_clients, dropped_clients, net, months_in_range.
    """
    summaries = aggregate_monthly_summary(versions, from_month, to_month)
    coaches: dict[str, dict] = {}
    for s in summaries:
        if s.coach_name not in coaches:
            coaches[s.coach_name] = {
                "Coach": s.coach_name,
                "New": 0,
                "Dropped": 0,
                "Months": 0,
            }
        coaches[s.coach_name]["New"] += s.new_clients
        coaches[s.coach_name]["Dropped"] += s.dropped_clients
        coaches[s.coach_name]["Months"] += 1
    result = []
    for c in coaches.values():
        c["Net"] = c["New"] - c["Dropped"]
        c["Avg Monthly Net"] = round(c["Net"] / max(c["Months"], 1), 2)
        result.append(c)
    return sorted(result, key=lambda x: x["Coach"])


# ---------------------------------------------------------------------------
# Commissions owed (by coach, by month)
# ---------------------------------------------------------------------------

@dataclass
class CommissionOwed:
    year: int
    month: int
    coach_id: int
    coach_name: str
    total_commission_gbp: float


def commissions_owed(
    versions: list[VersionSnapshot],
    from_month: tuple[int, int],
    to_month: tuple[int, int],
) -> list[CommissionOwed]:
    summaries = aggregate_monthly_summary(versions, from_month, to_month)
    return [
        CommissionOwed(
            year=s.year,
            month=s.month,
            coach_id=s.coach_id,
            coach_name=s.coach_name,
            total_commission_gbp=s.total_commission_gbp,
        )
        for s in summaries
    ]


# ---------------------------------------------------------------------------
# Helper: load versions from DB into VersionSnapshots
# ---------------------------------------------------------------------------

def load_version_snapshots(session) -> list[VersionSnapshot]:  # type: ignore[type-arg]
    """Load all ClientVersion rows into plain VersionSnapshot objects."""
    from models.client import ClientVersion  # avoid circular at module load

    rows = (
        session.query(ClientVersion)
        .all()
    )
    snapshots = []
    for r in rows:
        snapshots.append(
            VersionSnapshot(
                client_id=r.client_id,
                client_name=r.client.display_name,
                coach_id=r.coach_id,
                coach_name=r.coach.name,
                monthly_rate_gbp=float(r.monthly_rate_gbp),
                commission_pct=float(r.commission_pct),
                start_date=r.start_date,
                end_date=r.end_date,
                effective_from=r.effective_from,
                effective_to=r.effective_to,
            )
        )
    return snapshots
