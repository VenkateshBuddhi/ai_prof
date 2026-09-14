# ai_prof — Healthcare Voice Intake Agent

An AI-native, multi-tenant healthcare voice agent. A patient calls in and, in natural
conversation, the agent finds the right specialist, checks real availability, books the
appointment, and collects a pre-visit questionnaire — then writes the call back to the
patient's clinical record.

```
Cellular caller
   │  (Twilio SIP trunk — trunking only)
   ▼
LiveKit SIP ──► LiveKit room ──► Voice worker (Deepgram STT · Silero VAD · Cartesia TTS)
                                        │  transcribed turn
                                        ▼
                             LangGraph agent (ChatGroq + tools)
                                        │  FHIR reads/writes
                                        ▼
                                Medplum (FHIR R4)  ── doctors · slots · appointments
                                                      questionnaires · transcript
```

- **Media / telephony:** LiveKit Agents (ultra-low-latency bidirectional audio). Twilio is
  only a SIP trunk passing cellular calls into LiveKit.
- **Reasoning:** a LangGraph `StateGraph` over a **Gemini→Groq** fallback chain, with tool-calling for every action.
- **System of record:** Medplum (FHIR R4) — identity, scheduling, intake, and the call transcript.

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
uv run python -m src.voice.livekit_worker start         # production (connects to LiveKit)

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
```

## Configuration (`.env`)

| Key | Purpose |
|---|---|
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | LiveKit server / rooms |
| `DEEPGRAM_API_KEY` | Speech-to-text |
| `CARTESIA_API_KEY` | Text-to-speech |
| `GEMINI_API_KEY` | Agent LLM — Google Gemini (primary) |
| `GROQ_API_KEY` | Agent LLM — Groq (automatic fallback if Gemini errors) |
| `MEDPLUM_CLIENT_ID`, `MEDPLUM_CLIENT_SECRET` | Medplum system app (FHIR). Omit → EHR features disable (fail-open) |
| `MEDPLUM_BASE_URL` | optional, default `https://api.medplum.com` (**not** `medplum.com`) |
| `GROQ_MODEL` | optional, default `openai/gpt-oss-120b` |
| `CARTESIA_VOICE` | optional TTS voice id |
| `LIVEKIT_AGENT_NAME` | optional; agent name for SIP dispatch (default `healthcare-intake`) |
| `ESCALATION_TRANSFER_TO` | optional; `tel:`/`sip:` destination for human transfers |
| `MEDPLUM_DEFAULT_ORG` | optional; Organization for newly-registered patients |
| `NOTIFY_CHANNELS`, `REMINDER_LEAD_MINUTES`, `WORKFLOW_POLL_SECONDS` | optional; workflow/notification tuning |
| `LOG_LEVEL` | optional, default `INFO` (`DEBUG` for library detail) |

The **LiveKit** side of telephony (SIP inbound trunk + dispatch rule) is provisioned by
`src/voice/livekit_sip_setup.py`; the **Twilio** side (Origination → LiveKit SIP host, or a
trial-account `<Dial><Sip>` webhook) is set up in the Twilio console — see [`twilio.md`](twilio.md).
See `.env.example` for the full list.

## Repository layout

```
src/voice/livekit_worker.py    LiveKit worker: room lifecycle, STT/VAD/TTS, transcript writeback
src/voice/livekit_sip_setup.py provisions the LiveKit SIP inbound trunk + dispatch rule
src/agent/                     LangGraph agent (the brain)
  agent.py                       ConversationAgent — history, session, graph driver
  graph.py                       StateGraph (agent ⇄ tools) over ChatGroq
  capabilities.py                the 12 tools, backed by Medplum
  executor.py / schemas.py / tools.py   validated dispatch + Pydantic schemas + tool specs
  state.py / prompts.py          in-memory session state + system prompt & safety guardrails
  chat.py / smoke_test.py        text REPL / no-LLM tool test
src/database/medplum_client.py Medplum FHIR data layer (identity, scheduling, intake, writeback)
src/database/medplum_seed.py   idempotent FHIR seed (transaction bundle)
src/workflows/                 background workflow engine + notifications
  engine.py / runner.py          schedule + execute FHIR Task jobs (reminders)
  notifications.py               deliver/record notifications (FHIR Communication, optional SMS)
src/eval/                      AI evaluation harness (scenarios, checks, LLM-judge, runner)
src/observability.py           correlation IDs, per-call metrics, FHIR AuditEvent
src/logging_setup.py           centralized logging config
tests/                         pytest suite (offline/mocked), organized by milestone
schemas/                       JSON Schema catalog (design reference)
twilio.md                      receiving real calls on a Twilio trial account
overview.md                    original product blueprint (intent, not current code)
```

## Capabilities

`search_doctors` · `check_availability` · `create_appointment` · `reschedule_appointment` ·
`cancel_appointment` · `get_questionnaire` · `submit_questionnaire_response` · `lookup_patient` ·
`register_patient` · `get_appointment` · `transfer_to_human` · `end_call`.

Each is a Pydantic-validated tool mapped to FHIR resources (`PractitionerRole`, `Slot`,
`Appointment`, `Questionnaire`/`QuestionnaireResponse`). Every request is scoped to the
caller's `Organization` compartment for tenant isolation; booking uses FHIR conditional-create
for exactly-once semantics.

## Clinical safety

The agent is an **administrative assistant only** — no diagnosis, prescription, or clinical
opinion. Symptoms are recorded as patient-reported. Logs never contain PHI (transcripts go
only to Medplum). See `src/agent/prompts.py`.

## Notes

- **Single stack:** the earlier Twilio media-stream pipeline and PostgreSQL/Supabase engine
  have been removed — Medplum is the sole data engine (no SQL fallback). Twilio remains only as
  a SIP trunk into LiveKit.
- **Tests:** `uv run pytest` — an offline, mocked suite in `tests/` (no creds needed). The live
  paths (`smoke_test`, `chat`, `console`, `eval` live mode) need real credentials.
- **Observability:** every log line carries a `correlation_id`; each call emits a metrics
  summary + a FHIR `AuditEvent`. `src/eval` scores the agent against the PRD §21/§22 rubric.
- For deeper architectural guidance (module responsibilities, invariants, gotchas) see
  [`CLAUDE.md`](CLAUDE.md).
