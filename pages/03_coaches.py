"""Coaches page — add, edit, and view coaches."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import date

from core.config import APP_TITLE
from core.db import get_session, init_db
from repositories.coach_repo import create_coach, get_all_coaches, get_coach_by_name, update_coach
from services.audit import audit_create_coach, audit_update_coach
from ui.components import get_current_user

st.set_page_config(page_title=f"Coaches — {APP_TITLE}", page_icon="🏋️", layout="wide")
init_db()

st.title("🏋️ Coaches")

tab_add, tab_edit, tab_view = st.tabs(["➕ Add Coach", "✏️ Edit Coach", "📋 View Coaches"])

with tab_add:
    st.subheader("Add New Coach")
    with st.form("add_coach_form", clear_on_submit=True):
        name = st.text_input("Coach Name *")
        date_joined = st.date_input("Date Joined *", value=date.today(), format="DD/MM/YYYY")
        submitted = st.form_submit_button("Add Coach")

    if submitted:
        if not name.strip():
            st.error("Coach name is required.")
        else:
            session = get_session()
            try:
                existing = get_coach_by_name(session, name.strip())
                if existing:
                    st.warning(f"Coach '{name}' already exists.")
                else:
                    coach = create_coach(session, name.strip(), date_joined)
                    audit_create_coach(
                        session,
                        coach.coach_id,
                        coach.name,
                        str(coach.date_joined),
                        user=get_current_user(),
                    )
                    session.commit()
                    st.success(f"Coach **{name}** added.")
            except Exception as exc:
                session.rollback()
                st.error(f"Error: {exc}")
            finally:
                session.close()

with tab_edit:
    st.subheader("Edit Coach")
    session = get_session()
    try:
        coaches = get_all_coaches(session)
    finally:
        session.close()

    if not coaches:
        st.info("No coaches to edit.")
    else:
        coach_options = {c.name: c for c in coaches}
        selected_name = st.selectbox("Select coach", list(coach_options.keys()), key="edit_coach_select")
        current_coach = coach_options[selected_name]

        with st.form("edit_coach_form"):
            new_name = st.text_input("Coach Name *", value=current_coach.name)
            new_date_joined = st.date_input(
                "Date Joined *", value=current_coach.date_joined, format="DD/MM/YYYY"
            )
            edit_submitted = st.form_submit_button("Save Changes")

        if edit_submitted:
            if not new_name.strip():
                st.error("Coach name is required.")
            else:
                session = get_session()
                try:
                    before = {
                        "coach_id": current_coach.coach_id,
                        "name": current_coach.name,
                        "date_joined": str(current_coach.date_joined),
                    }
                    updated = update_coach(
                        session, current_coach.coach_id, new_name.strip(), new_date_joined
                    )
                    audit_update_coach(
                        session,
                        coach_id=current_coach.coach_id,
                        before=before,
                        after={
                            "coach_id": current_coach.coach_id,
                            "name": updated.name,
                            "date_joined": str(updated.date_joined),
                        },
                        user=get_current_user(),
                    )
                    session.commit()
                    st.success(f"Coach updated to **{updated.name}**.")
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    session.rollback()
                    st.error(f"Error: {exc}")
                finally:
                    session.close()

with tab_view:
    st.subheader("All Coaches")
    session = get_session()
    try:
        coaches = get_all_coaches(session)
        rows = []
        for c in coaches:
            active = sum(1 for v in c.client_versions if v.is_active)
            total_versions = len(c.client_versions)
            rows.append({
                "Coach": c.name,
                "Date Joined": str(c.date_joined),
                "Active Clients": active,
                "Total Versions": total_versions,
            })
    finally:
        session.close()

    if not rows:
        st.info("No coaches yet.")
    else:
        name_filter = st.text_input("Search by name", key="coach_search")
        df = pd.DataFrame(rows)
        if name_filter:
            df = df[df["Coach"].str.contains(name_filter, case=False)]
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} coaches shown.")
