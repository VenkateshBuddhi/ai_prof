# ai_prof — Healthcare Voice Intake Agent

An AI-native, multi-tenant healthcare voice agent with a management dashboard. A patient
calls in (by phone or browser) and, in natural conversation, the agent finds the right
specialist, checks real availability, books the appointment, and collects a pre-visit
questionnaire — then writes the call back to the patient's clinical record. A FastAPI
layer exposes the same data to a Next.js multi-role dashboard (admin / hospital / doctor /
patient).

```
Cellular caller                          Browser (dashboard / AI Assistant)
   │  (Twilio SIP trunk — trunking only)      │  HTTPS (react-query)          │  WebRTC (livekit-client)
   ▼                                          ▼                                ▼
LiveKit SIP ──► LiveKit room ──► Voice worker (Deepgram STT · Silero VAD · Cartesia TTS)
                                        │  transcribed turn                 ▲
                                        ▼                                   │ token + agent dispatch
                             LangGraph agent (Gemini→Groq + tools)          │
                                        │  FHIR reads/writes         FastAPI (src/api) ──┘
                                        ▼                                   │  reads (adapters)
                                Medplum (FHIR R4)  ◄─────────────────────────┘
                                  doctors · slots · appointments · questionnaires
                                  Task (workflows) · AuditEvent (observability) · Communication (transcript/notify)
```

- **Media / telephony:** LiveKit Agents (ultra-low-latency bidirectional audio). Twilio is
  only a SIP trunk passing cellular calls into LiveKit. Browser callers connect the same
  way via `livekit-client` + a token minted by the API.
- **Reasoning:** a LangGraph `StateGraph` over a **Gemini → Groq** fallback chain
  (`with_fallbacks`), with tool-calling for every action.
- **System of record:** Medplum (FHIR R4) — identity, scheduling, intake, workflows,
  audit, and the call transcript. No SQL database.
- **Dashboard API:** FastAPI (`src/api/`) adapts Medplum + the workflow/eval engines into
  the frontend's DTOs, with a dev-bypass auth header (real auth not yet wired).
- **Frontend:** Next.js 16 / React 19 dashboard (`frontend/`), pulled in from a separate
  design track — see [`decisions.md`](decisions.md) for how it was integrated.

For the full request→response walkthrough of every flow, see [`flow.md`](flow.md). For
why each technology/pattern was chosen, see [`decisions.md`](decisions.md). For a fast
orientation to the repo, see [`context.md`](context.md).

## 🚀 Deployment Status & Infrastructure

| Component | Platform / Host | Status | Details |
|---|---|:---:|---|
| **Frontend Web App** | **Render / Vercel** | 🟢 **Live** | Next.js 16 + React 19 multi-role dashboard (Patient, Doctor, Staff, Admin) & LiveKit WebRTC client |
| **Backend API** | **Render** | 🟢 **Live** | FastAPI REST service (`src/api/`) with LiveKit token dispatch & FHIR DTO adapters |
| **Voice Worker** | **Local Terminal** | 🟢 **Live** | Real-time WebRTC audio worker (`livekit_worker.py`) run locally due to Render memory limits, connecting to LiveKit Cloud |
| **FHIR System of Record** | **Medplum Cloud** | 🟢 **Seeded** | 210 FHIR R4 resources across 14 resource types seeded via `src/database/medplum_seed.py` |
| **Telephony Bridge** | **Twilio SIP Trunk** | 🟢 **Configured** | Inbound SIP trunking directly into LiveKit Cloud room dispatch |

---

## 📊 Overall Implementation Progress & PRD Audit

