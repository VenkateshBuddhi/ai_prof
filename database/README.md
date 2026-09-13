# PostgreSQL Database ? Setup & Operations Guide

This folder holds the production-shaped database for the AI-native, multi-tenant
healthcare operations & patient-access platform:

| File | Purpose |
|---|---|
| `schema.sql` | Full PostgreSQL 16 DDL: enums, tables, indexes, trigger, slot materialisation function, Row-Level Security policies |
| `seed.sql` | Demo data mirroring the legacy in-memory registries in `src/voice/capabilities.py` |
| `compose.yml` | One-command local Postgres 16 via Docker (auto-runs schema + seed on first init) |
| `../schemas/*.json` | JSON Schema draft-07 catalog the DDL mirrors (single source of truth for shapes) |

Design decisions baked into the schema:

- **UUID PKs** (`gen_random_uuid()`, built into PostgreSQL 13+).
- **Multi-tenant by `tenant_id`** on every tenant-scoped table, enforced with **Row-Level Security (FORCE)**, so a misconfigured query can never cross tenant boundaries at the database layer.
- **Conversational booking is race-safe**: `time_slots.status + hold_token + hold_until + row_version` give you atomic optimistic locking for voice/chat agents.
- **AI tool calls are exactly-once**: partial unique index on `appointments.idempotency_key` prevents double bookings when the LLM retries `create_appointment`.
- **EHR sync is an outbox**: `ehr_entity_mappings` bridge platform UUIDs to remote ids; `ehr_sync_logs` is an append-mostly audit/retry queue.
- **Flexible clinical payloads stay JSONB** (`questions`, `answers`, `tool_calls`, `intent_snapshot`, `settings`) while the columns that drive queries are strongly typed enums/timestamps.

---

## 1. Quick start (Docker)

Prerequisite: Docker Engine 20.10+ (Docker Desktop on Windows/macOS).

```powershell
# from the repository root
docker compose -f database/compose.yml up -d

# wait until healthy, then verify
docker exec ai_prof_postgres pg_isready -U ai_prof -d ai_prof
```

The first `up` runs `schema.sql` then `seed.sql` (alphabetical order in
`/docker-entrypoint-initdb.d`). To reset from scratch:

```powershell
docker compose -f database/compose.yml down -v
```

Connect with any Postgres client:

```text
host: localhost
port: 5432
db:    ai_prof
user:  ai_prof
pass:  ai_prof
```

## 2. Native install (PostgreSQL 16)

```bash
createdb ai_prof
# as a superuser
psql -d ai_prof -v ON_ERROR_STOP=1 -f database/schema.sql
psql -d ai_prof -v ON_ERROR_STOP=1 -f database/seed.sql
```

> `schema.sql` must be applied by a **superuser or the table owner** ? RLS is
> `FORCE`-enabled so any later non-owner role is constrained by policies.
> Superusers always bypass RLS, which is also what lets `seed.sql` run.

---

## 3. Connecting from the FastAPI service

Add a driver with `uv` (asyncpg is the leanest for `async`/`await`):

```powershell
uv add asyncpg
# or, if you also want an ORM later: uv add sqlalchemy[asyncio] asyncpg
```

Put the DSN in `.env` (next to `GROQ_API_KEY` etc.):

```text
DATABASE_URL=postgresql://ai_prof:ai_prof@localhost:5432/ai_prof
```

Minimal async helper inspired by the current pipeline (create a pool at startup):

```python
# src/db.py (illustrative)
import os
import asyncpg

POOL = None

async def init_db():
    global POOL
    POOL = await asyncpg.create_pool(os.environ["DATABASE_URL"])

async def book_appointment(tenant_id: str, slot_id: str, patient_id: str, idem: str):
    """Atomic slot acquisition + appointment insert."""
    acquired = await POOL.fetchrow(
        """UPDATE time_slots
              SET status='Booked', hold_until=NULL, hold_token=NULL,
                  row_version = row_version + 1
            WHERE slot_id = $1 AND status='Open' AND row_version = 0
        RETURNING slot_id, tenant_id, hospital_id, doctor_id,
                  start_time, end_time, appointment_type""",
        slot_id)
    if not acquired:
        raise RuntimeError("slot_no_longer_available")
    await POOL.execute(
        """INSERT INTO appointments
               (tenant_id, patient_id, hospital_id, doctor_id, calendar_slot_id,
                appointment_type, start_time, end_time, status, idempotency_key)
           VALUES ($1, $2, $3, $4, $5, COALESCE($6, 'Standard'), $7, $8, 'Confirmed', $9)""",
        acquired["tenant_id"], patient_id, acquired["hospital_id"],
        acquired["doctor_id"], slot_id, acquired["appointment_type"],
        acquired["start_time"], acquired["end_time"], idem)
```

## 4. Multi-tenancy & Row-Level Security

The application connects as one shared role (never the table owner) and states
its tenant per session/transaction. RLS (FORCE) then filters every table.

Create the app role once (as superuser):

```sql
CREATE ROLE platform_app LOGIN;
GRANT USAGE ON SCHEMA public TO platform_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO platform_app;
GRANT SELECT, USAGE ON ALL SEQUENCES IN SCHEMA public TO platform_app;
```

Runtime pattern ? set the tenant before touching data:

```sql
-- whole session (pooled connection):
SET app.tenant_id = '11111111-1111-4111-8111-111111111111';

-- or transaction-scoped (PostgreSQL 16+), auto-cleared on COMMIT/ROLLBACK:
BEGIN;
SET LOCAL app.tenant_id = '11111111-1111-4111-8111-111111111111';
SELECT count(*) FROM patients;   -- only this tenant's rows
COMMIT;
```

Mechanics:

