# Supabase backend — setup, auth model & operations

This folder is the **Supabase deployment path** of the same database that
lives in `../database/`. The schema is identical (PostgreSQL 16 either way);
only the *multi-tenancy plumbing, auth linkage and migration packaging* are
Supabase-native.

| Path | Purpose |
|---|---|
| `migrations/20260912000000_init.sql` | Baseline DDL, generated from `../database/schema.sql` (enums, 22 tables, indexes, triggers, `materialize_slots()`, RLS policies). Tenant resolution reads the JWT (`request.jwt.claims`) instead of the `app.tenant_id` GUC. |
| `migrations/20260912010000_auth_link.sql` | Supabase Auth linkage: `user_id` FKs, signup trigger, `doctor_hospital_affiliations` RLS closure, identity helpers, PostgREST role grants (conditional — skipped on plain PG rigs). |
| `seed.sql` | Same demo data as `../database/seed.sql` (also usable via `supabase seed`). |
| `config.toml` | Supabase CLI project config (Postgres 16, migrations + seed wiring). |

Related docs: [`../database/README.md`](../database/README.md) (full operations
guide: booking SQL, cron jobs, EHR flow), [`../README.md`](../README.md),
[`../schemas/`](../schemas/) (JSON Schema catalog).


---

## 1. Prerequisites

- A Supabase project (hosted) **or** the Supabase CLI for local development.
- This repo's `supabase/` directory is CLI-ready: `config.toml` pins
  Postgres 16 and points the CLI at `migrations/` + `seed.sql`.

## 2. Local development (Supabase CLI)

```bash
supabase start       # launches local Postgres + Auth + PostgREST + Studio
supabase db reset    # replays migrations/ then seed.sql for a clean slate
supabase status      # connection strings, Studio URL, keys
```

The CLI applies migrations in filename order, so the baseline
(`20260912000000_init.sql`) always runs before the auth linkage
(`20260912010000_auth_link.sql`) — Supabase requires timestamp-prefixed
names, hence the `YYYYMMDDHHMMSS_` prefixes.

## 3. Linking to a hosted project

```bash
supabase login
supabase link --project-ref <your-project-ref>
supabase db push     # applies pending migrations to hosted
```

Review pending/applied state first with `supabase migration list`
(or `supabase db diff` to generate new migrations from dashboard changes).

## 4. Auth and multi-tenancy model

- Signups go through Supabase Auth (`auth.users`). The
  `on_auth_user_created` trigger provisions a `patients` (default) or
  `admin_users` row from `raw_app_meta_data`
  (`tenant_id` + `profile_type`, names from `raw_user_meta_data`).
  `handle_new_auth_user()` runs `SECURITY DEFINER` and fails closed on a
  missing/invalid tenant claim.
- Every RLS policy ultimately calls `app_tenant_id()`, which reads the
  PostgREST JWT claims (`request.jwt.claims -> app_metadata.tenant_id`).
  Browser clients authenticate as `authenticated`; the voice/agent backend
  uses the `service_role` key (bypasses RLS — server-side tenant scoping
  still applies in application code).
- Helpers for PostgREST/edge functions: `current_tenant_id()`,
  `my_patient_id()`, `my_admin_id()`.
- Stamp `app_metadata.tenant_id` at signup (Auth admin API / Auth hook),
  e.g. `{"tenant_id": "<uuid>", "profile_type": "patient"}`. Rotating a
  user's tenant = update `auth.users.raw_app_meta_data` (plus their
  `patients`/`admin_users.tenant_id` row) — never trust client-supplied ids.

---

## 5. Connecting the FastAPI voice service

Point the service at the Supabase Postgres connection string
(`supabase status` locally, or Project Settings -> Database on hosted) with
the **`service_role`** key for the agent backend:

```bash
DATABASE_URL=postgresql://postgres:<password>@<host>:5432/postgres
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
```

`uv add asyncpg` (or `psycopg[binary]`) for the driver. Browser/portal code
uses the `anon` key and is RLS-confined automatically.

## 6. Booking pattern (JWT session)

Same hold -> insert -> confirm flow as
[`../database/README.md`](../database/README.md) section 5, but split into
one statement per step (a known Postgres RLS + writable-CTE interaction makes
`INSERT .. SELECT` from a data-modifying CTE in the *same* statement silently
insert 0 rows for non-owner roles; sequential statements are unaffected):

```sql
-- 1. hold (authenticated session carries the tenant JWT)
WITH target AS (
  SELECT slot_id FROM time_slots
   WHERE tenant_id = :tenant AND status = 'Open'
   ORDER BY start_time LIMIT 1
), held AS (
  UPDATE time_slots ts SET status = 'Held', hold_token = gen_random_uuid(),
         hold_until = now() + interval '10 minutes',
         row_version = row_version + 1
    FROM target WHERE ts.slot_id = target.slot_id AND ts.status = 'Open'
  RETURNING ts.slot_id
)
SELECT slot_id FROM held;                    -- one slot id back, or none

-- 2. insert the appointment from the held row (separate statement)
INSERT INTO appointments (tenant_id, patient_id, hospital_id, doctor_id,
                          calendar_slot_id, appointment_type, start_time, end_time,
                          status, idempotency_key)
SELECT ts.tenant_id, :patient, ts.hospital_id, ts.doctor_id,
       ts.slot_id, COALESCE(ts.appointment_type, 'Standard'),
       ts.start_time, ts.end_time, 'Confirmed', :idem
  FROM time_slots ts WHERE ts.status = 'Held' ORDER BY ts.start_time LIMIT 1
RETURNING appointment_id;

-- 3. confirm the slot
UPDATE time_slots SET status = 'Booked', hold_token = NULL, hold_until = NULL,
       row_version = row_version + 1
 WHERE slot_id = :held_slot RETURNING slot_id, status;
```

Guards (validated): no-JWT sessions see **0 rows** (fail closed);
cross-tenant writes are rejected by policy; double-booking the same slot
fails on `appointment_slot_uidx`; retried agent calls collapse on
`appointment_idempotency_uidx`.

## 7. Scheduled jobs

`materialize_slots(date, date)` ships in the baseline migration and is
idempotent (re-running a window creates 0 rows). On hosted Supabase,
schedule it plus the hold-expiry sweeper and the EHR outbox retry via
**pg_cron** (Database -> Extensions -> `pg_cron`, then `cron.schedule(...)`);
locally, run them from any scheduler against the CLI Postgres.

## 8. Validation record

All Supabase migrations were validated clean-room against stock
PostgreSQL 16 with a test-only `auth` schema stub (the real stack provides
`auth.users` / `auth.jwt()` / `auth.uid()` natively). Eleven checks, all
passing: baseline applies clean (22 tables, 61 policies); auth-link applies
clean including the signup trigger; seed is idempotent (84 slots, then 0);
no-JWT sessions fail closed with 0 rows; tenant-A JWT sees own rows only
(2 hospitals, 3 doctors, 84 slots); cross-tenant INSERT rejected by RLS;
signup trigger provisions the patient profile; `my_patient_id()` and
`current_tenant_id()` resolve from the JWT sub (NULL when anonymous);
hold -> insert -> confirm books Confirmed/Booked; second booking on the same
slot rejected (`appointment_slot_uidx`); idempotency-key replay rejected
(`appointment_idempotency_uidx`).
