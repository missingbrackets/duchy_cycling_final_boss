"""Unit tests for the analytics service.

Run with: python -m pytest tests/ -v
"""
from __future__ import annotations

from datetime import date
import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.analytics import (
    VersionSnapshot,
    _is_active_in_month,
    _month_bounds,
    compute_monthly_rows,
    aggregate_monthly_summary,
    current_mrr,
    project_yearly_method_a,
    project_yearly_method_b,
    project_yearly_method_c,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_version(
    client_id: int = 1,
    coach_id: int = 1,
    monthly_rate: float = 200.0,
    commission_pct: float = 0.20,
    start: str = "2024-01-01",
    end: str | None = None,
    eff_from: str = "2024-01-01",
    eff_to: str | None = None,
) -> VersionSnapshot:
    return VersionSnapshot(
        client_id=client_id,
        client_name=f"Client{client_id}",
        coach_id=coach_id,
        coach_name=f"Coach{coach_id}",
        monthly_rate_gbp=monthly_rate,
        commission_pct=commission_pct,
        start_date=date.fromisoformat(start),
        end_date=date.fromisoformat(end) if end else None,
        effective_from=date.fromisoformat(eff_from),
        effective_to=date.fromisoformat(eff_to) if eff_to else None,
    )


# ---------------------------------------------------------------------------
# _is_active_in_month
# ---------------------------------------------------------------------------

class TestIsActiveInMonth:
    def test_active_whole_month(self):
        v = make_version(start="2024-01-01", eff_from="2024-01-01")
        assert _is_active_in_month(v, 2024, 3) is True

    def test_starts_during_month(self):
        v = make_version(start="2024-03-15", eff_from="2024-03-15")
        assert _is_active_in_month(v, 2024, 3) is True

    def test_starts_after_month(self):
        v = make_version(start="2024-04-01", eff_from="2024-04-01")
        assert _is_active_in_month(v, 2024, 3) is False

    def test_ended_before_month(self):
        v = make_version(start="2024-01-01", end="2024-02-28", eff_from="2024-01-01", eff_to="2024-02-28")
        assert _is_active_in_month(v, 2024, 3) is False

    def test_ended_during_month(self):
        v = make_version(start="2024-01-01", end="2024-03-15", eff_from="2024-01-01", eff_to="2024-03-15")
        assert _is_active_in_month(v, 2024, 3) is True

    def test_superseded_version_excluded(self):
        """A version closed before the month should not count."""
        v = make_version(eff_from="2024-01-01", eff_to="2024-01-31")
        assert _is_active_in_month(v, 2024, 3) is False

    def test_superseded_version_current_month_included(self):
        """A version closing at end of query month counts."""
        v = make_version(eff_from="2024-01-01", eff_to="2024-03-31")
        assert _is_active_in_month(v, 2024, 3) is True


# ---------------------------------------------------------------------------
# compute_monthly_rows
# ---------------------------------------------------------------------------

class TestComputeMonthlyRows:
    def test_basic_single_client(self):
        v = make_version(monthly_rate=300.0, commission_pct=0.20)
        rows = compute_monthly_rows([v], (2024, 1), (2024, 3))
        assert len(rows) == 3
        assert all(r.monthly_rate_gbp == 300.0 for r in rows)
        assert all(abs(r.commission_gbp - 60.0) < 0.01 for r in rows)
        assert all(abs(r.coach_income_gbp - 240.0) < 0.01 for r in rows)

    def test_cancelled_client_excluded(self):
        v = make_version(
            start="2024-01-01", end="2024-02-28",
            eff_from="2024-01-01", eff_to="2024-02-28",
        )
        rows = compute_monthly_rows([v], (2024, 1), (2024, 3))
        months = [(r.year, r.month) for r in rows]
        assert (2024, 3) not in months
        assert (2024, 1) in months and (2024, 2) in months

    def test_two_clients_two_coaches(self):
        v1 = make_version(client_id=1, coach_id=1, monthly_rate=200.0)
        v2 = make_version(client_id=2, coach_id=2, monthly_rate=300.0)
        rows = compute_monthly_rows([v1, v2], (2024, 1), (2024, 1))
        assert len(rows) == 2
        total_mrr = sum(r.monthly_rate_gbp for r in rows)
        assert abs(total_mrr - 500.0) < 0.01


# ---------------------------------------------------------------------------
# aggregate_monthly_summary
# ---------------------------------------------------------------------------

class TestAggregateMonthly:
    def test_churn_counted(self):
        v_new = make_version(client_id=1, coach_id=1, start="2024-03-10", eff_from="2024-03-10")
        v_dropped = make_version(
            client_id=2, coach_id=1,
            start="2024-01-01", end="2024-03-20",
            eff_from="2024-01-01", eff_to="2024-03-20",
        )
        summaries = aggregate_monthly_summary([v_new, v_dropped], (2024, 3), (2024, 3))
        march = summaries[0]
        assert march.new_clients == 1
        assert march.dropped_clients == 1

    def test_mrr_accumulates(self):
        v1 = make_version(client_id=1, coach_id=1, monthly_rate=100.0)
        v2 = make_version(client_id=2, coach_id=1, monthly_rate=200.0)
        summaries = aggregate_monthly_summary([v1, v2], (2024, 1), (2024, 1))
        jan = summaries[0]
        assert abs(jan.total_mrr_gbp - 300.0) < 0.01
        assert jan.active_clients == 2


# ---------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------

class TestProjections:
    def _basic_snapshot(self) -> list[VersionSnapshot]:
        return [make_version(monthly_rate=1000.0, commission_pct=0.20)]

    def test_method_a(self):
        snaps = self._basic_snapshot()
        result = project_yearly_method_a(snaps, date(2024, 3, 1))
        assert abs(result - 12_000.0) < 0.01

    def test_method_b(self):
        snaps = self._basic_snapshot()
        result = project_yearly_method_b(snaps, date(2024, 3, 1))
        assert abs(result - 12_000.0) < 0.01

    def test_method_c(self):
        # Use a version that started well before the 6-month trailing window
        # so all 6 months have full MRR (no early-start zeros)
        snaps = [make_version(monthly_rate=1000.0, commission_pct=0.20,
                              start="2020-01-01", eff_from="2020-01-01")]
        result = project_yearly_method_c(snaps, date(2024, 3, 1))
        assert abs(result - 12_000.0) < 0.01

    def test_method_a_no_clients(self):
        result = project_yearly_method_a([], date(2024, 3, 1))
        assert result == 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_month_bounds_january(self):
        first, last = _month_bounds(2024, 1)
        assert first == date(2024, 1, 1)
        assert last == date(2024, 1, 31)

    def test_month_bounds_february_leap(self):
        first, last = _month_bounds(2024, 2)
        assert last == date(2024, 2, 29)  # 2024 is leap year

    def test_month_bounds_february_non_leap(self):
        first, last = _month_bounds(2023, 2)
        assert last == date(2023, 2, 28)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