- `app_tenant_id()` reads the GUC text value and casts to `uuid` (and `SET LOCAL` keeps it out of pooled-session state).
- Every tenant-scoped policy is `tenant_id = app_tenant_id()`; child tables (`conversation_messages`, `escalations`, `ehr_connections`, `ehr_sync_logs`, `patient_consents`) resolve their tenant through the FK chain.
- `audit_logs` is INSERT-only for the app role (no UPDATE/DELETE policies).
- Superusers (migration runner, `postgres`) bypass RLS by design.

---

## 5. Booking a slot atomically (voice/chat race safety)

Every slot has `status` (Open/Booked/Held/Blocked/Cancelled/Expired), a
`row_version`, and optional `hold_token`/`hold_until`. Agents should: (1) hold a
slot while confirming with the patient, (2) convert the hold to a booking; a
background sweeper releases expired holds.

Take a 10-minute hold (returns the token; zero rows if already raced):

```sql
UPDATE time_slots
   SET status = 'Held',
       hold_until = now() + interval '10 minutes',
       hold_token = gen_random_uuid(),
       row_version = row_version + 1
 WHERE slot_id = $1 AND status = 'Open'
RETURNING slot_id, hold_token;
```

Book a held slot (compare-and-swap on the token):

```sql
UPDATE time_slots
   SET status = 'Booked', hold_token = NULL, hold_until = NULL,
       row_version = row_version + 1
 WHERE slot_id = $1 AND hold_token = $2
RETURNING slot_id;
```

Release the hold on patient abandonment or timeout:

```sql
UPDATE time_slots
   SET status = 'Open', hold_token = NULL, hold_until = NULL,
       row_version = row_version + 1
 WHERE slot_id = $1 AND status = 'Held';
```

## 6. Scheduled jobs (run outside request handlers)

Release expired holds + expire stale slots:

```sql
UPDATE time_slots
   SET status = 'Expired', hold_token = NULL, hold_until = NULL,
       row_version = row_version + 1
 WHERE status = 'Held' AND hold_until < now();
```

Materialise slots from templates (daily cron, or weekly for the next 28 days):

```sql
SELECT materialize_slots(current_date, current_date + 13);
```

Sweep EHR sync retries:

```sql
SELECT sync_log_id FROM ehr_sync_logs
 WHERE status IN ('Pending', 'Retrying', 'Failed') AND attempts < 5;
```

## 7. Exactly-once AI tool calls

`create_appointment` carries an `idempotency_key`. The partial unique index
`appointment_idempotency_uniq` makes retries safe in SQL ? re-insert with the
same key simply returns the existing appointment:

```sql
INSERT INTO appointments (tenant_id, patient_id, hospital_id, doctor_id,
                          calendar_slot_id, appointment_type, start_time, end_time,
                          status, idempotency_key)
SELECT ts.tenant_id, $2, ts.hospital_id, ts.doctor_id, ts.slot_id,
       COALESCE(ts.appointment_type, 'Standard'), ts.start_time, ts.end_time,
       'Confirmed', $4
  FROM time_slots ts WHERE ts.slot_id = $1
ON CONFLICT (idempotency_key) DO NOTHING
RETURNING appointment_id;
```

## 8. EHR integration flow

1. `ehr_systems` defines the vendor instance; `ehr_connections` scopes it per facility (secrets by reference, never inline).
2. `ehr_entity_mappings` bridges platform UUIDs <-> remote EHR ids (`patients`, `doctors`, `appointments`, `time_slots`).
3. Every outbound/inbound exchange is written to `ehr_sync_logs` (outbox pattern): `Pending -> Success` or `Failed/Retrying` with `attempts`.
4. `appointments.verification_status` tracks `UNVERIFIED -> EHR_VERIFIED` (or `VERIFICATION_FAILED`); `status` mirrors the remote lifecycle (`Synchronization Pending`, `Reconciliation Required`).
5. A reconciliation sweep lists `verification_status <> 'EHR_VERIFIED'` older than N minutes and re-verifies via the mapped remote id.

## 9. Schema catalog <-> table map

| JSON Schema (`schemas/`) | PostgreSQL table(s) |
|---|---|
| `conversational_state` | `conversational_states` (+ `conversation_sessions`, `conversation_messages`) |
| `appointment` | `appointments` (+ `time_slots`) |
| `questionnaire_definition` / `questionnaire_response` | `questionnaire_definitions` / `questionnaire_responses` |
| `check_availability_input` / `create_appointment_input` (agent payloads) | validated at the API/tool layer against `time_slots` / `appointments` |
| `tenant`, `hospital`, `admin_user` | `tenants`, `hospitals`, `admin_users` |
| `patient`, `doctor`, `doctor_hospital_affiliation` | `patients`, `doctors`, `doctor_hospital_affiliations` |
| `availability_template`, `time_slot` | `availability_templates`, `time_slots` |
| `conversation_session`, `conversation_message`, `escalation` | `conversation_sessions`, `conversation_messages`, `escalations` |
| `ehr_system`, `ehr_connection`, `ehr_entity_mapping`, `ehr_sync_log` | `ehr_systems`, `ehr_connections`, `ehr_entity_mappings`, `ehr_sync_logs` |
| `patient_consent`, `audit_log`, `notification` | `patient_consents`, `audit_logs`, `notifications` |

## 10. Migration strategy

Keep the JSON Schema catalog as the design source of truth and SQL files as the
implementation. Plain SQL migrations (alphabetical in `database/migrations/`)
with `psql -v ON_ERROR_STOP=1 -f` are sufficient at this stage; if the team
adopts an ORM, `uv add sqlalchemy[asyncio]` and `alembic init` inside this
folder, pointing `sqlalchemy.url` at `DATABASE_URL`, and keep `schema.sql` as
the canonical baseline (alembic: `include_object` to ignore it).
