# Duchy Coaching Manager — User Guide

## Overview

Duchy Coaching Manager is a Streamlit web app for tracking coaching clients, revenue, commissions, and business analytics. It replaces a manual Excel workbook with a structured, audited database.

---

## Pages

### Dashboard
The dashboard shows:
- **Current MRR** (Monthly Recurring Revenue) — total monthly rates of all active clients.
- **Active Clients** — count of clients with no end date and an open version.
- **Yearly Projections** — three methods (see Analytics section).
- **Charts** — MRR by coach, income vs commission, active client count, churn.
- **Commissions Owed** — by coach and month.

Use the **From / To month** selectors to change the chart date range.

### Clients

#### Add Client
Fill in all required fields and click **Add Client**. This creates:
1. A `Client` record (stable identity).
2. A `ClientVersion` record (terms snapshot with effective dates).

#### Edit Client
Select a client from the dropdown. All fields are pre-filled from the current active version. Set an **Effective From** date — the system closes the old version and opens a new one.

> **Note:** Editing never overwrites history. You can always see prior rates in the Backend View.

#### Cancel Client
Select a client and choose an end date. This marks the active version as cancelled. The client will no longer appear in MRR calculations after the end date.

#### Backend View
A filterable table of all client versions. Filter by coach, status, source, and date ranges.

### Coaches
Add coaches with a name and date joined. The coaches table shows active client counts.

### Import / Export

#### Import
1. Upload a CSV file.
2. Review the auto-mapped column assignments and adjust if needed.
3. Check the validation preview — invalid rows are shown with error details.
4. Click **Commit Import** to save valid rows.

See [import_guide.md](import_guide.md) for CSV format details.

#### Export
Downloads a CSV of all client versions in normalised format.

### Audit Log
Every create, edit, cancel, and import action is logged with:
- Timestamp and user
- Before/after JSON snapshots
- Notes

Click an Audit ID to inspect the full before/after detail.

### Docs
This section. Documentation is rendered from Markdown files in the `/docs` folder.

---

## Running Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app creates `duchy_coaching.db` (SQLite) in the current directory on first run.

## Deployment (Streamlit Community Cloud)

1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo.
3. Set **Main file path** to `app.py`.
4. Optionally add secrets in the Streamlit Cloud dashboard:
   - `APP_PASSWORD` — password gate
   - `DATABASE_URL` — e.g. a PostgreSQL URL for persistent storage

> **Important:** Streamlit Community Cloud has ephemeral storage. For persistent data, configure `DATABASE_URL` to point to a hosted PostgreSQL database (e.g., Supabase, Neon, or Railway).