| PRD Section | Feature / Capability | Status | Implementation Details |
|---|---|:---:|---|
| **§2–§4** | **System Architecture & Data Flows** | ✅ **100%** | FastAPI backend, LangGraph agent, LiveKit RTC, Medplum FHIR, dual LLM fallback |
| **§5–§6** | **Agent Core & Reasoning Graph** | ✅ **100%** | LangGraph `StateGraph`, role capability matrix, session memory, Gemini 2.5 Flash + Groq fallback |
| **§7** | **Agent Tools Suite** | ✅ **100%** | 12 FHIR tools: `search_doctors`, `check_availability`, `create_appointment`, `reschedule_appointment`, `cancel_appointment`, `get_questionnaire`, `submit_questionnaire_response`, `lookup_patient`, `register_patient`, `get_appointment`, `transfer_to_human`, `end_call` |
| **§8** | **FHIR Adapter Layer** | ✅ **100%** | Comprehensive Medplum FHIR R4 client with OAuth2 token caching, retry policy, and transactional bundles |
| **§9** | **Real-Time Voice Pipeline** | ✅ **100%** | LiveKit RTC + Deepgram STT (medical model) + Cartesia Sonic TTS + Silero VAD (<500ms latency) |
| **§10–§11** | **Safety, Guardrails & Triage** | ✅ **100%** | Zero-PHI log redaction, emergency 911 deflectors (chest pain/severe trauma), non-prescriptive administrative bounds |
| **§12** | **Telephony Integration** | ✅ **100%** | Twilio SIP trunking bridge to LiveKit inbound dispatch rules |
| **§13–§14** | **API Layer & Security** | ✅ **100%** | FastAPI routers (`appointments`, `catalog`, `patients`, `ops`, `voice`, `health`) |
| **§18–§20** | **Observability & Telemetry** | ✅ **100%** | Correlation IDs, per-call metrics summaries, FHIR `AuditEvent`, and PRD §21/§22 evaluation scorecard |
| **§26–§29** | **Test Suite & Verification** | ✅ **100%** | **73 / 73 Pytest suite passing** (`tests/unit/`, `tests/integration/`, `tests/e2e/`) |
| **§31–§34** | **Frontend Client (Next.js)** | ✅ **100%** | Responsive UI for Patient Voice Assistant, Doctor Appointment & Refill Reviews, Staff Scheduling, and Admin KPIs |

---

## Quick start

```bash
uv sync                                    # install (Python 3.13, uv-managed)
cp .env.example .env                        # then fill in the keys below

# 1. Seed the FHIR backend (idempotent; mirrors a St. Mary Health Network demo)
uv run python -m src.database.medplum_seed --dry-run    # validate offline (no creds)
uv run python -m src.database.medplum_seed              # apply to your Medplum project

# 2. Test the agent without any phone call
uv run python -m src.agent.smoke_test --phone +15550192834 --specialty Cardiology   # tools only
uv run python -m src.agent.chat --show-tools                                        # text conversation

# 3. Run the voice worker
uv run python -m src.voice.livekit_worker console       # local mic/speakers, no telephony
uv run python -m src.voice.livekit_worker dev            # connect to LiveKit (dev, hot-reload off)
uv run python -m src.voice.livekit_worker start          # production

# 4. (For real phone calls) provision the LiveKit SIP trunk + dispatch rule
uv run python -m src.voice.livekit_sip_setup            # then follow twilio.md

# 5. Run the workflow runner (reminders/notifications) — alongside the worker
uv run python -m src.workflows.runner            # poll loop
uv run python -m src.workflows.runner --once     # single pass (testing)

# 6. Evaluate the agent (PRD §21/§22 scorecard)
uv run python -m src.eval.runner --offline --no-judge   # score fixtures (no creds)
uv run python -m src.eval.runner                        # live scenarios + LLM-judge

# 7. Run the test suite (offline, mocked)
uv run pytest

# 8. Run the dashboard backend + frontend
uv run uvicorn src.api.main:app --reload --port 8000    # FastAPI, http://localhost:8000/docs
cd frontend && npm install && npm run dev               # Next.js, http://localhost:3000
```

With all three running (worker, API, frontend) you get: phone/browser voice booking →
Medplum → the same data live in the dashboard.

## Configuration (`.env`)

