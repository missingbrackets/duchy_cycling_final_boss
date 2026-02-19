# Analytics Reference

## Definitions

### Active in Month
A client version is **active in month M** if:
- `effective_from` ≤ last day of M
- `effective_to` is NULL **or** `effective_to` ≥ first day of M
- `end_date` is NULL **or** `end_date` ≥ first day of M

> **Assumption:** No proration. If a client is active for even one day of the month, they count as a full month. This matches the typical practice of billing monthly upfront.

---

## Financial Metrics

| Metric | Formula |
|---|---|
| **Monthly Revenue (MRR)** | `monthly_rate_gbp` (per active version) |
| **Monthly Commission** | `monthly_rate_gbp × commission_pct` |
| **Coach Income** | `monthly_rate_gbp − commission` |

---

## Yearly Projections

Three methods are available, all accessible from the Dashboard:

| Method | Formula | Best for |
|---|---|---|
| **A — 12 × current MRR** | `12 × sum of current month MRR` | Snapshot of today |
| **B — 3-month trailing avg × 12** | `avg(MRR last 3 months) × 12` | Short-term trend |
| **C — 6-month trailing avg × 12** | `avg(MRR last 6 months) × 12` | Smoother long-term trend |

---

## Churn

| Metric | Definition |
|---|---|
| **New clients (month M)** | Clients whose `start_date` falls in M |
| **Dropped clients (month M)** | Clients whose `end_date` falls in M |
| **Churn rate** | `dropped / starting_active` — visible in dashboard table |

---

## Commissions Owed

Aggregated sum of `commission_gbp` grouped by coach and month. Useful for tracking how much to pay each coach's referral partner or business arrangement.
