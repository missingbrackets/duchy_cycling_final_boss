"""Clients page — add, edit, cancel, and view clients."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import date

from core.config import APP_TITLE, SOURCE_OPTIONS, fmt_gbp, fmt_pct
from core.db import get_session, init_db
from models.client import ClientVersion
from repositories.coach_repo import get_all_coaches
from repositories.client_repo import (
    create_client,
    create_initial_version,
    get_active_version,
    update_client_version,
    cancel_client,
    get_all_versions,
    get_client_by_id,
)
from services.audit import audit_create_client, audit_update_client, audit_cancel_client
from ui.components import version_to_dict, get_current_user

st.set_page_config(page_title=f"Clients — {APP_TITLE}", page_icon="👤", layout="wide")
init_db()

st.title("👤 Clients")

tab_add, tab_edit, tab_cancel, tab_view = st.tabs(
    ["➕ Add Client", "✏️ Edit Client", "❌ Cancel Client", "🔍 Backend View"]
)

# ---------------------------------------------------------------------------
# Tab: Add Client
# ---------------------------------------------------------------------------
with tab_add:
    st.subheader("Add New Client")
    session = get_session()
    try:
        coaches = get_all_coaches(session)
    finally:
        session.close()

    if not coaches:
        st.warning("No coaches found. Please add a coach first.")
    else:
        with st.form("add_client_form", clear_on_submit=True):
            coach_options = {c.name: c.coach_id for c in coaches}
            coach_name = st.selectbox("Coach *", list(coach_options.keys()))
            display_name = st.text_input("Client Name *")
            source = st.selectbox("Source *", SOURCE_OPTIONS)
            client_email = st.text_input("Email (optional)")
            client_phone = st.text_input("Phone")
            monthly_rate = st.number_input("Monthly Rate (£) *", min_value=0.0, step=10.0, format="%.2f")
            commission_pct = st.number_input(
                "Commission % *", min_value=0.0, max_value=100.0, value=20.0, step=1.0, format="%.1f"
            )
            start_date = st.date_input("Start Date *", value=date.today(), format="DD/MM/YYYY")
            submitted = st.form_submit_button("Add Client")

        if submitted:
            errors = []
            if not display_name.strip():
                errors.append("Client name is required.")
            if monthly_rate <= 0:
                errors.append("Monthly rate must be greater than 0.")
            if errors:
                for e in errors:
                    st.error(e)
            else:
                session = get_session()
                try:
                    coach_id = coach_options[coach_name]
                    client = create_client(session, display_name.strip())
                    session.flush()
                    version = create_initial_version(
                        session=session,
                        client_id=client.client_id,
                        coach_id=coach_id,
                        source=source,
                        client_email=client_email.strip() or None,
                        client_phone=client_phone.strip() or None,
                        monthly_rate_gbp=monthly_rate,
                        commission_pct=commission_pct / 100,
                        start_date=start_date,
                    )
                    audit_create_client(
                        session,
                        client.client_id,
                        after=version_to_dict(version),
                        user=get_current_user(),
                    )
                    session.commit()
                    st.success(f"Client **{display_name}** added successfully.")
                except Exception as exc:
                    session.rollback()
                    st.error(f"Error: {exc}")
                finally:
                    session.close()

# ---------------------------------------------------------------------------
# Tab: Edit Client
# ---------------------------------------------------------------------------
with tab_edit:
    st.subheader("Edit Client (creates new version)")
    session = get_session()
    try:
        coaches = get_all_coaches(session)
        all_versions = get_all_versions(session)
    finally:
        session.close()

    # Build list of active clients for selection
    active_clients: dict[str, int] = {}
    for v in all_versions:
        if v.is_open:
            label = f"{v.client.display_name} (coach: {v.coach.name})"
            active_clients[label] = v.client_id

    if not active_clients:
        st.info("No active clients to edit.")
    else:
        client_label = st.selectbox("Select client", list(active_clients.keys()), key="edit_select")
        client_id = active_clients[client_label]

        session = get_session()
        try:
            current = get_active_version(session, client_id)
            coaches_list = get_all_coaches(session)
        finally:
            session.close()

        if current is None:
            st.warning("No active version found.")
        else:
            coach_options = {c.name: c.coach_id for c in coaches_list}
            current_coach_name = next(
                (name for name, cid in coach_options.items() if cid == current.coach_id),
                list(coach_options.keys())[0],
            )

            with st.form("edit_client_form"):
                st.write(f"Editing: **{current.client.display_name}** | Current version effective from {current.effective_from}")
                coach_name_edit = st.selectbox(
                    "Coach", list(coach_options.keys()),
                    index=list(coach_options.keys()).index(current_coach_name),
                )
                source_edit = st.selectbox(
                    "Source", SOURCE_OPTIONS,
                    index=SOURCE_OPTIONS.index(current.source) if current.source in SOURCE_OPTIONS else 0,
                )
                email_edit = st.text_input("Email", value=current.client_email or "")
                phone_edit = st.text_input("Phone", value=current.client_phone or "")
                rate_edit = st.number_input(
                    "Monthly Rate (£)", min_value=0.0, step=10.0,
                    value=float(current.monthly_rate_gbp), format="%.2f",
                )
                commission_edit = st.number_input(
                    "Commission %", min_value=0.0, max_value=100.0, step=1.0,
                    value=float(current.commission_pct) * 100, format="%.1f",
                )
                effective_from = st.date_input(
                    "Effective From (new version start) *",
                    value=date.today(), format="DD/MM/YYYY",
                )
                edit_submitted = st.form_submit_button("Save New Version")

            if edit_submitted:
                session = get_session()
                try:
                    before = version_to_dict(get_active_version(session, client_id))
                    new_version = update_client_version(
                        session=session,
                        client_id=client_id,
                        coach_id=coach_options[coach_name_edit],
                        source=source_edit,
                        client_email=email_edit.strip() or None,
                        client_phone=phone_edit.strip() or None,
                        monthly_rate_gbp=rate_edit,
                        commission_pct=commission_edit / 100,
                        effective_from=effective_from,
                    )
                    audit_update_client(
                        session,
                        client_id=client_id,
                        before=before,
                        after=version_to_dict(new_version),
                        user=get_current_user(),
                    )
                    session.commit()
                    st.success("New client version saved.")
                except Exception as exc:
                    session.rollback()
                    st.error(f"Error: {exc}")
                finally:
                    session.close()

# ---------------------------------------------------------------------------
# Tab: Cancel Client
# ---------------------------------------------------------------------------
with tab_cancel:
    st.subheader("Cancel Client")
    session = get_session()
    try:
        all_versions = get_all_versions(session)
    finally:
        session.close()

    active_for_cancel: dict[str, int] = {
        f"{v.client.display_name} (coach: {v.coach.name})": v.client_id
        for v in all_versions
        if v.is_active
    }

    if not active_for_cancel:
        st.info("No active clients to cancel.")
    else:
        cancel_label = st.selectbox("Select client to cancel", list(active_for_cancel.keys()), key="cancel_select")
        cancel_client_id = active_for_cancel[cancel_label]

        end_date_cancel = st.date_input("End Date *", value=date.today(), format="DD/MM/YYYY", key="cancel_end_date")
        cancel_notes = st.text_area("Notes (optional)")

        if st.button("Cancel Client", type="primary"):
            session = get_session()
            try:
                before = version_to_dict(get_active_version(session, cancel_client_id))
                cancel_client(session, cancel_client_id, end_date_cancel)
                audit_cancel_client(
                    session,
                    client_id=cancel_client_id,
                    before=before,
                    end_date=str(end_date_cancel),
                    user=get_current_user(),
                )
                session.commit()
                st.success(f"Client cancelled with end date {end_date_cancel}.")
            except Exception as exc:
                session.rollback()
                st.error(f"Error: {exc}")
            finally:
                session.close()

# ---------------------------------------------------------------------------
# Tab: Backend View
# ---------------------------------------------------------------------------
with tab_view:
    st.subheader("Client & Version Data")

    session = get_session()
    try:
        all_versions = get_all_versions(session)
        coaches_list = get_all_coaches(session)
    finally:
        session.close()

    # Filters
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        coach_filter = st.multiselect("Filter by Coach", [c.name for c in coaches_list])
    with f_col2:
        status_filter = st.multiselect("Status", ["Active", "Cancelled", "Superseded"])
    with f_col3:
        source_filter = st.multiselect("Source", SOURCE_OPTIONS)

    date_col1, date_col2 = st.columns(2)
    with date_col1:
        start_from = st.date_input("Start date from", value=None, format="DD/MM/YYYY", key="view_start_from")
    with date_col2:
        start_to = st.date_input("Start date to", value=None, format="DD/MM/YYYY", key="view_start_to")

    rows = []
    for v in all_versions:
        status = "Active" if v.is_active else ("Cancelled" if v.end_date else "Superseded")
        rows.append({
            "Client": v.client.display_name,
            "Coach": v.coach.name,
            "Source": v.source,
            "Email": v.client_email or "",
            "Phone": v.client_phone or "",
            "Rate (£)": float(v.monthly_rate_gbp),
            "Commission": fmt_pct(float(v.commission_pct)),
            "Start Date": str(v.start_date),
            "End Date": str(v.end_date) if v.end_date else "",
            "Eff. From": str(v.effective_from),
            "Eff. To": str(v.effective_to) if v.effective_to else "open",
            "Status": status,
            "client_id": v.client_id,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No data.")
    else:
        if coach_filter:
            df = df[df["Coach"].isin(coach_filter)]
        if status_filter:
            df = df[df["Status"].isin(status_filter)]
        if source_filter:
            df = df[df["Source"].isin(source_filter)]
        if start_from:
            df = df[df["Start Date"] >= str(start_from)]
        if start_to:
            df = df[df["Start Date"] <= str(start_to)]

        display_df = df.drop(columns=["client_id"])
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.caption(f"{len(display_df)} rows shown.")