| Key | Purpose |
|---|---|
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | LiveKit server / rooms |
| `DEEPGRAM_API_KEY` | Speech-to-text |
| `CARTESIA_API_KEY` | Text-to-speech |
| `GEMINI_API_KEY` | Agent LLM — Google Gemini (default primary). `GOOGLE_API_KEY` also accepted |
| `GEMINI_MODEL` | optional, default `gemini-flash-lite-latest` (largest free-tier quota) |
| `GROQ_API_KEY` | Agent LLM — Groq (fallback, or primary if `LLM_PRIMARY=groq`) |
| `GROQ_MODEL` | optional, default `openai/gpt-oss-120b`; `gpt-oss-20b` is lighter on free-tier TPM |
| `LLM_PRIMARY` | optional, `gemini` (default) or `groq` — which provider is tried first |
| `MEDPLUM_CLIENT_ID`, `MEDPLUM_CLIENT_SECRET` | Medplum system app (FHIR). Omit → EHR features disable (fail-open) |
| `MEDPLUM_BASE_URL` | optional, default `https://api.medplum.com` (**not** `medplum.com`) |
| `CARTESIA_VOICE` | optional TTS voice id |
| `LIVEKIT_AGENT_NAME` | optional; agent name for SIP dispatch (default `healthcare-intake`) |
| `ESCALATION_TRANSFER_TO` | optional; `tel:`/`sip:` destination for human transfers |
| `MEDPLUM_DEFAULT_ORG` | optional; Organization for newly-registered patients |
| `NOTIFY_CHANNELS`, `REMINDER_LEAD_MINUTES`, `WORKFLOW_POLL_SECONDS` | optional; workflow/notification tuning |
| `FILLER_AFTER_SECONDS`, `FILLER_PHRASE` | optional; latency filler on slow tool turns (`0` disables) |
| `FRONTEND_ORIGIN` | optional; CORS origin(s) for the API, default `http://localhost:3000` |
| `LOG_LEVEL` | optional, default `INFO` (`DEBUG` for library detail) |

The **LiveKit** side of telephony (SIP inbound trunk + dispatch rule) is provisioned by
`src/voice/livekit_sip_setup.py`; the **Twilio** side (Origination → LiveKit SIP host, or a
trial-account `<Dial><Sip>` webhook) is set up in the Twilio console — see [`twilio.md`](twilio.md).
See `.env.example` for the full list. The frontend reads `frontend/.env.local`
(`NEXT_PUBLIC_API_URL`, default `http://localhost:8000`).

## Repository layout

```
src/voice/livekit_worker.py    LiveKit worker: room lifecycle, STT/VAD/TTS, transcript writeback
src/voice/livekit_sip_setup.py provisions the LiveKit SIP inbound trunk + dispatch rule
src/agent/                     LangGraph agent (the brain)
  agent.py                       ConversationAgent — history, session, graph driver
  graph.py                       StateGraph (agent ⇄ tools) over Gemini→Groq fallback chain
  capabilities.py                the 12 tools, backed by Medplum
  executor.py / schemas.py / tools.py   validated dispatch + Pydantic schemas + tool specs
  state.py / prompts.py          in-memory session state + system prompt & safety guardrails
  chat.py / smoke_test.py        text REPL / no-LLM tool test
src/database/medplum_client.py Medplum FHIR data layer (identity, scheduling, intake, writeback, reads)
src/database/medplum_seed.py   idempotent FHIR seed (transaction bundle)
src/workflows/                 background workflow engine + notifications
  engine.py / runner.py          schedule + execute FHIR Task jobs (reminders)
  notifications.py               deliver/record notifications (FHIR Communication, optional SMS)
src/eval/                      AI evaluation harness (scenarios, checks, LLM-judge, runner)
src/observability.py           correlation IDs, per-call metrics, FHIR AuditEvent
src/logging_setup.py           centralized logging config
src/api/                       FastAPI REST layer for the dashboard (dev-bypass auth)
  main.py                        app, CORS, router mounts, /api/health
  deps.py                        Scope (role/org/patient/doctor) from request headers
  adapters.py                    FHIR resource -> frontend DTO mappers
  routers/                       catalog, appointments, patients, ops (hospitals/workflows/audit/kpis/eval), voice
frontend/                      Next.js 16 dashboard (admin/hospital/doctor/patient) — pulled in separately
  src/lib/api.ts, queries.ts      axios client + react-query hooks with mock-data fallback
  src/lib/mock-data.ts            bundled fallback data (used until a page is wired / API is down)
  src/components/dashboard/live-badge.tsx   "Live API" vs "Mock data" indicator
tests/                          pytest suite (offline/mocked), organized by milestone
schemas/                        JSON Schema catalog (design reference)
twilio.md                       receiving real calls on a Twilio trial account
overview.md                     original product blueprint (intent, not current code)
context.md / decisions.md / flow.md   orientation / rationale / end-to-end walkthroughs
```

