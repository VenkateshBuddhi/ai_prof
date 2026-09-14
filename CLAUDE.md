# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An AI-native, multi-tenant healthcare voice agent. A patient calls in; the agent finds
specialists, checks availability, books appointments, and runs a conversational pre-visit
questionnaire. `overview.md` is the original product blueprint (a 20-step workflow); note it
predates the current stack — treat it as intent, not as a description of the code.

## Stack & layout

Single architecture: **LiveKit (voice) → LangGraph/ChatGroq (brain) → Medplum FHIR (engine)**.
Twilio is now **only a SIP trunk** into LiveKit; LiveKit owns all real-time media.

- `src/voice/livekit_worker.py` — the call entrypoint (LiveKit Agents worker).
- `src/agent/` — the LangGraph agent brain (ChatGroq + capability tools).
- `src/database/medplum_client.py` — Medplum FHIR: the core scheduling/identity/records engine.
- `src/workflows/` — background workflow engine + notifications (see below).
- `src/eval/` — AI evaluation harness (scenarios, deterministic checks, LLM-judge, runner).
- `src/observability.py` — correlation, per-call metrics, audit (see below).
- `src/logging_setup.py` — centralized logging (see below).
- `schemas/` — JSON Schema catalog kept as a **design reference** (the earlier relational
  model; the live engine is FHIR, not these shapes).
- `overview.md` / `output_markdown/Project_Requirements/` — product blueprint & PRD (intent,
  not a description of the code).

The legacy Twilio media-stream pipeline and the PostgreSQL/Supabase engine have been
**removed** — Medplum fully replaced them (there is no SQL fallback). Tests live in
`tests/` (pytest, offline/mocked); the runnable modules below are the manual dev loops.

## Commands (current stack)

```bash
uv sync                                                        # deps (Python 3.13, uv-managed)

# Seed / inspect the FHIR backend
uv run python -m src.database.medplum_seed --dry-run           # build+print bundle, no creds needed
uv run python -m src.database.medplum_seed                     # POST seed to Medplum

# Test the agent bottom-up
uv run python -m src.agent.smoke_test --phone +15550192834 --specialty Cardiology  # tools only, no LLM
uv run python -m src.agent.chat --show-tools                   # full text conversation (needs Groq)
uv run python -m src.agent.chat --phone +15550192834           # as a resolved Medplum patient

# Run the voice worker
uv run python -m src.voice.livekit_worker console              # local mic/speakers, no SIP
uv run python -m src.voice.livekit_worker dev                  # connect to LiveKit (dev)
uv run python -m src.voice.livekit_worker start                # production

# Telephony (LiveKit SIP inbound trunk + dispatch rule)
uv run python -m src.voice.livekit_sip_setup --list            # inspect
uv run python -m src.voice.livekit_sip_setup                   # create (idempotent)

# Background workflows (reminders/notifications) — run alongside the worker
uv run python -m src.workflows.runner                          # poll loop
uv run python -m src.workflows.runner --once                   # single pass

# Evaluate the agent (PRD §21/§22 scorecard)
uv run python -m src.eval.runner --offline --no-judge          # score fixtures, no creds
uv run python -m src.eval.runner                               # live scenarios + LLM-judge

# Tests
uv run pytest                                                  # offline/mocked suite
```

`smoke_test.py` and `chat.py` are the primary dev loops: `smoke_test` exercises every tool
against Medplum with **no LLM/LiveKit**, `chat` adds the LLM but no telephony. `twilio.md`
documents receiving real calls on a Twilio trial account (Programmable Voice `<Dial><Sip>`).

## Environment

`.env` (gitignored; see `.env.example`). Every entry point — the helper CLIs
(`chat.py`, `smoke_test.py`, `medplum_seed.py`) **and** the LiveKit worker — self-parses
`.env` with a small loader (`python-dotenv` is present but unused). The worker's `__main__`
calls `_load_env()` before `cli.run_app` so vars propagate to its job subprocesses.

