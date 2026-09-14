# context.md — orientation

A fast map of what this repository is, how it's organized, and where to start reading.
For *why* things are built this way, see [`decisions.md`](decisions.md). For *how a
request moves through the system*, see [`flow.md`](flow.md). For day-to-day commands and
module-level implementation notes, see [`CLAUDE.md`](CLAUDE.md) and [`README.md`](README.md).

## What this project is

A prototype of the PRD in `output_markdown/Project_Requirements/Project_Requirements.md`
(and the earlier `overview.md` blueprint): an AI-native, multi-tenant healthcare
patient-intake platform. A patient describes what they need in natural conversation
(voice, by phone or browser) and the AI finds a specialist, checks real availability,
books an EHR-verified appointment, and runs a pre-visit questionnaire — while hospital
staff, doctors, and platform admins watch and manage it all through a web dashboard.

The build happened in two, initially separate, halves that were later integrated:

1. **The voice/AI backend** (`src/`) — built incrementally, session by session, starting
   from a legacy Twilio+Postgres prototype that was fully replaced.
2. **The frontend dashboard** (`frontend/`) — a Next.js app generated separately (per its
   own commit history) implementing the PRD's §11 multi-role dashboards, originally
   against 100% mock data.

`src/api/` is the bridge: a FastAPI layer added specifically to connect the two.

## The three layers, one sentence each

- **Voice**: `src/voice/livekit_worker.py` runs on LiveKit's Agents framework. It owns
  the phone call / browser call — speech-to-text, voice-activity-detection, turn-taking,
  barge-in, text-to-speech — and hands each finished user utterance to the brain.
- **Brain**: `src/agent/` is a LangGraph agent. It takes text in, decides which of 12
  tools to call (search doctors, check slots, book, reschedule, cancel, run the
  questionnaire, register a new patient, escalate, hang up), and returns text out. It has
  no idea it's ever attached to a phone — `chat.py` drives the identical brain from a
  terminal, and the eval harness drives it from a script.
- **Engine**: `src/database/medplum_client.py` is the only thing that talks to Medplum
  (FHIR R4), which is where every doctor, appointment, patient, questionnaire, workflow
  job, and audit record actually lives. There is no other database.

Two supporting systems ride on top of the engine:
- `src/workflows/` — background jobs (appointment reminders, notifications), stored as
  FHIR `Task` resources, executed by a standalone poller.
- `src/observability.py` + `src/eval/` — per-call metrics/audit trail, and a scorecard
  that scores the agent's own behavior (intent accuracy, safety compliance, etc.).

`src/api/` reads from the same engine (plus the workflow/eval outputs) and reshapes it
into the JSON the dashboard expects, so the dashboard and the voice agent are always
looking at the same data.

## Where to start reading, by goal

| I want to... | Start here |
|---|---|
| Understand a live phone/browser call end to end | `flow.md` § "Voice call" |
| Understand a dashboard page loading | `flow.md` § "Dashboard read" |
| Add a new agent capability (tool) | `src/agent/schemas.py` → `tools.py` → `capabilities.py` → `executor.py`'s `_REGISTRY` (all four must agree — there's a test for it) |
| Add a new dashboard page's live data | `src/api/adapters.py` (add a mapper) → `src/api/routers/*.py` (add/extend an endpoint) → `frontend/src/lib/queries.ts` (add a hook) → the page component |
| Change what the agent is allowed to say/do | `src/agent/prompts.py` |
| Understand the FHIR data model assumptions | top of `src/database/medplum_client.py`, and `src/database/medplum_seed.py` |
| Run anything locally | `README.md` § "Quick start" |
| Understand a past architectural pivot (e.g. why Twilio→LiveKit, why Postgres→Medplum) | `decisions.md` |

## Directory map (one line each)

```
src/agent/         LangGraph brain: state, tools, schemas, prompts, graph, text-mode drivers
src/voice/         LiveKit worker (phone/browser calls) + SIP trunk provisioning script
src/database/      Medplum FHIR client (the only datastore) + seed script
src/workflows/     FHIR-Task-backed background jobs (reminders/notifications)
src/eval/          Scenario-based scoring harness for the agent (rule-based + LLM judge)
src/observability.py   Correlation IDs, per-call metrics, FHIR AuditEvent writer
src/logging_setup.py   One place all entry points call to configure logging
src/api/           FastAPI bridge: Medplum/workflows/eval -> dashboard JSON
frontend/          Next.js 16 dashboard (admin/hospital/doctor/patient), mostly pre-built
tests/             pytest, fully offline (a FakeMedplum fixture stands in for the real one)
schemas/           JSON Schema catalog from the original relational design (reference only)
output_markdown/   The PRD (Project_Requirements.md) that this all implements
overview.md        An earlier, shorter product blueprint (superseded by the PRD, kept for context)
twilio.md          Runbook for receiving real calls on a free Twilio trial account
```

## Things that look like they should exist but don't (and why)

- **No SQL database.** An earlier iteration used PostgreSQL/Supabase; it was fully
  removed once Medplum became the system of record. If you see a reference to
  `DATABASE_URL` or `SupabaseClient` anywhere, it's stale — flag it.
- **No `app.py` / Twilio media-stream server.** The original voice pipeline spoke
  Twilio's raw WebSocket media protocol directly; it was replaced end-to-end by the
  LiveKit worker. Twilio's only remaining job is SIP trunking.
- **No real authentication yet.** `src/api/deps.py` reads role/scope from plain request
  headers (`X-Role`, etc.), defaulting to `platform_admin`. This was a deliberate
  sequencing choice (see `decisions.md`) so the dashboard could go live against real data
  before auth was built. Do not treat header-based scope as a security boundary.
- **No cross-call analytics store.** Trend charts (appointments-over-time, latency
  history) still use mock data — KPI *tiles* are computed on the fly from Medplum, but
  time-series aggregation was deferred (see `decisions.md`'s Supabase-vs-Medplum note).

## Conventions worth knowing before you edit code

- Every CLI entry point (`chat.py`, `smoke_test.py`, `medplum_seed.py`, the worker, the
  workflow runner, the eval runner, `src/api/main.py`) **self-parses `.env`** with the
  same small inline loader — `python-dotenv` is a listed dependency but unused.
- The tool contract (`src/agent/schemas.py` Pydantic models, `tools.py` LLM-facing
  descriptions, `capabilities.py` implementations, `executor.py`'s `_REGISTRY`) is
  intentionally four separate lists that must all agree. `tests/test_tool_parity.py`
  enforces this — if you add a tool, update all four or the test fails.
- `AgentSession` is defined twice on purpose: once in `src/agent/state.py` (our Pydantic
  conversation state) and once by LiveKit's SDK. The worker imports ours under an alias
  (`AgentStateSession`) to avoid confusion.
- All FHIR writes are `read-modify-PUT` or conditional-`POST`, never JSON-Patch for
  multi-field updates (Medplum rejected multi-op patches in testing — see `decisions.md`).
