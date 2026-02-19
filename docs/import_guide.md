# CSV Import Guide

## Supported Column Names

The importer auto-detects columns by common name variants. You can also remap columns manually in the UI.

| Field | Required | Accepted column names |
|---|---|---|
| Coach | ✅ | `coach`, `coach_name`, `trainer` |
| Client Name | ✅ | `name`, `client_name`, `client`, `display_name` |
| Source | ✅ | `source`, `acquisition`, `lead_source`, `channel` |
| Monthly Rate | ✅ | `monthly_rate`, `rate`, `monthly_rate_gbp`, `price`, `fee` |
| Commission | ✅ | `commission_pct`, `commission`, `commission_%` |
| Start Date | ✅ | `start_date`, `start`, `joined`, `date_joined` |
| Email | ❌ | `email`, `client_email`, `e-mail` |
| Phone | ❌ | `phone`, `client_phone`, `telephone`, `mobile` |
| End Date | ❌ | `end_date`, `end`, `cancelled`, `cancel_date` |

## Commission Format

Any of these are accepted:
- `20%`
- `0.20`
- `20`

All are normalised to a 0–1 decimal internally.

## Date Formats

Dates are parsed with UK-first heuristics (day before month). Examples:
- `01/01/2024` → 1 Jan 2024 ✅
- `2024-01-01` → 1 Jan 2024 ✅
- `1 January 2024` → 1 Jan 2024 ✅

## De-duplication Strategy

When importing, the system checks for existing clients to avoid duplicates:
1. If `email` is present → match on email first.
2. If no email match → match on `(name + phone)`.
3. If still no match → match on `name` alone.
4. If no match found → create a new client.

## Sample CSV

See `/sample_data/sample_import.csv` for a working example.

## Import Behaviour

- **Coaches** are auto-created if they don't exist (toggle in UI).
- Each CSV row creates one `ClientVersion`.
- Invalid rows (missing required fields, unparseable values) are skipped and reported.
- A single `IMPORT_CSV` audit log entry is created with row counts and the filename.

## Tips

- Export your Excel sheet to CSV (File → Save As → CSV UTF-8).
- Remove merged cells and header rows before exporting.
- If column auto-mapping is wrong, use the dropdown selectors to manually remap.
