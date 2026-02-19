# Duchy Coaching Manager

A production-ready Streamlit web app for coaching businesses to track clients, coaches, revenue, commissions, and analytics — replacing a manual Excel workbook.

## Features

- **Client management** with full SCD Type-2 history (no data ever overwritten)
- **Coach management** with per-coach analytics
- **Dashboard** with MRR, projections (3 methods), churn, and commissions charts
- **CSV import** with auto column-mapping, validation preview, and de-dup
- **CSV export** of normalised data
- **Audit log** for every create/edit/cancel/import action with before/after JSON
- **In-app documentation** rendered from Markdown
- **Optional password gate** via Streamlit secrets
- **Configurable database** (SQLite by default, PostgreSQL via env var)

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd duchy_cycling_final_boss
pip install -r requirements.txt

# 2. Run
streamlit run app.py
```

The app creates `duchy_coaching.db` (SQLite) in the working directory on first run.

## Project Structure

```
/app.py                     # Entry point + password gate
/pages/
  01_dashboard.py           # KPIs, charts, projections
  02_clients.py             # Add / edit / cancel / view clients
  03_coaches.py             # Add / view coaches
  04_import_export.py       # CSV import & export
  05_audit_log.py           # Filterable audit log
  06_docs.py                # Renders /docs/*.md
/core/
  config.py                 # Constants, enums, formatters
  db.py                     # SQLAlchemy engine, session, init_db
/models/
  coach.py                  # Coach ORM model
  client.py                 # Client + ClientVersion ORM models
  audit.py                  # AuditLog ORM model
/repositories/
  coach_repo.py             # Coach DB operations
  client_repo.py            # Client / ClientVersion DB operations
  audit_repo.py             # AuditLog DB operations
/services/
  analytics.py              # MRR, projections, churn, commissions
  importer.py               # CSV parsing, validation, import
  audit.py                  # Structured audit logging helpers
/ui/
  components.py             # Shared UI helpers
/docs/
  user_guide.md
  data_model.md
  import_guide.md
  analytics.md
/sample_data/
  sample_import.csv         # 10-row test import file
/tests/
  test_analytics.py         # Unit tests for analytics
  test_importer.py          # Unit tests for CSV parsing
/requirements.txt
/.streamlit/
  config.toml
  secrets.toml.example      # Copy → secrets.toml to configure
```

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Configuration

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set:

| Key | Description |
|---|---|
| `APP_PASSWORD` | Optional password gate |
| `DATABASE_URL` | SQLAlchemy URL (default: local SQLite) |

## Deployment (Streamlit Community Cloud)

1. Push this repo to GitHub.
2. Connect at [share.streamlit.io](https://share.streamlit.io).
3. Set main file to `app.py`.
4. Add secrets in the Cloud dashboard for `APP_PASSWORD` and `DATABASE_URL`.

> For persistent storage on Streamlit Cloud, set `DATABASE_URL` to a hosted PostgreSQL connection string (e.g., Supabase, Neon, Railway).

## Architecture

| Layer | Tech | Purpose |
|---|---|---|
| UI | Streamlit multipage | All user interaction |
| Models | SQLAlchemy ORM | Type-safe schema definitions |
| Repositories | SQLAlchemy sessions | DB read/write operations |
| Services | Pure Python | Analytics, import logic, audit |
| Storage | SQLite / PostgreSQL | Via configurable DATABASE_URL |

The analytics service uses plain Python dataclasses (`VersionSnapshot`) so it is fully unit-testable without a live database.
