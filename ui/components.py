"""Shared Streamlit UI components and helpers."""
from __future__ import annotations

import streamlit as st
from core.config import fmt_gbp, fmt_pct


def metric_card(label: str, value: str, delta: str | None = None) -> None:
    st.metric(label=label, value=value, delta=delta)


def section_header(title: str, divider: bool = True) -> None:
    st.subheader(title)
    if divider:
        st.divider()


def success_toast(msg: str) -> None:
    st.success(msg)


def error_toast(msg: str) -> None:
    st.error(msg)


def version_to_dict(version) -> dict:
    """Convert a ClientVersion ORM object to a plain dict for JSON serialisation."""
    return {
        "client_version_id": version.client_version_id,
        "client_id": version.client_id,
        "coach_id": version.coach_id,
        "source": version.source,
        "client_email": version.client_email,
        "client_phone": version.client_phone,
        "monthly_rate_gbp": float(version.monthly_rate_gbp),
        "commission_pct": float(version.commission_pct),
        "start_date": str(version.start_date),
        "end_date": str(version.end_date) if version.end_date else None,
        "effective_from": str(version.effective_from),
        "effective_to": str(version.effective_to) if version.effective_to else None,
    }


def get_current_user() -> str:
    """Return the current logged-in username from session state, or 'local'."""
    return st.session_state.get("auth_user", "local")
