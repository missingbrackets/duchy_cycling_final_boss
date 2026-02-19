"""Manage Data page — delete selected records or clear all data."""
from __future__ import annotations

import streamlit as st
import pandas as pd

from core.config import APP_TITLE
from core.db import get_session, init_db
from repositories.client_repo import (
    get_all_clients,
    get_all_versions,
    delete_clients_by_ids,
    delete_all_clients,
)
from repositories.coach_repo import (
    get_all_coaches,
    delete_coaches_by_ids,
    delete_all_coaches,
)
from services.audit import (
    audit_delete_clients,
    audit_delete_coaches,
    audit_clear_all,
)
from ui.components import get_current_user

st.set_page_config(page_title=f"Manage Data — {APP_TITLE}", page_icon="🗑️", layout="wide")
init_db()

st.title("🗑️ Manage Data")
st.warning(
    "⚠️ All deletions are **permanent and cannot be undone**. "
    "Actions are recorded in the Audit Log.",
    icon="⚠️",
)

tab_clients, tab_coaches, tab_clear = st.tabs(
    ["Delete Clients", "Delete Coaches", "☢️ Clear All Data"]
)

# ---------------------------------------------------------------------------
# Tab: Delete Clients
# ---------------------------------------------------------------------------
with tab_clients:
    st.subheader("Delete Selected Clients")
    st.caption("Deleting a client removes all their history versions too.")

    session = get_session()
    try:
        all_versions = get_all_versions(session)
    finally:
        session.close()

    if not all_versions:
        st.info("No clients in the database.")
    else:
        # Build a summary row per client (show active version details)
        seen: dict[int, dict] = {}
        for v in all_versions:
            cid = v.client_id
            if cid not in seen:
                seen[cid] = {
                    "client_id": cid,
                    "Name": v.client.display_name,
                    "Coach": v.coach.name,
                    "Status": "Active" if v.is_active else ("Cancelled" if v.end_date else "Superseded"),
                    "Versions": 0,
                }
            seen[cid]["Versions"] += 1
            # Prefer the open version for status display
            if v.is_open:
                seen[cid]["Coach"] = v.coach.name
                seen[cid]["Status"] = "Active" if v.is_active else "Cancelled"

        rows = list(seen.values())
        df = pd.DataFrame(rows)

        # Filters
        f1, f2 = st.columns(2)
        with f1:
            name_search = st.text_input("Search by name", key="del_client_search")
        with f2:
            status_filter = st.multiselect("Filter by status", ["Active", "Cancelled", "Superseded"], key="del_client_status")

        display_df = df.copy()
        if name_search:
            display_df = display_df[display_df["Name"].str.contains(name_search, case=False)]
        if status_filter:
            display_df = display_df[display_df["Status"].isin(status_filter)]

        st.dataframe(display_df.drop(columns=["client_id"]), use_container_width=True, hide_index=True)

        # Multi-select by name
        name_to_id = {r["Name"]: r["client_id"] for r in rows}
        filtered_names = display_df["Name"].tolist()

        selected_names = st.multiselect(
            "Select clients to delete", filtered_names, key="del_client_select"
        )

        if selected_names:
            st.error(f"You are about to permanently delete **{len(selected_names)} client(s)** and all their version history:")
            for n in selected_names:
                st.write(f"- {n}")

            confirmed = st.checkbox("I understand this cannot be undone", key="del_client_confirm")
            if st.button("🗑️ Delete Selected Clients", type="primary", disabled=not confirmed):
                ids_to_delete = [name_to_id[n] for n in selected_names]
                session = get_session()
                try:
                    count = delete_clients_by_ids(session, ids_to_delete)
                    audit_delete_clients(session, ids_to_delete, selected_names, user=get_current_user())
                    session.commit()
                    st.success(f"Deleted {count} client(s).")
                    st.rerun()
                except Exception as exc:
                    session.rollback()
                    st.error(f"Error: {exc}")
                finally:
                    session.close()