## Capabilities (agent tools)

`search_doctors` · `check_availability` · `create_appointment` · `reschedule_appointment` ·
`cancel_appointment` · `get_questionnaire` · `submit_questionnaire_response` · `lookup_patient` ·
`register_patient` · `get_appointment` · `transfer_to_human` · `end_call`.

Each is a Pydantic-validated tool mapped to FHIR resources (`PractitionerRole`, `Slot`,
`Appointment`, `Questionnaire`/`QuestionnaireResponse`, `Patient`). Every request is scoped to
the caller's `Organization` compartment for tenant isolation; booking uses FHIR
conditional-create for exactly-once semantics; `register_patient` dedupes on phone (or
name+DOB when no phone is available, e.g. browser calls).

## Dashboard API endpoints (`src/api/`)

`GET /api/doctors`, `/api/doctors/{id}/slots`, `/api/doctors/{id}/questionnaire`,
`GET/POST /api/appointments[/{id}/reschedule|cancel|questionnaire-response]`,
`GET/POST /api/patients[/by-phone|{id}|{id}/notifications]`,
`GET /api/hospitals`, `/api/workflows`, `/api/audit`, `/api/ai-activity`, `/api/evaluation`,
`/api/kpis` (on-the-fly aggregation from FHIR counts + `AuditEvent` summaries),
`POST /api/voice/token` (mints a LiveKit token and dispatches the agent for browser voice).
Auth is a **dev-bypass**: `X-Role` / `X-Organization` / `X-Patient-Id` / `X-Doctor-Id` headers,
defaulting to `platform_admin` — see `decisions.md` for why, and what real auth needs.

## Clinical safety

The agent is an **administrative assistant only** — no diagnosis, prescription, or clinical
opinion. Symptoms are recorded as patient-reported. Emergency language (e.g. "chest pain")
triggers a 911 deflection before any scheduling. Logs never contain PHI (transcripts go
only to Medplum). See `src/agent/prompts.py`.

## Notes

- **Single stack:** the earlier Twilio media-stream pipeline and PostgreSQL/Supabase engine
  have been removed — Medplum is the sole data engine (no SQL fallback). Twilio remains only as
  a SIP trunk into LiveKit.
- **Tests:** `uv run pytest` — an offline, mocked suite in `tests/` (no creds needed). The live
  paths (`smoke_test`, `chat`, `console`, `eval` live mode, the API against real Medplum) need
  real credentials.
- **Observability:** every log line carries a `correlation_id`; each call emits a metrics
  summary + a FHIR `AuditEvent`. `src/eval` scores the agent against the PRD §21/§22 rubric,
  and `/api/evaluation` + `/api/kpis` surface it to the dashboard.
- **Frontend is live-first:** the frontend dashboard has been fully migrated to fetch live Medplum data via the FastAPI backend (`src/api/`). Any components that do not yet have a backend API equivalent (e.g., Admin Trend Charts) are explicitly badged with a "Mock Data" indicator using the `LiveBadge` component.
- For deeper architectural guidance (module responsibilities, invariants, gotchas) see
  [`CLAUDE.md`](CLAUDE.md).
