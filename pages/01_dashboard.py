"""Dashboard page — KPIs, charts, projections."""
import streamlit as st
import pandas as pd
import altair as alt
from datetime import date

from core.config import APP_TITLE, fmt_gbp
from core.db import get_session, init_db
from services.analytics import (
    load_version_snapshots,
    aggregate_monthly_summary,
    current_mrr,
    project_yearly_method_a,
    project_yearly_method_b,
    project_yearly_method_c,
    projection_series,
    churn_summary_by_coach,
    commissions_owed,
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
# Global date range
# ---------------------------------------------------------------------------
all_starts = [v.start_date for v in snapshots]
min_date = min(all_starts) if all_starts else date(today.year, 1, 1)

col_a, col_b = st.columns(2)
with col_a:
    from_month = st.date_input(
        "From month", value=date(min_date.year, min_date.month, 1), format="DD/MM/YYYY"
    )
with col_b:
    to_month = st.date_input(
        "To month", value=date(today.year, today.month, 1), format="DD/MM/YYYY"
    )

fm = (from_month.year, from_month.month)
tm = (to_month.year, to_month.month)

summaries = aggregate_monthly_summary(snapshots, fm, tm)

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
st.subheader("Live Snapshot (Current Month)")
mrr = current_mrr(snapshots, today)
comm_now = sum(
    v.monthly_rate_gbp * v.commission_pct
    for v in snapshots
    if v.effective_to is None and v.end_date is None
)
active_now = sum(1 for v in snapshots if v.effective_to is None and v.end_date is None)
proj_a = project_yearly_method_a(snapshots, today)
proj_b = project_yearly_method_b(snapshots, today)
proj_c = project_yearly_method_c(snapshots, today)
comm_ratio = (comm_now / mrr) if mrr else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Current MRR", fmt_gbp(mrr))
k2.metric("Current Commission", fmt_gbp(comm_now))
k3.metric("Active Clients", str(active_now))
k4.metric("Proj. Revenue (12×MRR)", fmt_gbp(proj_a))
k5.metric("Proj. Income (12×Comm)", fmt_gbp(proj_a * comm_ratio))

st.divider()

if not summaries:
    st.info("No data in selected date range.")
    st.stop()

# Build core DataFrames used across multiple sections
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

coaches_in_data = sorted(df["Coach"].unique().tolist())

# ============================================================================
# SECTION 1 — Active Client Count
# ============================================================================
st.subheader("👥 Active Client Count by Month")

breakdown_toggle = st.radio(
    "View",
    ["Month only", "By coach & month"],
    horizontal=True,
    key="client_breakdown",
)

if breakdown_toggle == "Month only":
    chart_clients = (
        alt.Chart(df_month)
        .mark_bar(color="#1f77b4")
        .encode(
            x=alt.X("Month:O", sort=None, title="Month"),
            y=alt.Y("Active Clients:Q"),
            tooltip=["Month", "Active Clients"],
        )
        .properties(height=300)
    )
    st.altair_chart(chart_clients, use_container_width=True)

else:
    chart_style = st.radio(
        "Chart type", ["Stacked bar", "Grouped bar", "Lines"],
        horizontal=True, key="client_chart_type"
    )
    if chart_style == "Lines":
        chart_clients = (
            alt.Chart(df)
            .mark_line(point=True)
            .encode(
                x=alt.X("Month:O", sort=None),
                y=alt.Y("Active Clients:Q"),
                color=alt.Color("Coach:N"),
                tooltip=["Month", "Coach", "Active Clients"],
            )
            .properties(height=300)
        )
        st.altair_chart(chart_clients, use_container_width=True)
    elif chart_style == "Stacked bar":
        chart_clients = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("Month:O", sort=None),
                y=alt.Y("Active Clients:Q", stack="zero"),
                color=alt.Color("Coach:N"),
                tooltip=["Month", "Coach", "Active Clients"],
            )
            .properties(height=300)
        )
        st.altair_chart(chart_clients, use_container_width=True)
    else:  # Grouped bar
        n_coaches = max(len(coaches_in_data), 1)
        chart_clients = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("Coach:N", title=None),
                y=alt.Y("Active Clients:Q"),
                color=alt.Color("Coach:N", legend=None),
                column=alt.Column(
                    "Month:O", sort=None, spacing=4,
                    header=alt.Header(labelAngle=-45, labelFontSize=10),
                ),
                tooltip=["Month", "Coach", "Active Clients"],
            )
            .properties(height=260, width=max(16, 360 // n_coaches))
        )
        st.altair_chart(chart_clients)

with st.expander("Client count table"):
    if breakdown_toggle == "Month only":
        st.dataframe(df_month[["Month", "Active Clients"]], use_container_width=True, hide_index=True)
    else:
        pivot = df.pivot_table(
            index="Month", columns="Coach", values="Active Clients",
            aggfunc="sum", fill_value=0,
        )
        st.dataframe(pivot, use_container_width=True)

st.divider()

# ============================================================================
# SECTION 2 — Projections Over Time
# ============================================================================
st.subheader("📈 Projected Yearly Income Over Time")

proj_col1, proj_col2 = st.columns(2)
with proj_col1:
    metric_toggle = st.radio(
        "Metric",
        ["Revenue (total rate)", "Income (commission)"],
        horizontal=True,
        key="proj_metric",
        help=(
            "Revenue = total monthly rate clients pay.  "
            "Income = commission the business earns (rate × commission %)."
        ),
    )
with proj_col2:
    methods_shown = st.multiselect(
        "Methods to show",
        ["Method A (12×current)", "Method B (3-mo avg)", "Method C (6-mo avg)"],
        default=["Method A (12×current)", "Method B (3-mo avg)", "Method C (6-mo avg)"],
        key="proj_methods",
    )

use_commission = metric_toggle == "Income (commission)"
curr_val   = comm_now if use_commission else mrr
proj_a_val = proj_a * comm_ratio if use_commission else proj_a
proj_b_val = proj_b * comm_ratio if use_commission else proj_b
proj_c_val = proj_c * comm_ratio if use_commission else proj_c

kp1, kp2, kp3 = st.columns(3)
kp1.metric("Method A — current", fmt_gbp(proj_a_val))
kp2.metric("Method B — current", fmt_gbp(proj_b_val))
kp3.metric("Method C — current", fmt_gbp(proj_c_val))

proj_data = projection_series(snapshots, fm, tm, use_commission=use_commission)
df_proj = pd.DataFrame(proj_data)

if methods_shown and not df_proj.empty:
    available_cols = [c for c in methods_shown if c in df_proj.columns]
    if available_cols:
        df_proj_long = df_proj.melt(
            id_vars=["Month"], value_vars=available_cols,
            var_name="Method", value_name="Projected Yearly (£)",
        )
        chart_proj = (
            alt.Chart(df_proj_long)
            .mark_line(point=True)
            .encode(
                x=alt.X("Month:O", sort=None),
                y=alt.Y("Projected Yearly (£):Q"),
                color=alt.Color("Method:N"),
                tooltip=["Month", "Method", "Projected Yearly (£)"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart_proj, use_container_width=True)

with st.expander("Projection data table"):
    st.dataframe(df_proj, use_container_width=True, hide_index=True)

st.divider()

# ============================================================================
# SECTION 3 — Revenue by Coach
# ============================================================================
st.subheader("💰 Monthly Revenue by Coach")
chart_mrr = (
    alt.Chart(df)
    .mark_bar()
    .encode(
        x=alt.X("Month:O", sort=None),
        y=alt.Y("MRR (£):Q"),
        color=alt.Color("Coach:N"),
        tooltip=["Month", "Coach", "MRR (£)", "Commission (£)", "Coach Income (£)"],
    )
    .properties(height=300)
)
st.altair_chart(chart_mrr, use_container_width=True)

st.divider()

# ============================================================================
# SECTION 4 — Churn Analysis
# ============================================================================
st.subheader("📉 Churn Analysis")

churn_view = st.radio(
    "View",
    ["Overall (all coaches)", "By coach comparison"],
    horizontal=True,
    key="churn_view",
)

if churn_view == "Overall (all coaches)":
    df_churn = df_month[["Month", "New Clients", "Dropped Clients"]].melt(
        id_vars=["Month"], var_name="Type", value_name="Count"
    )
    chart_churn = (
        alt.Chart(df_churn)
        .mark_bar()
        .encode(
            x=alt.X("Month:O", sort=None),
            y=alt.Y("Count:Q"),
            color=alt.Color(
                "Type:N",
                scale=alt.Scale(
                    domain=["New Clients", "Dropped Clients"],
                    range=["#2ca02c", "#d62728"],
                ),
            ),
            tooltip=["Month", "Type", "Count"],
        )
        .properties(height=280)
    )
    st.altair_chart(chart_churn, use_container_width=True)

    df_month_net = df_month.copy()
    df_month_net["Net Change"] = df_month_net["New Clients"] - df_month_net["Dropped Clients"]
    chart_net = (
        alt.Chart(df_month_net)
        .mark_line(point=True, color="#ff7f0e")
        .encode(
            x=alt.X("Month:O", sort=None),
            y=alt.Y("Net Change:Q"),
            tooltip=["Month", "Net Change", "New Clients", "Dropped Clients"],
        )
        .properties(height=160)
    )
    st.caption("Net change (new − dropped) per month:")
    st.altair_chart(chart_net, use_container_width=True)

else:  # By coach comparison
    coach_chart_type = st.radio(
        "Chart style",
        ["Monthly net change (lines per coach)", "New vs Dropped per coach (small multiples)"],
        horizontal=True,
        key="coach_churn_chart",
    )

    if coach_chart_type == "Monthly net change (lines per coach)":
        df_net = df.copy()
        df_net["Net Change"] = df_net["New Clients"] - df_net["Dropped Clients"]
        chart = (
            alt.Chart(df_net)
            .mark_line(point=True)
            .encode(
                x=alt.X("Month:O", sort=None),
                y=alt.Y("Net Change:Q", title="Net change (new − dropped)"),
                color=alt.Color("Coach:N"),
                tooltip=["Month", "Coach", "Net Change", "New Clients", "Dropped Clients"],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
        st.caption(
            "Each line shows a coach's monthly net client change. "
            "Above zero = growing; below zero = shrinking that month."
        )

    else:  # Small multiples — faceted per coach
        coach_filter = st.multiselect(
            "Filter coaches", coaches_in_data, default=coaches_in_data, key="churn_coach_filter"
        )
        df_fc = df[df["Coach"].isin(coach_filter)] if coach_filter else df
        df_churn_coach = df_fc.melt(
            id_vars=["Month", "Coach"],
            value_vars=["New Clients", "Dropped Clients"],
            var_name="Type", value_name="Count",
        )
        chart = (
            alt.Chart(df_churn_coach)
            .mark_bar()
            .encode(
                x=alt.X("Month:O", sort=None, title=None),
                y=alt.Y("Count:Q"),
                color=alt.Color(
                    "Type:N",
                    scale=alt.Scale(
                        domain=["New Clients", "Dropped Clients"],
                        range=["#2ca02c", "#d62728"],
                    ),
                ),
                facet=alt.Facet("Coach:N", columns=2, title=None),
                tooltip=["Month", "Coach", "Type", "Count"],
            )
            .properties(height=180, width=360)
        )
        st.altair_chart(chart)

    # ----------------------------------------------------------------
    # Period vs period comparison table
    # ----------------------------------------------------------------
    st.markdown("---")
    st.markdown("**Coach comparison — Period 1 vs Period 2**")
    st.caption("Period 1 uses the chart date range above. Set Period 2 below to compare.")

    cmp_col1, cmp_col2 = st.columns(2)
    with cmp_col1:
        p2_from = st.date_input(
            "Period 2 from", value=date(today.year - 1, 1, 1),
            format="DD/MM/YYYY", key="p2_from"
        )
    with cmp_col2:
        p2_to = st.date_input(
            "Period 2 to", value=date(today.year - 1, 12, 1),
            format="DD/MM/YYYY", key="p2_to"
        )

    p1_summary = churn_summary_by_coach(snapshots, fm, tm)
    p2_summary = churn_summary_by_coach(snapshots, (p2_from.year, p2_from.month), (p2_to.year, p2_to.month))

    if p1_summary:
        df_p1 = pd.DataFrame(p1_summary).rename(columns={
            "New": "P1 New", "Dropped": "P1 Dropped",
            "Net": "P1 Net", "Avg Monthly Net": "P1 Avg/Mo",
        })
        if p2_summary:
            df_p2 = pd.DataFrame(p2_summary).rename(columns={
                "New": "P2 New", "Dropped": "P2 Dropped",
                "Net": "P2 Net", "Avg Monthly Net": "P2 Avg/Mo",
            })
            df_cmp = df_p1.merge(
                df_p2[["Coach", "P2 New", "P2 Dropped", "P2 Net", "P2 Avg/Mo"]],
                on="Coach", how="outer",
            ).fillna(0)
            int_cols = ["P1 New", "P1 Dropped", "P1 Net", "P2 New", "P2 Dropped", "P2 Net"]
            df_cmp[int_cols] = df_cmp[int_cols].astype(int)
        else:
            df_cmp = df_p1
            st.caption("No data in Period 2 for comparison.")

        st.dataframe(
            df_cmp[[c for c in df_cmp.columns if c != "Months"]],
            use_container_width=True, hide_index=True,
        )

        # Visual bar comparison
        if p2_summary:
            df_bar = df_cmp.melt(
                id_vars=["Coach"],
                value_vars=["P1 Net", "P2 Net"],
                var_name="Period", value_name="Net Change",
            )
            chart_cmp = (
                alt.Chart(df_bar)
                .mark_bar()
                .encode(
                    x=alt.X("Period:N", title=None),
                    y=alt.Y("Net Change:Q"),
                    color=alt.Color("Period:N"),
                    column=alt.Column("Coach:N", spacing=8),
                    tooltip=["Coach", "Period", "Net Change"],
                )
                .properties(height=220, width=60)
            )
            st.caption("Net client change per coach — Period 1 vs Period 2:")
            st.altair_chart(chart_cmp)

st.divider()

# ============================================================================
# SECTION 5 — Commissions Owed
# ============================================================================
st.subheader("💷 Commissions Owed by Coach & Month")
owed = commissions_owed(snapshots, fm, tm)
if owed:
    df_owed = pd.DataFrame([
        {
            "Month": f"{o.year}-{o.month:02d}",
            "Coach": o.coach_name,
            "Commission Owed (£)": round(o.total_commission_gbp, 2),
        }
        for o in owed
    ])
    chart_owed = (
        alt.Chart(df_owed)
        .mark_bar()
        .encode(
            x=alt.X("Month:O", sort=None),
            y=alt.Y("Commission Owed (£):Q"),
            color=alt.Color("Coach:N"),
            tooltip=["Month", "Coach", "Commission Owed (£)"],
        )
        .properties(height=240)
    )
    st.altair_chart(chart_owed, use_container_width=True)
    st.dataframe(df_owed, use_container_width=True, hide_index=True)
else:
    st.info("No commissions data for selected range.")

# ============================================================================
# Full breakdown table
# ============================================================================
with st.expander("Full monthly breakdown table"):
    st.dataframe(df, use_container_width=True, hide_index=True)