# ---------------------------------------------------------------------------
# Tab: Delete Coaches
# ---------------------------------------------------------------------------
with tab_coaches:
    st.subheader("Delete Selected Coaches")
    st.caption(
        "A coach can only be deleted if they have **no client versions** assigned. "
        "Delete or reassign their clients first."
    )

    session = get_session()
    try:
        coaches = get_all_coaches(session)
        rows_c = []
        for c in coaches:
            active = sum(1 for v in c.client_versions if v.is_active)
            total_v = len(c.client_versions)
            rows_c.append({
                "coach_id": c.coach_id,
                "Name": c.name,
                "Date Joined": str(c.date_joined),
                "Active Clients": active,
                "Total Versions": total_v,
                "Can Delete": "✅ Yes" if total_v == 0 else f"❌ No ({total_v} versions)",
            })
    finally:
        session.close()

    if not rows_c:
        st.info("No coaches in the database.")
    else:
        df_c = pd.DataFrame(rows_c)
        st.dataframe(df_c.drop(columns=["coach_id"]), use_container_width=True, hide_index=True)

        deletable = [r["Name"] for r in rows_c if r["Total Versions"] == 0]
        if not deletable:
            st.warning("All coaches have client versions attached and cannot be deleted. Remove their clients first.")
        else:
            coach_name_to_id = {r["Name"]: r["coach_id"] for r in rows_c}
            selected_coaches = st.multiselect(
                "Select coaches to delete (only coaches with no clients shown)",
                deletable,
                key="del_coach_select",
            )

            if selected_coaches:
                st.error(f"You are about to permanently delete **{len(selected_coaches)} coach(es)**:")
                for n in selected_coaches:
                    st.write(f"- {n}")

                confirmed_c = st.checkbox("I understand this cannot be undone", key="del_coach_confirm")
                if st.button("🗑️ Delete Selected Coaches", type="primary", disabled=not confirmed_c):
                    ids_to_del = [coach_name_to_id[n] for n in selected_coaches]
                    session = get_session()
                    try:
                        deleted, errors = delete_coaches_by_ids(session, ids_to_del)
                        if deleted:
                            audit_delete_coaches(
                                session, ids_to_del[:deleted], selected_coaches[:deleted],
                                user=get_current_user(),
                            )
                        session.commit()
                        st.success(f"Deleted {deleted} coach(es).")
                        if errors:
                            for e in errors:
                                st.warning(e)
                        st.rerun()
                    except Exception as exc:
                        session.rollback()
                        st.error(f"Error: {exc}")
                    finally:
                        session.close()

# ---------------------------------------------------------------------------
# Tab: Clear All Data
# ---------------------------------------------------------------------------
with tab_clear:
    st.subheader("☢️ Clear All Data")
    st.error(
        "This will **permanently delete ALL clients, ALL client versions, and ALL coaches** "
        "from the database. The audit log is preserved. This cannot be undone.",
    )

    session = get_session()
    try:
        from models.client import Client, ClientVersion
        from models.coach import Coach
        n_clients = session.query(Client).count()
        n_versions = session.query(ClientVersion).count()
        n_coaches = session.query(Coach).count()
    finally:
        session.close()

    col1, col2, col3 = st.columns(3)
    col1.metric("Clients", n_clients)
    col2.metric("Client Versions", n_versions)
    col3.metric("Coaches", n_coaches)

    st.divider()
    st.write("Type **DELETE** in the box below to enable the button:")
    confirm_text = st.text_input("Confirmation", placeholder="Type DELETE here", key="clear_all_text")

    col_clients, col_coaches = st.columns(2)
    with col_clients:
        clear_clients = st.checkbox("Clear all clients & versions", value=True, key="clear_clients_cb")
    with col_coaches:
        clear_coaches = st.checkbox("Clear all coaches", value=False, key="clear_coaches_cb")

    ready = confirm_text == "DELETE" and (clear_clients or clear_coaches)

    if st.button("☢️ Clear Selected Data", type="primary", disabled=not ready):
        session = get_session()
        try:
            clients_deleted = 0
            coaches_deleted = 0

            if clear_clients:
                clients_deleted = delete_all_clients(session)

            if clear_coaches:
                deleted_c, errors_c = delete_all_coaches(session)
                coaches_deleted = deleted_c
                for e in errors_c:
                    st.warning(e)

            audit_clear_all(session, clients_deleted, coaches_deleted, user=get_current_user())
            session.commit()
            st.success(
                f"Done. Deleted {clients_deleted} client(s) and {coaches_deleted} coach(es)."
            )
            st.rerun()
        except Exception as exc:
            session.rollback()
            st.error(f"Error: {exc}")
        finally:
            session.close()
