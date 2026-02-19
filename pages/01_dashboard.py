"""Dashboard page — KPIs, charts, projections."""
import streamlit as st
import pandas as pd
import altair as alt
from datetime import date

from core.config import APP_TITLE, fmt_gbp, fmt_pct
from core.db import get_session, init_db
from services.analytics import (
    load_version_snapshots,
    aggregate_monthly_summary,
    current_mrr,
    project_yearly_method_a,
    project_yearly_method_b,
    project_yearly_method_c,
    commissions_owed,
    _month_bounds,
)

st.set_page_config(page_title=f"Dashboard — {APP_TITLE}", page_icon="📊", layout="wide")
init_db()

st.title("📊 Dashboard")

session = get_session()
try:
    snapshots = load_version_snapshots(session)
finally:
    session.close()

if not snapshots:
    st.info("No data yet. Add clients or import a CSV to see metrics.")
    st.stop()

today = date.today()

# ---------------------------------------------------------------------------
# Date range selector for charts
# ---------------------------------------------------------------------------
all_starts = [v.start_date for v in snapshots]
min_date = min(all_starts) if all_starts else date(today.year, 1, 1)

col_a, col_b = st.columns(2)
with col_a:
    from_month = st.date_input(
        "From month",
        value=date(min_date.year, min_date.month, 1),
        format="DD/MM/YYYY",
    )
with col_b:
    to_month = st.date_input(
        "To month",
        value=date(today.year, today.month, 1),
        format="DD/MM/YYYY",
    )

fm = (from_month.year, from_month.month)
tm = (to_month.year, to_month.month)

summaries = aggregate_monthly_summary(snapshots, fm, tm)

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
st.subheader("Live Snapshot (Current Month)")
mrr = current_mrr(snapshots, today)
active_now = sum(
    1 for v in snapshots
    if v.effective_to is None and v.end_date is None
)
proj_a = project_yearly_method_a(snapshots, today)
proj_b = project_yearly_method_b(snapshots, today)
proj_c = project_yearly_method_c(snapshots, today)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Current MRR", fmt_gbp(mrr))
k2.metric("Active Clients", str(active_now))
k3.metric("Proj. Yearly (12×MRR)", fmt_gbp(proj_a))
k4.metric("Proj. Yearly (6-month avg)", fmt_gbp(proj_c))

st.divider()

# ---------------------------------------------------------------------------
# Projection method selector
# ---------------------------------------------------------------------------
st.subheader("Yearly Income Projections")
proj_method = st.radio(
    "Projection method",
    ["Method A: 12 × current MRR", "Method B: 3-month trailing avg × 12", "Method C: 6-month trailing avg × 12"],
    horizontal=True,
)
if "Method A" in proj_method:
    proj_val = proj_a
elif "Method B" in proj_method:
    proj_val = proj_b
else:
    proj_val = proj_c

st.metric("Projected Yearly Income", fmt_gbp(proj_val))

col_proj = st.columns(3)
col_proj[0].metric("Method A", fmt_gbp(proj_a))
col_proj[1].metric("Method B", fmt_gbp(proj_b))
col_proj[2].metric("Method C", fmt_gbp(proj_c))

st.divider()

# ---------------------------------------------------------------------------
# Convert summaries to DataFrame
# ---------------------------------------------------------------------------
if not summaries:
    st.info("No data in selected date range.")
    st.stop()

rows = [
    {
        "Month": f"{s.year}-{s.month:02d}",
        "Coach": s.coach_name,
        "Active Clients": s.active_clients,
        "MRR (£)": round(s.total_mrr_gbp, 2),
        "Commission (£)": round(s.total_commission_gbp, 2),
        "Coach Income (£)": round(s.total_coach_income_gbp, 2),
        "New Clients": s.new_clients,
        "Dropped Clients": s.dropped_clients,
    }
    for s in summaries
]
df = pd.DataFrame(rows)

# Totals by month (all coaches)
df_month = df.groupby("Month", as_index=False).agg(
    {
        "Active Clients": "sum",
        "MRR (£)": "sum",
        "Commission (£)": "sum",
        "Coach Income (£)": "sum",
        "New Clients": "sum",
        "Dropped Clients": "sum",
    }
)

# ---------------------------------------------------------------------------
# Chart: MRR by month (stacked by coach)
# ---------------------------------------------------------------------------
st.subheader("Monthly Revenue by Coach")
chart_mrr = (
    alt.Chart(df)
    .mark_bar()
    .encode(
        x=alt.X("Month:O", sort=None, title="Month"),
        y=alt.Y("MRR (£):Q", title="MRR (£)"),
        color=alt.Color("Coach:N", legend=alt.Legend(title="Coach")),
        tooltip=["Month", "Coach", "MRR (£)", "Active Clients"],
    )
    .properties(height=350)
)
st.altair_chart(chart_mrr, use_container_width=True)

# ---------------------------------------------------------------------------
# Chart: Coach Income vs Commission
# ---------------------------------------------------------------------------
st.subheader("Coach Income vs Commission by Month")
df_income_long = df_month.melt(
    id_vars=["Month"],
    value_vars=["Coach Income (£)", "Commission (£)"],
    var_name="Type",
    value_name="Amount (£)",
)
chart_income = (
    alt.Chart(df_income_long)
    .mark_bar()
    .encode(
        x=alt.X("Month:O", sort=None),
        y=alt.Y("Amount (£):Q"),
        color=alt.Color("Type:N"),
        tooltip=["Month", "Type", "Amount (£)"],
    )
    .properties(height=300)
)
st.altair_chart(chart_income, use_container_width=True)

# ---------------------------------------------------------------------------
# Chart: Active Clients by Month
# ---------------------------------------------------------------------------
st.subheader("Active Client Count by Month")
chart_clients = (
    alt.Chart(df)
    .mark_line(point=True)
    .encode(
        x=alt.X("Month:O", sort=None),
        y=alt.Y("Active Clients:Q"),
        color=alt.Color("Coach:N"),
        tooltip=["Month", "Coach", "Active Clients"],
    )
    .properties(height=280)
)
st.altair_chart(chart_clients, use_container_width=True)

# ---------------------------------------------------------------------------
# Chart: Churn (new vs dropped)
# ---------------------------------------------------------------------------
st.subheader("Client Churn by Month (All Coaches)")
df_churn = df_month[["Month", "New Clients", "Dropped Clients"]].melt(
    id_vars=["Month"], var_name="Type", value_name="Count"
)
chart_churn = (
    alt.Chart(df_churn)
    .mark_bar()
    .encode(
        x=alt.X("Month:O", sort=None),
        y=alt.Y("Count:Q"),
        color=alt.Color("Type:N", scale=alt.Scale(scheme="set2")),
        tooltip=["Month", "Type", "Count"],
    )
    .properties(height=260)
)
st.altair_chart(chart_churn, use_container_width=True)

# ---------------------------------------------------------------------------
# Commissions owed table
# ---------------------------------------------------------------------------
st.subheader("Commissions Owed by Coach & Month")
owed = commissions_owed(snapshots, fm, tm)
if owed:
    df_owed = pd.DataFrame([
        {"Month": f"{o.year}-{o.month:02d}", "Coach": o.coach_name, "Commission Owed (£)": round(o.total_commission_gbp, 2)}
        for o in owed
    ])
    st.dataframe(df_owed, use_container_width=True, hide_index=True)
else:
    st.info("No commissions data for selected range.")

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------
with st.expander("Full monthly breakdown table"):
    st.dataframe(df, use_container_width=True, hide_index=True)
