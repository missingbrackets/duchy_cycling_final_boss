"""Audit Log page."""
from __future__ import annotations

import json
import streamlit as st
import pandas as pd

from core.config import APP_TITLE
from core.db import get_session, init_db
from repositories.audit_repo import get_all_logs

st.set_page_config(page_title=f"Audit Log — {APP_TITLE}", page_icon="📜", layout="wide")
init_db()

st.title("📜 Audit Log")

session = get_session()
try:
    logs = get_all_logs(session)
finally:
    session.close()

if not logs:
    st.info("No audit entries yet.")
    st.stop()

rows = [
    {
        "ID": log.audit_id,
        "Timestamp": str(log.timestamp)[:19],
        "User": log.user,
        "Action": log.action_type,
        "Entity": log.entity_type,
        "Entity ID": log.entity_id or "",
        "Notes": log.notes or "",
    }
    for log in logs
]
df = pd.DataFrame(rows)

# Filters
f1, f2, f3 = st.columns(3)
with f1:
    action_filter = st.multiselect("Filter by Action", df["Action"].unique().tolist())
with f2:
    entity_filter = st.multiselect("Filter by Entity", df["Entity"].unique().tolist())
with f3:
    user_filter = st.multiselect("Filter by User", df["User"].unique().tolist())

if action_filter:
    df = df[df["Action"].isin(action_filter)]
if entity_filter:
    df = df[df["Entity"].isin(entity_filter)]
if user_filter:
    df = df[df["User"].isin(user_filter)]

st.dataframe(df, use_container_width=True, hide_index=True)
st.caption(f"{len(df)} entries shown.")

# Row detail viewer
st.subheader("Row Detail")
selected_id = st.number_input("Enter Audit ID to inspect", min_value=1, step=1, value=1)

target = next((log for log in logs if log.audit_id == selected_id), None)
if target:
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Before**")
        if target.before_json:
            try:
                st.json(json.loads(target.before_json))
            except Exception:
                st.text(target.before_json)
        else:
            st.write("_(none)_")
    with col2:
        st.write("**After**")
        if target.after_json:
            try:
                st.json(json.loads(target.after_json))
            except Exception:
                st.text(target.after_json)
        else:
            st.write("_(none)_")
    if target.notes:
        st.write(f"**Notes:** {target.notes}")
else:
    st.info("No entry with that ID.")
