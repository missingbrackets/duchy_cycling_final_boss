"""Unit tests for the CSV importer parsing helpers."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import io
import pandas as pd
from services.importer import (
    auto_map_columns,
    parse_and_validate,
    _parse_commission,
    _parse_date,
    _parse_rate,
    _norm_source,
)


class TestParseCommission:
    def test_percent_string(self):
        assert abs(_parse_commission("20%") - 0.20) < 0.001

    def test_decimal_string(self):
        assert abs(_parse_commission("0.20") - 0.20) < 0.001

    def test_int_string(self):
        assert abs(_parse_commission("20") - 0.20) < 0.001

    def test_float(self):
        assert abs(_parse_commission(0.20) - 0.20) < 0.001

    def test_none(self):
        assert _parse_commission(None) is None


class TestParseDate:
    def test_uk_format(self):
        from datetime import date
        d = _parse_date("01/06/2024")
        assert d == date(2024, 6, 1)

    def test_iso_format(self):
        from datetime import date
        d = _parse_date("2024-06-01")
        assert d == date(2024, 6, 1)

    def test_empty_string(self):
        assert _parse_date("") is None

    def test_invalid(self):
        assert _parse_date("not-a-date") is None


class TestAutoMapColumns:
    def test_standard_names(self):
        cols = ["coach", "name", "source", "email", "phone", "monthly_rate", "commission_pct", "start_date"]
        mapping = auto_map_columns(cols)
        assert mapping["coach"] == "coach"
        assert mapping["name"] == "name"
        assert mapping["monthly_rate"] == "monthly_rate"

    def test_alias_names(self):
        cols = ["trainer", "client_name", "acquisition", "fee", "commission", "joined"]
        mapping = auto_map_columns(cols)
        assert mapping.get("coach") == "trainer"
        assert mapping.get("name") == "client_name"
        assert mapping.get("monthly_rate") == "fee"

    def test_case_insensitive(self):
        cols = ["Coach", "Name", "Monthly_Rate"]
        mapping = auto_map_columns(cols)
        assert "coach" in mapping
        assert "name" in mapping


class TestParseAndValidate:
    def _make_df(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_valid_row(self):
        df = self._make_df([{
            "coach": "Alice", "name": "Bob", "source": "Organic",
            "monthly_rate": "200", "commission_pct": "20%",
            "start_date": "01/01/2024",
        }])
        col_map = {k: k for k in df.columns}
        rows = parse_and_validate(df, col_map)
        assert len(rows) == 1
        assert rows[0].is_valid
        assert rows[0].commission_pct == 0.20
        assert rows[0].monthly_rate == 200.0

    def test_missing_required_fields(self):
        df = self._make_df([{"coach": "Alice", "name": ""}])
        col_map = {"coach": "coach", "name": "name"}
        rows = parse_and_validate(df, col_map)
        assert not rows[0].is_valid
        errors = rows[0].errors
        assert any("name" in e.lower() for e in errors)

    def test_invalid_commission(self):
        df = self._make_df([{
            "coach": "Alice", "name": "Bob", "source": "Organic",
            "monthly_rate": "200", "commission_pct": "not_a_number",
            "start_date": "01/01/2024",
        }])
        col_map = {k: k for k in df.columns}
        rows = parse_and_validate(df, col_map)
        assert not rows[0].is_valid


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
