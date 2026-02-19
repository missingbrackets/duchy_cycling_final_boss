"""Import / Export page."""
from __future__ import annotations

import io
import streamlit as st
import pandas as pd
from datetime import date

from core.config import APP_TITLE
from core.db import get_session, init_db
from services.importer import (
    auto_map_columns,
    parse_and_validate,
    execute_import,
    read_csv_bytes,
    COLUMN_ALIASES,
)
from services.audit import audit_import_csv
from repositories.client_repo import get_all_versions
from repositories.coach_repo import get_all_coaches
from ui.components import get_current_user, fmt_gbp, fmt_pct

st.set_page_config(page_title=f"Import/Export — {APP_TITLE}", page_icon="📥", layout="wide")
init_db()

st.title("📥 Import / Export")

tab_import, tab_export = st.tabs(["⬆️ Import CSV", "⬇️ Export CSV"])

# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------
with tab_import:
    st.subheader("Import Clients from CSV")

    st.markdown("""
Upload a flat CSV export (e.g., from Excel). Required columns (can be named differently — auto-mapped):
`coach`, `name`, `source`, `monthly_rate`, `commission_pct`, `start_date`

Optional: `email`, `phone`, `end_date`

**Commission** can be `20%`, `0.20`, or `20`.
**Dates** accept UK format (DD/MM/YYYY) and most other common formats.
""")

    uploaded = st.file_uploader("Choose CSV file", type=["csv"])
    auto_create = st.checkbox("Auto-create coaches if missing", value=True)

    if uploaded:
        raw_bytes = uploaded.read()
        try:
            df = read_csv_bytes(raw_bytes)
        except Exception as exc:
            st.error(f"Could not read CSV: {exc}")
            st.stop()

        st.write(f"**{len(df)} rows detected.** Columns: {', '.join(df.columns.tolist())}")

        # Column mapping
        auto_map = auto_map_columns(df.columns.tolist())
        st.subheader("Column Mapping")
        col_map: dict[str, str] = {}
        available_cols = ["(not mapped)"] + df.columns.tolist()

        cols_per_row = 3
        canonical_keys = list(COLUMN_ALIASES.keys())
        for i in range(0, len(canonical_keys), cols_per_row):
            row_keys = canonical_keys[i:i + cols_per_row]
            row_cols = st.columns(cols_per_row)
            for j, key in enumerate(row_keys):
                current_val = auto_map.get(key, "(not mapped)")
                idx = available_cols.index(current_val) if current_val in available_cols else 0
                chosen = row_cols[j].selectbox(
                    key, available_cols, index=idx, key=f"map_{key}"
                )
                if chosen != "(not mapped)":
                    col_map[key] = chosen

        st.subheader("Preview & Validation")
        parsed_rows = parse_and_validate(df, col_map)

        valid = [r for r in parsed_rows if r.is_valid]
        invalid = [r for r in parsed_rows if not r.is_valid]

        col_v, col_i = st.columns(2)
        col_v.metric("Valid rows", len(valid))
        col_i.metric("Invalid rows", len(invalid))

        if invalid:
            with st.expander(f"⚠️ {len(invalid)} validation errors"):
                err_rows = [
                    {"Row": r.row_number, "Name": r.name, "Error": "; ".join(r.errors)}
                    for r in invalid
                ]
                st.dataframe(pd.DataFrame(err_rows), use_container_width=True, hide_index=True)

        if valid:
            with st.expander("✅ Valid rows preview"):
                preview = [
                    {
                        "Name": r.name,
                        "Coach": r.coach,
                        "Source": r.source,
                        "Rate (£)": r.monthly_rate,
                        "Commission": f"{r.commission_pct * 100:.1f}%" if r.commission_pct else "",
                        "Start Date": str(r.start_date),
                        "End Date": str(r.end_date) if r.end_date else "",
                        "Email": r.email or "",
                        "Phone": r.phone or "",
                    }
                    for r in valid
                ]
                st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)

        if valid and st.button("✅ Commit Import", type="primary"):
            session = get_session()
            try:
                result = execute_import(session, parsed_rows, auto_create_coaches=auto_create)
                audit_import_csv(
                    session,
                    filename=uploaded.name,
                    clients_created=result.clients_created,
                    coaches_created=result.coaches_created,
                    versions_created=result.versions_created,
                    errors=len(result.errors),
                    user=get_current_user(),
                )
                session.commit()
                st.success(
                    f"Import complete: {result.clients_created} clients, "
                    f"{result.coaches_created} coaches, "
                    f"{result.versions_created} versions created. "
                    f"{result.skipped_rows} rows skipped."
                )
                if result.errors:
                    with st.expander("Import errors"):
                        st.dataframe(pd.DataFrame(result.errors), use_container_width=True, hide_index=True)
            except Exception as exc:
                session.rollback()
                st.error(f"Import failed: {exc}")
            finally:
                session.close()

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
with tab_export:
    st.subheader("Export Data to CSV")

    session = get_session()
    try:
        all_versions = get_all_versions(session)
    finally:
        session.close()

    rows = [
        {
            "client_id": v.client_id,
            "name": v.client.display_name,
            "coach": v.coach.name,
            "source": v.source,
            "email": v.client_email or "",
            "phone": v.client_phone or "",
            "monthly_rate_gbp": float(v.monthly_rate_gbp),
            "commission_pct": float(v.commission_pct),
            "start_date": str(v.start_date),
            "end_date": str(v.end_date) if v.end_date else "",
            "effective_from": str(v.effective_from),
            "effective_to": str(v.effective_to) if v.effective_to else "",
            "status": "Active" if v.is_active else ("Cancelled" if v.end_date else "Superseded"),
        }
        for v in all_versions
    ]

    if not rows:
        st.info("No data to export.")
    else:
        df_export = pd.DataFrame(rows)
        csv_bytes = df_export.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download all_clients.csv",
            data=csv_bytes,
            file_name=f"duchy_clients_{date.today()}.csv",
            mime="text/csv",
        )
        st.dataframe(df_export, use_container_width=True, hide_index=True)