Keys:
- LiveKit: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- Speech: `DEEPGRAM_API_KEY` (STT), `CARTESIA_API_KEY` (TTS)
- Brain: **Gemini primary → Groq fallback** (LangChain `with_fallbacks` in `graph.py`).
  `GEMINI_API_KEY` (+ optional `GEMINI_MODEL`, default `gemini-flash-lite-latest` — lite has
  the largest free-tier quota) and `LLM_PRIMARY` (gemini|groq) and/or
  `GROQ_API_KEY` (+ optional `GROQ_MODEL`, default `openai/gpt-oss-120b`; `gpt-oss-20b`
  is lighter on the free-tier TPM). Either key alone works; both = automatic failover.
- FHIR: `MEDPLUM_CLIENT_ID`, `MEDPLUM_CLIENT_SECRET` (+ optional `MEDPLUM_BASE_URL` —
  must be `https://api.medplum.com`, **not** `medplum.com`)
- Optional: `CARTESIA_VOICE`, `LIVEKIT_AGENT_NAME` (explicit SIP dispatch),
  `ESCALATION_TRANSFER_TO` (tel:/sip: for human transfer), `MEDPLUM_DEFAULT_ORG`
  (Organization for newly-registered patients), `LOG_LEVEL` (default INFO; DEBUG for libraries)

## Architecture — the agent brain (`src/agent/`)

LangGraph orchestration; the layers are deliberately separable so the tools/DB are testable
without the LLM, and the LLM without telephony.

- `agent.py` — `ConversationAgent`. Owns the message history + Pydantic session, drives the
  compiled graph. `start(phone)` (text path, Medplum lookup) / `start_with_context()` (worker
  path, context pre-resolved) / `send(text) -> reply`. Public surface used by the worker and
  `chat.py`; keep it stable.
- `graph.py` — the LangGraph `StateGraph`: `START → agent → (tool_calls? → tools → agent)* → END`
  over a tool-bound LLM chain (`ChatGoogleGenerativeAI` primary `.with_fallbacks([ChatGroq])`;
  `_chat_models()` includes each provider only if its key is set). Wraps each capability as a
  `StructuredTool` from its Pydantic schema, **bound to the session** (tools get `patient_id`/
  state without the LLM seeing them).
- `capabilities.py` — the 12 tool implementations, all calling Medplum via `get_medplum_client()`
  (`search_doctors`, `check_availability`, `create_appointment`, `reschedule_appointment`,
  `cancel_appointment`, `get_questionnaire`, `submit_questionnaire_response`, `lookup_patient`,
  `register_patient`, `get_appointment`, `transfer_to_human`, `end_call`).
- `executor.py` — `execute_tool()`: validates raw LLM args through Pydantic, dispatches via
  `_REGISTRY`, returns errors to the model instead of raising. `smoke_test` uses this directly.
- `schemas.py` / `tools.py` — Pydantic input models + the LLM-facing tool descriptions.
  `_REGISTRY` keys, `TOOLS_SCHEMA` names, and `schemas.py` must stay in sync (there's an
  assert-able parity in tests).
- `state.py` — `ConversationState` / `PersistentUserContext` / `AgentSession` + in-memory
  `SESSION_STORE`. **Naming collision warning:** this `AgentSession` is *our Pydantic state*,
  distinct from LiveKit's `AgentSession`; the worker aliases one of them.
- `prompts.py` — system prompt + clinical-safety guardrails.

Tools degrade gracefully: with Medplum unconfigured they return
`{"success": false, "error": "ehr_unavailable"}` rather than crashing.

## Architecture — the LiveKit worker (`src/voice/livekit_worker.py`)

`livekit-agents` 1.8 worker. Flow: Twilio SIP trunk → LiveKit SIP → room → this worker.
- `entrypoint(ctx)`: connect, `wait_for_participant()`, read caller number from
  `participant.attributes["sip.phoneNumber"]`, resolve identity via Medplum, build a
  `ConversationAgent`, start a LiveKit `AgentSession` (Deepgram STT + Silero VAD + Cartesia
  TTS), speak the greeting, and register a shutdown callback to flush the transcript.
