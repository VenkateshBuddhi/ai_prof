# decisions.md — architectural decision log

Why the system is built the way it is. Written after the fact from the actual build
history (this was built conversationally, iterating with a live user, not from a
pre-written spec) — each entry is a real decision point, the alternatives that were on
the table, and why the chosen path won. Organized roughly chronologically by theme, not
strictly by date.

---

## 1. Agent brain: a decoupled `src/agent/` package, testable without voice or telephony

**Context.** The first ask was "build an agent layer with all the capabilities, but
don't touch the voice pipeline yet — I want to test it without making a call."

**Decision.** `src/agent/` was built as a fully standalone package: its own state
(`AgentSession`, not the voice pipeline's), its own tool registry, and two CLI drivers
(`chat.py` for a live LLM conversation, `smoke_test.py` for tool-only testing with no
LLM at all). It was wired into the voice worker only once it worked standalone.

**Why.** Testing a conversational agent through a live phone call is slow and
non-reproducible (you have to speak, listen, and remember what you said). A text/no-LLM
path lets every layer be validated independently and quickly, and this same separation
later made the LangGraph swap (see #2), the Medplum swap (see #4), and the eval harness
(see #12) each a change in one layer without touching the others.

**Consequence.** The brain has zero LiveKit imports. The voice worker is the only file
that knows both the brain and the telephony layer exist.

---

## 2. Orchestration: LangGraph, not a hand-rolled tool loop

**Context.** The first cut of the agent used a plain `for`-loop calling the Groq API
directly and dispatching tool calls by hand. It worked, but the user asked which
framework was handling orchestration, and — on hearing "none, it's hand-rolled" — asked
to refactor onto a real framework.

**Decision.** Rebuilt the loop as a LangGraph `StateGraph`: `START → agent →
(tool_calls? → tools → agent)* → END`, with tools exposed as LangChain `StructuredTool`s
built from the same Pydantic schemas the executor already validated against.

**Why LangGraph specifically (over LlamaIndex, CrewAI, raw LangChain, etc.).** The
existing code already validated tool args with Pydantic and dispatched through a
registry — LangGraph's tool-calling model maps onto that almost one-to-one, so the
refactor didn't require redesigning the tool layer, just re-hosting it. It's also the
lowest-ceremony of the graph frameworks for a single linear agent loop (no need for
CrewAI's multi-agent roles or LlamaIndex's retrieval-first framing).

**Consequence.** A `_BridgeLLM` placeholder was later needed to make LiveKit's session
call into this graph at all (see #7) — an integration cost of using a "real" LLM object
where a callback would have suffered, paid once.

---

## 3. Voice transport: LiveKit replacing Twilio's raw media-stream WebSocket

**Context.** The original prototype had a hand-rolled Twilio `<Stream>` WebSocket
pipeline in `app.py`/`src/voice/pipeline.py` — direct μ-law audio frames, a custom
energy-based VAD, and direct HTTP calls to Groq Whisper/LLM/Cartesia. The user asked to
replace it with LiveKit for lower latency, with Twilio kept only as a SIP trunk.

**Decision.** Full replacement: `src/voice/livekit_worker.py` (a `livekit-agents`
worker) now owns STT (Deepgram), VAD (Silero), turn-detection, barge-in, and TTS
(Cartesia). Twilio's role was reduced to carrying the call over SIP into LiveKit.

**Why.** LiveKit Agents is a maintained framework for exactly this problem (streaming
STT/VAD/turn-taking/TTS orchestration) — the hand-rolled version was reinventing
barge-in detection and audio buffering that a framework already solves, with worse
latency (Twilio's raw media stream has no built-in turn-detection, so the old pipeline
used a fixed silence-timeout heuristic instead of LiveKit's real endpointing).

**Consequence.** The old pipeline, `app.py`, `pipeline.py`, and `capabilities.py` (the
voice-specific tool copy) were deleted outright once LiveKit was validated end-to-end
(see #5 for why deletion, not archival).

---

## 4. Data engine: Medplum (FHIR) fully replacing PostgreSQL/Supabase

This was the single largest architectural pivot, and it happened in two steps.

### 4a. Medplum introduced for identity + transcript only

**Context.** Once LiveKit was in place, the user asked to add Medplum for
multi-tenant patient identity resolution and to write the call transcript back to a
clinical record — alongside the existing Postgres-backed scheduling engine.

**Decision.** `src/voice/medplum_client.py` (later moved) added `find_patient_by_phone`
and `create_communication`, called from the worker before/after the conversation. The
scheduling tools kept using `SupabaseClient`/Postgres.

### 4b. Medplum promoted to the entire scheduling engine

**Context.** The user then asked: "do I still need Postgres and Supabase now that
Medplum works?" The honest answer was that nothing fell back between them — they were
two unrelated stores doing different jobs. The user then said: "go on and do Medplum the
core engine."

**Decision.** Rewrote every capability (`search_doctors`, `check_availability`,
`create_appointment`, `reschedule_appointment`, `cancel_appointment`,
`get_questionnaire`, `submit_questionnaire_response`) against Medplum FHIR resources —
`PractitionerRole`, `Slot`/`Schedule`, `Appointment`, `Questionnaire`/
`QuestionnaireResponse` — replacing the SQL calls entirely. `src/database/medplum_seed.py`
was written to produce an idempotent FHIR transaction bundle mirroring the old
`database/seed.sql` fixture data.

**Why Medplum over keeping Postgres as the engine, or over a dual-write approach.**
Medplum *is* a real, spec-compliant FHIR server — using it as a bolt-on for two
endpoints while a hand-rolled Postgres schema did the actual scheduling meant
maintaining two overlapping data models with no clear source of truth. Once identity was
already flowing through Medplum, the honest architecture was to make it the *only* data
model, matching the PRD's EHR-integration intent more literally (Medplum is arguably the
EHR itself, not an adapter target).

**Alternative considered and rejected: Supabase as a KPI/analytics sink alongside
Medplum.** Raised explicitly later (§18) when building dashboard KPIs — rejected for the
same reason: introducing a second store for derived data reopens the "which one is
truth" question this decision closed. Deferred instead of adopted (see #18).

**Consequence.** `src/database/supabase_db.py`, `database/`, `supabase/`, and the
`asyncpg`/`psycopg2-binary` dependencies were deleted in a later cleanup pass (#5).
`schemas/*.json` (the relational JSON Schema catalog) was kept, explicitly demoted to
"design reference" — it documents entity shapes even though FHIR resources are now the
literal storage format.

---

## 5. Cleanup: delete the legacy stack outright, don't keep it as a fallback

**Context.** After Medplum became the engine and LiveKit became the transport, the
repository still contained the fully-superseded Twilio pipeline and the SQL layer. The
user asked directly whether to drop them.

**Decision.** Deleted `app.py`, `src/voice/pipeline.py`, `src/voice/capabilities.py`,
`check_twilio.py`, `test_twilio_call.py`, `main.py`, `src/database/supabase_db.py`,
`database/`, `supabase/`, and the now-unused Postgres client libraries. Kept
`schemas/` as an explicitly-labeled reference.

**Why delete instead of archive/flag-gate.** Nothing in the active code path used the
old stack — it wasn't a fallback (see #4b), it was dead weight that made "which store is
real?" an open question for anyone reading the repo. Git history preserves it if it's
ever needed again; a living repo shouldn't carry two parallel, half-working
implementations of the same feature.

---

## 6. LLM provider selection under real quota constraints

**Context.** Groq was the original/default LLM provider. In practice, the configured
Groq account had no Llama models available at all (`llama-3.3-70b-versatile` 404'd), and
the fallback model (`openai/gpt-oss-120b`) later hit the free tier's 8,000
tokens-per-minute cap mid-conversation, causing a visible failure during a live call.
The user then asked to add Gemini as primary with Groq as fallback; Gemini in turn hit
its own daily-quota wall (`gemini-3.6-flash`'s 20-requests/day cap) and a retired-model
404 (`gemini-2.0-flash`).

**Decision.** `src/agent/graph.py` builds an **ordered fallback chain** via LangChain's
`.with_fallbacks()`: whichever provider is set as primary (`LLM_PRIMARY`, env-driven,
default `gemini`) is tried first; if it raises (quota, retired model, network), the
other provider is tried automatically, mid-request, transparently to the conversation.
Each provider's retry policy is tuned differently — Gemini uses `max_retries=0` (fail
instantly on quota errors so the fallback fires without a multi-second retry storm),
Groq uses `max_retries=6` (Groq's 429s legitimately clear within milliseconds, so
retrying in place is worth it there). The default Gemini model was moved to
`gemini-flash-lite-latest`, which carries a much larger free-tier quota than the
`3.6-flash` default.

**Why a fallback chain instead of picking one provider and fixing its limits.** Every
single-provider free tier hit a real wall during actual testing — this wasn't
theoretical. A fallback chain converts "the whole conversation error path fires" into
"one silent provider switch," which is the difference between a broken demo and an
invisible hiccup. Making the *order* configurable (`LLM_PRIMARY`) rather than hardcoded
let the user flip to Groq-only instantly when Gemini's daily quota was fully spent,
without a code change — this was used live during testing.

**Consequence.** Tool-calling had to work identically across both providers; LangChain's
provider-agnostic `bind_tools` made this a non-issue in practice.

---

## 7. `_BridgeLLM`: a placeholder LLM to satisfy LiveKit's internal gate

**Context.** After wiring `llm_node` (LiveKit's bring-your-own-LLM override) into the
worker, live calls transcribed correctly (confirmed via Deepgram logs) but the agent
never replied — no crash, no log line reaching the brain at all.

**Decision.** Traced into `livekit-agents`' own source
(`agent_activity.py`) and found: `elif self.llm is None: return  # skip response if no
llm is set` — LiveKit's `AgentSession` silently drops every user turn if no LLM is
attached, regardless of whether a custom `llm_node` exists. Added `_BridgeLLM`, a
minimal `llm.LLM` subclass whose `.chat()` raises `NotImplementedError` and is never
called — it exists purely to make `self.llm is not None` true so LiveKit proceeds to
invoke the real `llm_node`.

**Why not switch to a different integration point in LiveKit.** `llm_node` is the
documented extension point for bringing an arbitrary agent framework's response
generation into LiveKit's turn loop; the alternative (implementing a full LangGraph-to-
`llm.LLM` adapter with real streaming semantics) is significantly more code to solve a
problem that's actually just an internal `None`-check. The placeholder is small, its
purpose is documented in the source, and it was verified as a real `llm.LLM` instance in
tests.

---

## 8. Escalation and hangup: act only after the farewell finishes speaking

**Context.** `transfer_to_human` and (later) `end_call` needed to actually disconnect
the caller on a real SIP call, not just say a line and leave the line open.

**Decision.** The worker doesn't transfer/hang up the instant the tool succeeds. It sets
a `pending_transfer` / `pending_hangup` flag, lets the farewell TTS play out, and
performs `ctx.transfer_sip_participant(...)` / `ctx.delete_room()` only when
`agent_state_changed` reports the agent has left the `speaking` state.

**Why.** Doing it immediately would cut the farewell mid-sentence — a caller told
"Transferring you now" who is disconnected before hearing the second half of that
sentence is a bad, jarring experience, particularly for a healthcare product. This is
also why `end_call` has an explicit prompt instruction not to fire while a booking or
questionnaire is mid-flight — it's a two-part contract (say the closing line, *then*
signal completion) enforced across the prompt and the worker.

**Consequence.** Both actions are no-ops in `console` mode (LiveKit skips SIP operations
outside a real call) — verified and documented, not a bug.

---

## 9. Closing capability gaps found by live testing, not by spec review

Several tools were added reactively, after a live call actually failed, rather than
being planned upfront. This is recorded because it explains *why* the tool set doesn't
match any single design document one-to-one — it matches what real conversations needed.

- **`get_appointment` + `lookup_patient`.** The agent could reschedule/cancel only
  appointments made *within* the current session — there was no way to look up a
  patient's existing bookings. Added so reschedule/cancel work on real prior
  appointments, and so the prompt could require "call `get_appointment` first, never
  guess an ID."
- **`register_patient`.** A live call with an unrecognized phone number dead-ended: the
  agent tried to "create a new patient record" but no such tool existed, so it
  escalated. Added a real Medplum-backed registration tool, with the prompt updated to
  collect name + DOB first.
- **`end_call`.** Originally the agent just fell silent after a booking completed —
  nothing hung up the call. Added as an explicit tool so the agent's own turn signals
  "this conversation is over," rather than relying on the caller to hang up or an
  external timeout.

**Why fix these as they were found rather than pre-building a "complete" tool set.**
The agent's actual failure modes only showed up under real conversation, not by reading
the PRD's capability list in the abstract (e.g. the PRD lists `get_appointment` as a
capability, but the concrete need — "the model just tried to hallucinate an appointment
ID" — only became visible in a transcript). Building reactively kept every tool tied to
a reproduced failure, which is also why each one has a corresponding prompt-level
instruction, not just an executor entry.

---

## 10. Patient registration dedup key: phone when known, else name+DOB

**Context.** After `register_patient` shipped, testing via the browser (no SIP phone
number available) produced four duplicate "Venkatesh Budhi" `Patient` records — one per
registration attempt — because the FHIR conditional-create key was phone-only, and the
browser flow often had no phone captured.

**Decision.** `MedplumClient.create_patient`'s `If-None-Exist` key falls back to
`family+given+birthdate` when no phone is supplied.

**Why not require a phone for registration.** Browser callers have no equivalent of SIP
caller-ID, so requiring a phone would make browser-only registration impossible. Name+DOB
is a reasonable secondary key for a prototype; it's explicitly documented as weaker (STT
misspellings of a surname won't match) and phone remains the primary, more reliable key
for real telephone calls.

---

## 11. Latency mitigation: a filler phrase, then made optional, then defaulted off

**Context.** Booking/questionnaire turns route through multiple LLM calls and Medplum
round-trips, taking several seconds with nothing spoken — a bad experience on a voice
call. A filler phrase ("Let me check that for you, one moment.") was added, fired if a
turn exceeded a threshold.

**Decision, in three steps as real usage revealed the tuning needed:**
1. Initial threshold 1.2s — turned out to fire on almost *every* turn once real LLM
   latency was measured, becoming an annoyance rather than a cover for silence.
2. Raised to 4s and shortened the phrase to "One moment…", so only genuinely slow
   (multi-tool) turns triggered it.
3. Even at 4s, the user found any repetition intrusive once the Gemini/Groq latency
   issues were separately fixed and turns got fast — so `FILLER_AFTER_SECONDS` was made
   a first-class env switch (`0` disables it entirely) and set to `0` in the working
   `.env`.

**Why keep the mechanism but default it off, rather than removing it.** The underlying
problem (multi-second dead air during tool-heavy turns) is real and will return under
different network/LLM conditions; deleting the code would lose that mitigation
permanently for a UX preference that might change. Making it a tunable env var instead
of a constant means the tradeoff (a rare interjection vs. rare silence) is a deployment
decision, not a code decision.

---

## 12. Testing: pytest with a single `FakeMedplum` fixture, fully offline

**Context.** No test framework existed until explicitly requested ("write tests for
every part, like milestones"), by which point the agent, workflows, observability, and
(later) the API all depended on a live Medplum connection for any real exercise.

**Decision.** One `FakeMedplum` class in `tests/conftest.py` implements every method the
real `MedplumClient` exposes, injected via the same module-level cache
(`get_medplum_client()`) the production code already used for connection reuse. Every
test file is organized by milestone/component (`test_capabilities.py`,
`test_medplum_retry.py`, `test_workflows.py`, `test_eval.py`, `test_api.py`, etc.) and
runs with zero network calls or credentials.

**Why one fake instead of mocking each call site individually.** The production code
already had exactly one seam — `get_medplum_client()` — because that was built for
connection caching, not testability; reusing it for test injection meant no test-only
code paths were added to production modules. A single fake object is also easier to keep
in sync with the real client's interface than dozens of per-test mocks.

**Consequence.** The suite (73+ tests) runs in under a second and needs no credentials,
so it doubles as a CI-safe regression check even though nothing in this repo runs CI yet.

---

## 13. FHIR writes: read-modify-`PUT`, not multi-op JSON-Patch

**Context.** `reschedule_appointment` and `cancel_appointment` initially used FHIR
JSON-Patch (`PATCH` with an ops array) to update multiple fields on an `Appointment` in
one call. Live testing against Medplum returned `400 Bad Request` on the multi-op patch
(single-field patches, e.g. a `Slot` status flip, worked fine).

**Decision.** Both methods now do read-modify-write: `GET` the resource, mutate the
Python dict in place, `PUT` the whole resource back. Additionally, `_send()`'s error
handling was extended to parse and log the FHIR `OperationOutcome` reason on any 4xx,
so future failures are diagnosable instead of just a bare status code.

**Why not debug the exact JSON-Patch syntax Medplum expects.** Read-modify-`PUT` is
strictly more portable across FHIR server implementations (every server accepts a full
resource `PUT`; not every server accepts every JSON-Patch construct identically) and was
faster to make correct under real testing pressure. Single-field patches (slot status)
were left as `PATCH` since those were already proven to work.

---

## 14. Reliability: retry/backoff on every FHIR call, not per-method

**Context.** DNS/network flakiness on the development machine surfaced repeatedly as
`ConnectTimeout`/`ConnectError` during testing (a real environment issue, not a code bug
— confirmed by testing the same host against public DNS resolvers). Separately, the PRD
explicitly calls for "Basic retry/recovery" on EHR failures.

**Decision.** All FHIR HTTP calls funnel through one method, `MedplumClient._send()`,
which applies bounded exponential backoff (3 attempts) on transport errors, timeouts,
and `429`/`5xx` responses — implemented once, inherited by every `_search`/`_read`/
`_create`/`_patch`/`_update`/`transaction` caller.

**Why centralize instead of wrapping each capability's Medplum calls individually.** The
alternative (retry logic in each of the ~15 call sites) would drift out of sync and be
easy to forget on new methods; centralizing in the one HTTP entry point makes retry
behavior a property of *how the client talks to Medplum*, not something each caller has
to remember to opt into. It also made the PHI-safety fix (see #15) a one-line addition
in one place.

**Explicit limit acknowledged.** Retry cannot fix a genuinely broken DNS resolver (an
instant `gaierror`, not a timeout) — that was diagnosed separately as an actual
environment problem and fixed by changing the machine's DNS servers, not by the retry
code. The decision log distinguishes "retry helps" (transient network blips, rate
limits) from "retry can't help" (misconfigured local resolver) because conflating them
wastes debugging time.

---

## 15. Privacy: strip PHI from every log line by construction, not by convention

**Context.** The PRD requires privacy-aware logging (no raw PHI in logs). Retry logging
in particular risked leaking phone numbers via query strings (e.g.
`Patient?telecom=+15550192834` appearing in a retry warning).

**Decision.** `_safe_path()` strips the query string from any URL before it's logged, applied
uniformly inside `_send()`. Separately, `MedplumClient`'s identity-lookup and
communication-write error handlers log only the exception *type*, never the exception
message (which could contain the search term).

**Why enforce this in the shared logging path rather than trusting each call site to be
careful.** The same reasoning as #14 — a rule that depends on every future contributor
remembering it at every call site will eventually be violated; a rule enforced in the
one shared function can't be forgotten.

---

## 16. Background workflows and observability: reuse Medplum, add no new infrastructure

**Context.** Two PRD Must-Haves — a workflow/reminder engine (§5.28) and AI
usage/audit tracking (§5.34–5.36, §5.40) — were the largest remaining gaps after the
core booking flow worked. The natural "proper" implementations (Temporal, ClickHouse/
OpenTelemetry, per the original blueprint's tech matrix) were available as options.

**Decision.** Both were built entirely on Medplum resource types instead of new
services:
- **Workflows** = FHIR `Task` resources (`status: requested → completed/failed`,
  `executionPeriod.start` as the due time). `src/workflows/engine.py` enqueues a
  reminder `Task` on booking; `runner.py` is a standalone poller that executes due
  Tasks. Notifications are recorded as FHIR `Communication` resources (with an optional
  Twilio SMS channel, off by default).
- **Observability** = a `correlation_id` `contextvars.ContextVar` threaded through
  logging (no new tracing infra), an in-memory per-call `CallMetrics` object populated
  by the existing `execute_tool()` call site, and a FHIR `AuditEvent` written once per
  call summarizing those metrics.

**Why not stand up Temporal/ClickHouse for a prototype.** Those are the *right* choice
at production scale, but for this system's actual size (a handful of calls at a time,
demo/evaluation volume), they're pure operational overhead — another service to run,
configure, and keep in sync with Medplum's data. Every workflow/audit concept mapped
cleanly onto an existing FHIR resource type (`Task`, `Communication`, `AuditEvent`),
which meant zero new infrastructure and one dependency graph. This is the same reasoning
as decision #4 (single source of truth) applied to two more subsystems.

**Explicitly acknowledged tradeoff.** Polling FHIR `Task` resources for due jobs doesn't
scale the way a real scheduler does, and per-call `AuditEvent` summaries aren't a
substitute for a real time-series metrics store (see #18). These were accepted as
prototype-appropriate, not as a claim that they're production-final.

---

## 17. AI evaluation: deterministic rule-based checks as the core, LLM-as-judge as an addable layer

**Context.** The PRD's §21/§22 evaluation framework asks for both objective checks
(intent match, tool selection, booking verification) and more subjective quality
judgments (response correctness, appropriate clarification). Given a straight choice
between the two, the user opted to build both.

**Decision.** `src/eval/checks.py` implements every check as a pure, synchronous
function operating on plain data (final state, accumulated tool calls, assistant
transcript) — no network, fully unit-testable, and shared identically between a **live**
run (drives the real `ConversationAgent`) and an **offline** run (scores pre-recorded
JSON fixtures). `src/eval/judge.py` is a separate, optional layer: one `ChatGroq` call
per scenario, rubric-scored, degrading to `{"available": false}` if no key is
configured — the deterministic scorecard is complete with or without it.

**Why keep the LLM judge strictly optional and separate rather than merging it into the
core checks.** Rule-based checks are reproducible and free to run in CI-like offline
mode; an LLM judge is neither (it costs tokens and its output varies run to run).
Keeping it as an additive, gated layer means the harness is always runnable
(`--offline --no-judge` needs zero credentials) while still supporting the richer
judgment when it's wanted.

**Tool-argument provenance check, specifically.** One check (`score_tool_args`) doesn't
just verify a tool was called — it verifies every ID argument (`doctor_id`, `slot_id`,
etc.) passed to a booking-mutating tool actually appeared in an *earlier* tool's result,
catching a model hallucinating an identifier instead of using a real one. This was
included because ID hallucination is a realistic and specific failure mode for a
tool-calling LLM in a booking system, not a generic "did it call the right function"
check.

---

## 18. Dashboard KPIs: computed on the fly from Medplum, Supabase sink deferred

**Context.** Wiring `/api/kpis` required rate/average metrics (booking success rate,
average AI latency, escalation rate) that no single FHIR query can answer directly. The
user asked directly whether to add a Supabase analytics table to support these (and the
dashboard's time-series trend charts).

**Decision.** Chose **Medplum-only, on-the-fly aggregation** for now: `/api/kpis` runs a
handful of FHIR `_summary=count` queries for exact counts, and a bounded scan of recent
`AuditEvent`s (whose `outcomeDesc` already carries the JSON `CallMetrics` summary from
decision #16) reduced in Python for rates/averages. A companion decision was made
explicit but not (yet) acted on: **if/when time-series trend charts are wired, a
Supabase table would be the right tool** — described as a *derived, rebuildable
analytics sink*, not a second source of truth, mirroring the reasoning in #4/#16.

**Why not build the Supabase sink immediately.** The KPI *tiles* (single current numbers)
don't need `GROUP BY`/time-bucketing — a bounded FHIR scan is sufficient and adds no new
infrastructure, consistent with the project's overall bias (#4, #16). The *trend charts*
genuinely do need SQL-style aggregation and remain on mock data, explicitly flagged
rather than half-implemented against a store not built for it.

**Known limitation, acknowledged rather than hidden.** The audit-event scan window is
bounded (last ~200 events) — correct at prototype volume, and rates are clamped to 100%
to handle mismatched historical denominators (e.g. more lifetime questionnaire responses
than currently-booked appointments).

---

## 19. Frontend integration: adapt to the pulled-in Next.js app, don't rebuild it

**Context.** A separately-generated Next.js 16 dashboard (~50 pages across
admin/hospital/doctor/patient roles, matching the PRD's §11 dashboard spec) was pulled
into `frontend/` with its own commit history. It rendered entirely from
`src/lib/mock-data.ts`; `axios` and `@tanstack/react-query` were installed but unused; a
fake login (`setTimeout` + `router.push`) stood in for auth.

**Decision.** Rather than rebuild or restructure the frontend, a FastAPI layer
(`src/api/`) was written specifically to match the frontend's existing TypeScript DTO
shapes (`frontend/src/types/index.ts`) — `adapters.py`'s functions are named and shaped
to produce exactly `Doctor`, `Appointment`, `Patient`, `Hospital`, `Workflow`,
`AuditEvent` as already defined there, not a new API-native schema the frontend would
need to be rewritten to consume.

**Why adapt the backend to the frontend's contract instead of the reverse.** The
frontend's page components, `DataTable` columns, and business labels were already
written against those types; changing them would mean touching ~50 files for no
functional gain. Writing the adapter layer to match cost one file
(`src/api/adapters.py`) and kept the frontend's existing UI code untouched.

**Wiring strategy: live-data first + empty state fallbacks.**
`frontend/src/lib/queries.ts`'s `useLive()` hook tries the real API. Initially it fell back to bundled mock data on any error, but this was updated to fallback to empty states (`[]` or `{}`) instead to prevent confusing mix-ups of real and mock records. Every dashboard page was systematically wired to these hooks, displaying a green "Live API" badge when successful, or an amber "Mock Data" or "Error" badge when falling back to the empty state.

**Why fallback-to-empty instead of mock.** While the dashboard was explicitly designed to "use fallback mock data" if the backend is unreachable (e.g. for a Vercel preview), pulling in static mock data masked the true state of the backend and created confusion when live and mock data were intermingled. Replacing it with an empty state ensures a clear boundary between real data and error states. Incremental wiring meant each page could be verified against a running backend before moving to the next.

**Deliberately left on mock (pure UI components):**
- Components without a matching backend write/read equivalent (e.g. Admin Trend Charts, Questionnaire lists, EHR Connector config) were preserved to showcase the UI design. These specific components have been explicitly hard-coded with a `<LiveBadge live={false} />` tag right next to their titles to ensure they are never mistaken for live backend data.
- The `admin/ai-activity` page was fully migrated by parsing the FHIR `AuditEvent` `outcomeDesc` payload on the frontend, bridging the gap between the `AIConversation` UI shape and the FHIR backend's raw output.

---

## 20. Dashboard auth: an explicit, temporary dev-bypass, not deferred silently

**Context.** Wiring the dashboard to real data required *some* notion of "who is asking
and what can they see" (a platform admin sees everything; a hospital admin should see
one organization; a patient should see only their own records). Real authentication
(Supabase JWT verification, since the frontend already ships Supabase client libraries)
was not yet built. Asked directly how to sequence this, the user chose to defer real
auth and get read endpoints working first.

**Decision.** `src/api/deps.py`'s `get_scope()` reads role/scope from plain request
headers (`X-Role`, `X-Organization`, `X-Patient-Id`, `X-Doctor-Id`), defaulting to
`platform_admin` if absent. Every router accepts a `Scope` dependency and is written to
use it for filtering (e.g. `list_appointments` scopes by `patient_id` when
`role=patient`) — so the *shape* of scoped access is already correct, only the
*verification* of the caller's claimed identity is missing.

**Why build the scoping logic now against a fake identity, rather than wait for real
auth to build both together.** This let every read endpoint and dashboard page get
wired and verified against real Medplum data immediately, which was the priority at the
time (`decisions.md` #19). Writing the `Scope` dependency correctly *now*, even though
its input is currently untrusted, means swapping in real JWT verification later is a
one-function change (`get_scope`'s body) rather than a second pass through every router.

**Why this is flagged prominently rather than left implicit.** Header-based scope is
trivially spoofable — it is explicitly documented (here, in `CLAUDE.md`, and in
`context.md`) as **not a security boundary**, so it isn't mistaken for a finished auth
system by a future reader. This is also exactly why `doctor/*`/`patient/*` dashboard
pages were left unwired (#19) — wiring them against unverified scope would produce
data-isolation bugs that look like they work in a demo and are actually a privacy
violation.

---

## 21. Telephony testing path: Twilio trial + Programmable Voice, not paid SIP Trunking

**Context.** Real inbound phone calls require Twilio to originate SIP into LiveKit.
Twilio's Elastic SIP Trunking (the "correct" product for this) requires a paid,
upgraded account; the available Twilio account was suspended for non-payment and
couldn't be upgraded.

**Decision.** Documented (`twilio.md`) and used a different path: a **free Twilio trial
number**, with its Voice webhook pointed at a **TwiML Bin** containing
`<Dial><Sip>sip:...@<livekit-sip-host></Sip></Dial>` — bridging the call into the same
LiveKit inbound trunk/dispatch rule (`src/voice/livekit_sip_setup.py`) that a paid SIP
trunk would have used.

**Why not wait for a paid account, or simplify to browser-only voice.** The user
specifically wanted a real phone-call test path without paying for SIP Trunking.
`<Dial><Sip>` is a Programmable Voice feature available on free trial credit and
produces the identical LiveKit-side experience (same trunk, same dispatch rule, same
worker) — the only cost is the trial's mandatory "press any key" preamble and its
limited daily credit, both explicitly called out as trial-only artifacts in `twilio.md`,
not permanent architecture.

**Consequence — a debugging trail worth recording.** Getting this working surfaced two
real misconfigurations along the way, both fixed and documented in `twilio.md`'s
troubleshooting table: (1) the LiveKit SIP host guessed from the project's *dashboard*
URL was wrong — LiveKit assigns a separate, differently-named SIP subdomain, found by
checking the LiveKit console directly; (2) the account-suspension error ("service
unavailable" after ~16s, with LiveKit showing zero received calls) was initially
mistaken for a SIP transport/routing problem before the Twilio billing banner was seen —
recorded as a reminder that "call times out with no SIP logs on the receiving side" can
mean the *sender* never left its own network, not a routing bug on the receiving end.

---

## Cross-cutting theme

Read together, most of these decisions follow the same two rules, applied repeatedly to
different subsystems:

1. **One source of truth, not an additional layer "just in case."** Medplum absorbed
   scheduling (#4), workflows (#16), and audit (#16) instead of each getting its own
   store; Supabase was twice considered and twice deferred (#4, #18) for the same
   reason. The frontend's own mock-data fallback (#19) is the one deliberate exception —
   accepted because it's explicitly a *fallback*, not a second source of truth for data
   that's actually live.
2. **Fix what a real run actually broke, then generalize the fix.** Nearly every tool
   (#9), retry policy (#14), FHIR write strategy (#13), and LLM fallback rule (#6) exists
   because a live test produced a specific failure, not because it was anticipated from
   a spec. The corresponding cost is that some gaps (dashboard write endpoints, real
   auth, trend-chart analytics) are still open — they're recorded as open in `context.md`
   and `flow.md` rather than glossed over.
