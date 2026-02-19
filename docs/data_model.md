# Data Model

## Design: SCD Type-2 Client History

Client terms (rate, coach, commission) change over time. Rather than overwriting the old record, a **new version** is created. This gives you a full, auditable history of every change.

---

## Entities

### Coach
| Column | Type | Notes |
|---|---|---|
| `coach_id` | int PK | Auto-increment |
| `name` | string | Unique |
| `date_joined` | date | |

### Client
The stable identity — never mutated after creation.

| Column | Type | Notes |
|---|---|---|
| `client_id` | int PK | Auto-increment |
| `display_name` | string | Client's name |
| `created_at` | datetime | Row creation time |

### ClientVersion
One snapshot of a client's terms, effective for a date range.

| Column | Type | Notes |
|---|---|---|
| `client_version_id` | int PK | Auto-increment |
| `client_id` | int FK | → Client |
| `coach_id` | int FK | → Coach |
| `source` | string | Acquisition channel |
| `client_email` | string? | Nullable |
| `client_phone` | string? | |
| `monthly_rate_gbp` | decimal | Rate charged to client |
| `commission_pct` | decimal | 0–1 (e.g. 0.20 = 20%) |
| `start_date` | date | Original coaching start |
| `end_date` | date? | NULL if still active |
| `effective_from` | date | Version becomes valid |
| `effective_to` | date? | NULL = current version |

### AuditLog
| Column | Type | Notes |
|---|---|---|
| `audit_id` | int PK | |
| `timestamp` | datetime | |
| `user` | string | |
| `action_type` | string | CREATE_CLIENT, UPDATE_CLIENT, etc. |
| `entity_type` | string | CLIENT, COACH, IMPORT |
| `entity_id` | string? | |
| `before_json` | text? | |
| `after_json` | text? | |
| `notes` | text? | |

---

## How "Current Active Client" Is Resolved

For a given date **D**, the active version satisfies:
```
effective_from <= D
AND (effective_to IS NULL OR effective_to >= D)
AND (end_date IS NULL OR end_date >= D)
```

For dashboard metrics (e.g. "active in month M"), we use:
```
effective_from <= last_day(M)
AND (effective_to IS NULL OR effective_to >= first_day(M))
AND (end_date IS NULL OR end_date >= first_day(M))
```

This means a client is counted as active in a month if they were active at **any point** during that month (no proration). This is a deliberate simplification; document it in your reports if needed.

---

## Version Lifecycle Example

1. **Create** client `James` on 2024-01-01:
   - `effective_from = 2024-01-01`, `effective_to = NULL`

2. **Edit** on 2024-06-01 (rate change effective 2024-07-01):
   - Old version: `effective_to` set to `2024-06-30`
   - New version: `effective_from = 2024-07-01`, `effective_to = NULL`

3. **Cancel** on 2024-10-31:
   - Active version: `end_date = 2024-10-31`, `effective_to = 2024-10-31`