- `HealthcareIntakeAgent(Agent)`: overrides `llm_node` (LiveKit's bring-your-own-LLM hook) —
  each completed user turn is fed to `ConversationAgent.send()` and the reply is yielded to
  TTS. **LiveKit owns STT/VAD/turn-detection/barge-in; the LangGraph brain owns reasoning + tools.**
- **`_BridgeLLM`**: a placeholder `llm.LLM` attached to the agent. LiveKit skips the response
  step entirely when `llm is None` (`agent_activity.py`), so this exists purely to make it call
  our `llm_node`; its `.chat()` is never invoked.
- **Escalation & hangup**: after the brain runs `transfer_to_human` or `end_call`, the worker
  sets `pending_transfer` / `pending_hangup` and — once the farewell finishes (an
  `agent_state_changed` leaving `speaking`) — does a real `ctx.transfer_sip_participant(...)` or
  `ctx.delete_room()` (hang up). These only take effect on real SIP calls (skipped in console).
- **Latency**: `llm_node` speaks a filler ("one moment…") if a turn exceeds ~1.2s.
- Silero VAD is loaded once in `prewarm()`; transcript captured via `conversation_item_added`
  and written back to Medplum (`Communication`) on shutdown.

## Architecture — the FHIR engine (`src/database/medplum_client.py`)

`MedplumClient` (+ cached `get_medplum_client()`) is the single data gateway: OAuth2
client-credentials (system app) with token caching, then FHIR R4 operations. Tool → FHIR map:

| Tool | FHIR |
|---|---|
| `search_doctors` | `PractitionerRole` (specialty text + org filter, `_include` Practitioner/Location) |
| `check_availability` | `Slot?schedule.actor=Practitioner/…&status=free` (`_include` Schedule→Location) |
| `create_appointment` | `POST Appointment` (`booked`) w/ conditional-create `If-None-Exist` = exactly-once; `PATCH Slot→busy` |
| `reschedule_/cancel_appointment` | read-modify-`PUT Appointment` (not JSON-Patch) + free/busy Slot patches |
| `get_appointment` | `Appointment?patient=…&status=booked` (for reschedule/cancel of existing) |
| `get_/submit_questionnaire` | `Questionnaire` matched by specialty; `POST QuestionnaireResponse` |
| `lookup_patient` / `register_patient` | phone→`Patient`; `POST Patient` (conditional on telecom) |
| identity / transcript | phone→`Patient`+`Organization`; transcript→`Communication` |

All FHIR calls route through `_send()` with **retry/backoff** (3 tries; 429/5xx + network) and
PHI-safe logs (`_safe_path` strips query strings; 4xx logs the `OperationOutcome` reason).

**Tenant isolation:** the caller's `Patient.managingOrganization` (`fhir_organization_id`) is
resolved before the conversation and every search is scoped to it. `create_appointment` uses
`session.context.fhir_patient_id` — a successfully created `booked` Appointment *is* the EHR
verification (no separate sync step).

Data-model assumptions (doctors as `PractitionerRole` with specialty/practitioner/location,
availability as `Slot` on a `Schedule` whose actor includes Practitioner+Location,
specialty-named `Questionnaire`s) are documented at the top of the client and produced by
`src/database/medplum_seed.py` (an idempotent transaction bundle, ~84 free slots, mirroring
the old `database/seed.sql`).

## Architecture — the workflow engine (`src/workflows/`)

Background jobs (PRD 5.28) with **no extra infra** — jobs are FHIR `Task`
resources in Medplum; notifications are FHIR `Communication` resources.
- `notifications.py` — `notify(patient_id, message, …)` records a `Communication`
  in the patient compartment (default `record` channel) and optionally sends
  Twilio SMS if `NOTIFY_CHANNELS` includes `sms`. No PHI in logs.
- `engine.py` — `on_appointment_booked()` (called inline from
  `capabilities.create_appointment`, best-effort) sends an immediate confirmation
  and enqueues an `appointment-reminder` Task due `REMINDER_LEAD_MINUTES` before
  the visit. `process_due_tasks()` executes Tasks whose `executionPeriod.start`
  has passed and marks them `completed` (transient failure stays `requested` for
  retry on the next poll).
- `runner.py` — standalone poller: `uv run python -m src.workflows.runner`
  (`--once` for a single pass). Run it alongside the LiveKit worker.
- Medplum Task helpers: `create_task` / `list_open_tasks` / `set_task_status`.

## Architecture — the eval harness (`src/eval/`)

Scores the agent against the PRD §21 categories and emits the §22 scorecard.
- `scenarios.py` — `EvalScenario` catalog (book, symptom→specialty, cancel, clarify,
  refuse-diagnosis, escalate, register-new-patient) with expected intent/tools/status/safety.
- `checks.py` — pure, deterministic scorers (the unit-tested core): intent, capability
  selection/success, tool-arg **provenance** (hallucinated-ID guard), booking verification,
  status, and rule-based safety (forbidden diagnosis regexes / required deflection / escalation).
- `judge.py` — optional `ChatGroq` LLM-as-judge (response correctness / clarification /
  safety, 0–1); degrades to `{"available": false}` without Groq.
- `runner.py` — `--offline` scores bundled `fixtures/*.json` (no creds); default runs the
  `SCENARIOS` live through `ConversationAgent` (+ judge); `--save-fixtures` captures runs.
  Prints the §22 scorecard and writes `eval_report.json` (gitignored).
- Reuses `ConversationAgent`, `observability.CallMetrics` (latency), `checks` for both paths.

## Architecture — observability (`src/observability.py`)

Correlation, metrics, and audit (PRD 5.34–5.36, 5.40), no extra infra.
- **Correlation** (§5.35): a `correlation_id` context var + `CorrelationFilter` injected into
  every log line; bound to the session id per turn (`agent.send`) and at call start.
- **Metrics** (§5.36): per-call `CallMetrics` (tool calls, success/failure, per-tool counts,
  LLM turns, duration), recorded from `executor.execute_tool` so it works across chat + voice.
  Active only between `start_call()`/`pop_call()`, so tests/one-off tool calls are no-ops.
- **Audit** (§5.40): `MedplumClient.create_audit_event()` writes a FHIR `AuditEvent`;
  `write_call_audit()` logs + persists the per-call summary on shutdown.

## Logging

`src/logging_setup.py` `setup_logging()` is called by every entry point. Format is
`[time] LEVEL Logger [correlation_id] message`. App loggers (`ConversationAgent`, `AgentGraph`,
`AgentCapabilities`, `AgentExecutor`, `MedplumClient`, `LiveKitWorker`, `WorkflowEngine`,
`Observability`) log at INFO; third-party libs are pinned to WARNING unless `LOG_LEVEL=DEBUG`.
The worker logs the full turn: `STT[...]` → `USER:` → `tool … -> success` → `AGENT:`.

## Testing

`tests/` (pytest, `asyncio_mode=auto`, `pythonpath=["."]`), organized by milestone and fully
**offline** — a `FakeMedplum` in `conftest.py` is injected via the cached-client globals, so
tool/workflow/observability logic runs against fake data with no network. `uv run pytest`
(62 tests). The live paths (`smoke_test`, `chat`, `console`, `eval` live mode) need real creds.

## Verification status

Confirmed against real Medplum + a live console voice session: `medplum_seed` (98 resources),
`smoke_test` (search → book → verify → questionnaire → reschedule → cancel → escalate), the
spoken loop in `livekit_worker console`, `eval --offline`, and the full `pytest` suite. The
LiveKit SIP inbound trunk + dispatch rule are provisioned (`livekit_sip_setup`). **Not yet
exercised:** a real inbound phone call (blocked on Twilio account funding — see `twilio.md`),
and therefore the real SIP transfer/hangup (both are no-ops in console mode).
