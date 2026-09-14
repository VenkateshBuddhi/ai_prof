# flow.md — how the application actually works, end to end

Numbered, file-and-function-level walkthroughs of every major flow in the system. Read
`context.md` first if you haven't already — it explains the three layers (voice / brain
/ engine) this document assumes. See `decisions.md` for *why* each piece works this way.

---

## 1. Voice call over the phone (PSTN)

```
Caller's phone
  │  dials the Twilio number
  ▼
Twilio  (SIP trunk only — see twilio.md)
  │  SIP INVITE to the LiveKit SIP host
  ▼
LiveKit SIP → inbound trunk (src/voice/livekit_sip_setup.py provisioned this)
  │  matches the trunk by dialed number, applies the dispatch rule
  ▼
LiveKit room created (call-<id>) + agent "healthcare-intake" dispatched into it
  │
  ▼
src/voice/livekit_worker.py: entrypoint(ctx)
```

1. `entrypoint()` calls `ctx.connect()`, then `ctx.wait_for_participant()` — this blocks
   until the SIP participant (the caller) joins the room.
2. `_extract_caller_number(participant)` reads `participant.attributes["sip.phoneNumber"]`
   — the caller's number, provided by LiveKit's SIP integration. (On a mock/console
   participant this returns `None` safely — see the hardening added after a `MagicMock`
   crash during local testing.)
3. `_resolve_context(phone, medplum)` calls `MedplumClient.find_patient_by_phone(phone)`.
   - If found: `PersistentUserContext` is populated with `fhir_patient_id`,
     `fhir_organization_id`, `first_name`, `last_name` — this patient's tenant
     compartment is now fixed for the rest of the call.
   - If not found (or Medplum is unreachable): the context stays unidentified,
     **fail-open** — the call proceeds; the agent will resolve identity later, likely via
     `lookup_patient`/`register_patient`, or the caller remains anonymous for a
     general inquiry.
4. `ConversationAgent(session=AgentStateSession(context=context))` is constructed — this
   builds the LangGraph brain (see §5 below for what happens inside).
   `observability.start_call(session_id, channel="voice")` begins per-call metrics
   collection.
5. `brain.start_with_context()` produces the opening line — "Hi {first_name}, this is
   the clinic's scheduling assistant..." if identified, a generic greeting otherwise. No
   LLM call happens for the greeting itself; it's templated in `agent.py`'s `_greeting()`.
6. `AgentSession` (LiveKit's, not ours — see `context.md`'s naming-collision note) is
   started with Deepgram STT, Silero VAD (loaded once per worker process in `prewarm()`,
   not per call), and Cartesia TTS.
7. The worker speaks the greeting (`session.say(greeting, allow_interruptions=True)`) —
   barge-in is enabled from the first word.
8. **Per turn**, LiveKit's session handles voice-activity-detection and turn-endpointing
   internally, then calls `HealthcareIntakeAgent.llm_node(chat_ctx, tools, model_settings)`
   with the finished transcript:
   - The latest user utterance is pulled from `chat_ctx.items`.
   - A `_BridgeLLM`-satisfied response step means this method actually runs (see
     `decisions.md` #7 for why that's not automatic).
   - `self._brain.send(user_text)` is awaited as a background task; if it takes longer
     than `FILLER_AFTER_SECONDS` (env-configurable, default off in the working config —
     see `decisions.md` #11), a short filler line is spoken while it's still running.
   - The reply text is `yield`ed back to LiveKit, which synthesizes and streams it via
     Cartesia.
   - Every tool call the brain made this turn is logged (`tool <name> -> success=<bool>`)
     and inspected for two special signals: a successful `transfer_to_human` sets
     `pending_transfer`; a successful `end_call` sets `pending_hangup`.
9. `session.on("agent_state_changed")`: when the agent transitions out of `"speaking"`
   (i.e. it just finished talking), the worker checks those flags:
   - `pending_transfer` → `ctx.transfer_sip_participant(participant, ESCALATION_TRANSFER_TO)`
     — a real SIP transfer, moving the caller to a human line.
   - `pending_hangup` → `ctx.delete_room()` — ends the call.
   - Both are genuine no-ops in `console` mode (no real SIP leg exists), by design.
10. `session.on("conversation_item_added")` accumulates every user/assistant text line
    into an in-memory `transcript` list (skips non-message items like `AgentHandoff`).
11. On room shutdown (`ctx.add_shutdown_callback`):
    - If a patient was identified and the transcript is non-empty, the whole
      conversation is written to Medplum as a `Communication` resource
      (`_format_transcript` → `MedplumClient.create_communication`).
    - `observability.write_call_audit(session_id, patient_id, organization_id)` logs the
      accumulated `CallMetrics` summary and persists it as a FHIR `AuditEvent`.
    - The in-memory metrics for this call are popped/discarded.

**What's inside step 8's `self._brain.send(user_text)` — see §5, "one conversational
turn through the brain," which is identical regardless of whether the caller is on a
phone, in a browser, or typing into `chat.py`.**

---

## 2. Voice call over the browser (patient dashboard's AI Assistant)

The same worker and brain as §1; only how the call gets *started* differs.

```
Browser: frontend/src/app/patient/assistant/page.tsx
  │  user clicks "Start call"
  ▼
POST /api/voice/token  (src/api/routers/voice.py)
```

1. The frontend calls `apiPost("/api/voice/token", { name: "Patient" })`.
2. The API mints a LiveKit access token (`livekit.api.AccessToken`, scoped to a fresh
   room name like `web-<random>`) **and** calls
   `lkapi.agent_dispatch.create_dispatch(CreateAgentDispatchRequest(agent_name=
   "healthcare-intake", room=room))` — explicitly telling LiveKit to send the
   `healthcare-intake` worker into that specific room (this is necessary because a
   browser room has no SIP dispatch rule to trigger it automatically). Dispatch failure
   is logged but non-fatal — the room still opens.
3. The frontend receives `{url, token, room}` and does
   `new Room().connect(url, token)` (via `livekit-client`), then
   `localParticipant.setMicrophoneEnabled(true)`.
4. LiveKit routes a job to the dispatched worker exactly as in §1 from
   `entrypoint(ctx)` onward — except `wait_for_participant()` resolves to the browser's
   participant, which has **no `sip.phoneNumber` attribute**, so
   `_extract_caller_number` returns `None` and the caller starts unidentified. (This is
   why the assistant page's greeting is generic, and why a first-time browser caller is
   walked through `lookup_patient` → `register_patient` if they want to book.)
5. Audio flows both ways over WebRTC: the browser's mic track is subscribed by the
   worker (Deepgram transcribes it); the worker's synthesized TTS track is subscribed by
   the browser (`RoomEvent.TrackSubscribed` → `track.attach()` → an `<audio>` element).
6. `RoomEvent.TranscriptionReceived` segments (both the caller's and the agent's) are
   rendered live in the page's transcript panel, keyed by segment id so interim/partial
   text is replaced in place as it finalizes.
7. Ending: the page's "End" button calls `room.disconnect()`; the agent's own `end_call`
   flow (§1 step 9) can also end things from the other side.

---

## 3. Text-mode conversation (no voice at all) — `chat.py` / `smoke_test.py`

Used for development and debugging, not by end users.

- **`uv run python -m src.agent.chat`**: builds a `ConversationAgent` directly (no
  worker, no LiveKit). `agent.start(phone_number=...)` does the same
  `find_patient_by_phone` lookup as §1 step 3, then drops into a `while True: input()`
  loop calling `agent.send(text)` — identical brain, identical tool execution, just
  typed instead of spoken. `--show-tools` prints each tool call's success/failure inline.
- **`uv run python -m src.agent.smoke_test`**: doesn't touch the LLM or LangGraph at
  all — it calls `execute_tool(name, args, session)` directly for a scripted sequence
  (search → check availability → book → questionnaire → reschedule → cancel →
  escalate), asserting on each result. This is the fastest way to verify the
  tool/Medplum layer is wired correctly without spending any LLM tokens.

---

## 4. One conversational turn through the brain (`ConversationAgent.send`)

This is the core loop, identical for phone, browser, and text-mode callers.

```
agent.send(user_text)
  │
  ▼
observability.bind_correlation(session_id) + record_turn(session_id)
  │
  ▼
self.messages.append(HumanMessage(user_text))
  │
  ▼
self._graph.ainvoke({"messages": self.messages})   ← the LangGraph StateGraph
```

Inside the graph (`src/agent/graph.py`, compiled once per `ConversationAgent`):

1. **`agent` node**: the current message history is sent to the LLM
   (`llm_with_tools.ainvoke(...)`), where `llm_with_tools` is a Gemini-primary,
   Groq-fallback chain (`gemini_chat_model.with_fallbacks([groq_chat_model])`) with all
   12 tools bound via `bind_tools`. If Gemini errors (quota, retired model, network), the
   *same request* transparently retries on Groq — the graph doesn't know or care which
   provider actually answered.
2. The LLM's response either contains **no tool calls** (a plain reply — go straight to
   `END`) or **one or more tool calls** (go to the `tools` node).
3. **`tools` node**: for each requested tool call, `execute_tool(name, args, session)`
   (`src/agent/executor.py`) runs:
   - The raw LLM-provided `args` dict is validated against that tool's Pydantic model
     from `schemas.py`. A validation failure is returned to the model as
     `{"success": false, "error": "invalid_arguments", "details": [...]}`  — **not**
     raised — so the model can see what it got wrong and retry with corrected
     arguments on its next turn.
   - The matching capability function in `capabilities.py` runs, calling into
     `MedplumClient` (see §6/§7 below for what each tool actually does).
   - The result and timing are recorded via `observability.record_tool(...)`.
   - The result is wrapped as a `ToolMessage` and appended to the graph's message list.
4. Control returns to the **`agent` node** with the tool results now in context — the
   LLM sees what happened and either calls more tools (e.g. `check_availability` after
   `search_doctors`) or produces its next reply to the caller.
5. This loop continues until the LLM replies with no further tool calls, then the graph
   reaches `END` and `ainvoke` returns the final message list.

Back in `ConversationAgent.send()`:
- The last `AIMessage`'s content is extracted (normalizing Gemini's occasional
  list-of-blocks content shape into plain text) and returned as the reply.
- `self.last_tool_calls` is populated (used by the worker for the
  transfer/hangup/logging signals in §1 step 8, and by the eval harness in §9).
- If `ainvoke` itself raises (a genuine failure of *both* LLM providers, or an
  unrecoverable graph error), a hardcoded safe fallback line is returned instead of
  propagating the exception — this is the "healthcare error boundary": a broken
  turn must never crash the call.

---

## 5. Booking a new appointment — the tool sequence in practice

A concrete instance of §4, showing which tools typically fire in what order for "I have
chest pain, I need a cardiologist":

1. **`search_doctors(specialty="Cardiology")`** → `MedplumClient.search_practitioners`:
   FHIR search on `PractitionerRole` filtered by `specialty:text` and (if the caller is
   identified) `organization=` for tenant isolation, `_include`-ing the linked
   `Practitioner` and `Location`. Returns doctor id, name, specialty, hospital name/id.
   (Symptom→specialty mapping — "chest pain" → Cardiology — happens in the LLM's own
   reasoning per the system prompt's guardrails, not in this tool.)
2. **`check_availability(doctor_id, date=...)`** → `MedplumClient.get_available_slots`:
   searches `Slot?schedule.actor=Practitioner/<id>&status=free`, `_include`-ing the
   `Schedule` to resolve the `Location`. Returns real, bookable slot ids and human-
   readable times — the model is instructed never to invent a time.
3. The model presents 2–3 options and waits for the caller to pick one — the system
   prompt explicitly requires confirming the slot before booking, never auto-selecting.
4. If the caller isn't yet identified: **`lookup_patient(phone?)`** →
   `find_patient_by_phone`; if that returns `found: false`, the model collects name +
   DOB and calls **`register_patient`** → `MedplumClient.create_patient` (conditional
   FHIR create, deduped on phone-or-name+DOB — see `decisions.md` #10). The returned
   `patient_id` is stored on `session.context.fhir_patient_id` for the rest of the call.
5. **`create_appointment(doctor_id, hospital_id, slot_id)`** →
   `MedplumClient.create_appointment`:
   - Reads the target `Slot`; refuses if it's already `busy`.
   - `POST`s a new `Appointment` (`status: booked`) with a conditional-create
     `If-None-Exist` keyed on a deterministic `patient_id-slot_id` identifier — a retry
     of the same booking (e.g. the model re-calling the tool) returns the existing
     appointment instead of double-booking.
   - Flips the `Slot`'s status to `busy`.
   - Because Medplum **is** the system of record here (not an external EHR being
     synced to), a successfully created `booked` Appointment **is** the verification —
     the capability returns `verification_status: "EHR_VERIFIED"` directly, no separate
     confirmation round-trip. The system prompt enforces a "two-phase rule": never tell
     the caller they're confirmed until this field says so.
   - On success, `src/workflows/engine.on_appointment_booked(...)` fires (best-effort,
     failure here never fails the booking itself) — see §8.
6. The model speaks the confirmation and, per the prompt, immediately moves into the
   pre-visit questionnaire (§6) rather than waiting to be asked.

---

## 6. Pre-visit questionnaire

1. **`get_questionnaire(doctor_id)`** → `MedplumClient.get_questionnaire`: resolves the
   doctor's specialty via their `PractitionerRole`, then searches active `Questionnaire`
   resources whose title/`useContext` names that specialty. Each FHIR `item` (with its
   `type` — boolean, string, choice, etc.) is mapped to a friendlier
   `{question_id, prompt_text, response_type, options, is_required}` shape via
   `_map_question_item`. `session.state.questionnaire_ref` is stored for the submit
   step.
2. The model asks each question **one at a time**, in plain language — this is an
   explicit prompt instruction, not a UI/tool constraint; the model could technically
   ask several at once, but is told not to.
3. Once all answers are collected, **`submit_questionnaire_response(appointment_id,
   answers)`** → `MedplumClient.save_questionnaire_response`: resolves the patient from
   the `Appointment`, then `POST`s one `QuestionnaireResponse` resource with all answers
   as `item`s, linked back to the `Appointment` via an extension.
4. The model then either continues the conversation or, if nothing else is needed,
   speaks a closing line and calls `end_call` (see §1 step 9 for what happens next).

---

## 7. Rescheduling, cancelling, and escalation

- **Reschedule/cancel an *existing* appointment** (one not just booked this call): the
  prompt requires calling **`get_appointment(status="booked")`** first —
  `MedplumClient.get_appointments` searches `Appointment?patient=<id>&status=booked`,
  `_include`-ing participants to resolve doctor names. If more than one comes back, the
  model must ask which one before calling `reschedule_appointment`/`cancel_appointment` —
  this closes a specific gap where the model previously had no way to reference a prior
  booking and would either hallucinate an id or refuse.
  - `reschedule_appointment`: read-modify-`PUT`s the `Appointment` (new slot/start/end,
    status back to `booked`), frees the old `Slot`, marks the new one `busy`.
  - `cancel_appointment`: sets `Appointment.status = "cancelled"` (+ a reason if given),
    frees the `Slot`.
- **Escalation** (`transfer_to_human`): fires when the caller explicitly asks for a
  person, or the model determines it can't help (repeated tool failures, a request
  outside its allowed scope, an emergency it can't handle — the system prompt separately
  requires deflecting anything resembling "am I having a heart attack" to calling 911
  *before* any scheduling talk). Sets `session.state.appointment_status = "Escalated"`;
  the actual SIP transfer happens per §1 step 9.

---

## 8. Background workflows (reminders/notifications)

Runs continuously, independent of any single call — `uv run python -m
src.workflows.runner` (a separate long-lived process from the voice worker).

1. **On booking** (triggered inline from §5 step 5, best-effort): `on_appointment_booked`
   immediately calls `notifications.notify(...)`, which writes a `Communication`
   resource under the patient's compartment (the "record" channel, always on) and
   optionally sends a Twilio SMS if `NOTIFY_CHANNELS` includes `sms` and credentials are
   configured. It then calls `MedplumClient.create_task(...)` to enqueue a
   `Task(code="appointment-reminder", status="requested", executionPeriod.start=<due
   time>)`, where the due time is `REMINDER_LEAD_MINUTES` before the appointment (or ~1
   minute out, for demo purposes, if that would already be in the past).
2. **The runner's poll loop** (`process_due_tasks`, called every `WORKFLOW_POLL_SECONDS`):
   fetches all `Task`s with `status="requested"` (`list_open_tasks`), filters to those
   whose due time has passed, and for each due one calls `notifications.notify(...)`
   again with the Task's stored reminder text, then marks it `completed` via
   `set_task_status`. A task that fails to execute is left `requested` so the next poll
   retries it — there's no separate dead-letter/max-attempts handling yet.

---

## 9. AI evaluation run (`src/eval`)

Two independent ways to produce the same PRD §22 scorecard.

**Offline** (`uv run python -m src.eval.runner --offline --no-judge`, no credentials
needed): for each bundled fixture (`src/eval/fixtures/*.json` — a pre-recorded
`turns`/`assistant_texts`/`tool_calls`/`state` capture), the identical deterministic
`checks.run_all_checks(scenario, state, tool_calls, assistant_texts)` used by the live
path scores it: intent match, capability selection/success, tool-argument provenance
(did every booking-mutating call use an id that actually came from an earlier tool
result?), booking verification, final status, and rule-based safety (forbidden-diagnosis
language absent; required deflection/escalation language present where the scenario
calls for it).

**Live** (`uv run python -m src.eval.runner`, needs Gemini/Groq + Medplum): for each
`EvalScenario` in `scenarios.py` (book, symptom→specialty mapping, cancel, ambiguous
clarification, diagnosis-refusal, explicit escalation, register-new-patient), a fresh
`ConversationAgent` is built and driven through the scripted `turns` exactly like
`chat.py` would, timing each `send()` call for latency. The same `run_all_checks` scores
the real transcript/tool-calls/final-state that resulted. If `--no-judge` isn't passed,
`judge.judge_scenario(...)` additionally asks a `ChatGroq` model to rate response
correctness, clarification quality, and safety compliance on a 0–1 rubric per scenario.

Both paths converge on `build_scorecard(results)`, which aggregates pass/fail rates per
check category into the PRD §22 metrics (intent accuracy %, capability selection %,
booking verification %, safety compliance %, average response time) — printed as a
console table and written to `eval_report.json`, which `/api/evaluation` (§11) later
serves to the dashboard as-is.

---

## 10. Test suite (fully offline)

`uv run pytest` runs ~73+ tests with **no network calls at all**. The mechanism:
`tests/conftest.py` defines `FakeMedplum`, a class implementing every method the real
`MedplumClient` exposes (search, create, patch, list, count — see `decisions.md` #12),
and a `fake_medplum` fixture that injects it via
`src.database.medplum_client._CLIENT = fake; _CLIENT_RESOLVED = True` — the exact same
module-level cache slot `get_medplum_client()` reads from in production. Every test file
targets one milestone/component (schemas, tool-registry parity, the executor, the 12
capabilities, Medplum's pure helper functions, the retry/backoff logic with a mocked
`httpx`, the workflow engine, observability, the eval checks, and the FastAPI routes via
`TestClient`) and exercises real production code paths against fake data.

---

## 11. Dashboard read: a page loading real data

```
Browser: any wired page, e.g. frontend/src/app/admin/page.tsx
  │  React renders, calls useKpis() (frontend/src/lib/queries.ts)
  ▼
react-query useQuery(["kpis"], () => apiGet("/api/kpis"))
  │  GET, via the axios instance in src/lib/api.ts (baseURL = NEXT_PUBLIC_API_URL,
  │  header X-Role: platform_admin — the current dev-bypass identity, see decisions.md #20)
  ▼
FastAPI: src/api/routers/ops.py -> kpis(scope: Scope = Depends(get_scope))
```

1. `get_scope()` reads the `X-Role`/`X-Organization`/etc. headers (defaults to
   `platform_admin` if absent) and returns a `Scope` object — no verification of the
   caller's identity happens (this is the explicitly-flagged dev bypass).
2. `require_medplum()` fetches the cached `MedplumClient`; if none is configured, every
   endpoint returns `503` rather than crashing.
3. For KPIs specifically: exact counts come from FHIR `_summary=count` queries
   (`Organization`, `Practitioner`, `Patient`, `Appointment` filtered by status/date);
   rate/average metrics come from `_aggregate_audit()`, which fetches the most recent
   `AuditEvent`s, parses each one's `outcomeDesc` JSON (the same `CallMetrics` summary
   written in §1 step 11 / §4), and reduces them into average latency, escalation rate,
   and capability success rate — all values clamped to 100% since denominators (e.g.
   lifetime questionnaire count vs. currently-booked appointments) aren't perfectly
   aligned.
4. For other endpoints, `src/api/adapters.py` maps the raw FHIR resource (or the
   `MedplumClient`'s already-friendlier search-result dicts, for doctors/slots) into the
   exact TypeScript shape `frontend/src/types/index.ts` expects — e.g.
   `appointment_dto()` pulls the patient/doctor/location names out of a FHIR
   `Appointment`'s `participant` list plus the `_include`d resources.
5. The JSON response flows back through react-query; `useLive()`
   (`frontend/src/lib/queries.ts`) marks the result `isLive: true` and the page renders
   real data with a green "Live API" badge (`live-badge.tsx`). If the request fails for
   any reason (backend down, `503`, network error), `useLive()` falls back to
   an empty state (`[]` or `{}`) rather than fake data, preventing confusing mix-ups of real and mock records. It then shows an amber "Mock Data" or "Error" badge.

**Which pages are actually wired this way today:** Every dashboard page (Admin, Hospital, Doctor, Patient) is fully wired to live Medplum data via `src/api`. Only a handful of pure UI components (like the Admin Trend Charts, Questionnaires list, and EHR Integrations) still render static data because their corresponding backend endpoints do not exist yet. These components are explicitly badged with a hardcoded `<LiveBadge live={false} />` to distinguish them from live tables.

---

## 12. Dashboard write: booking an appointment from the API directly

(Distinct from §5, which is the *voice agent* booking a slot on the caller's behalf —
this is the same underlying engine, reachable directly over HTTP, e.g. for a future
admin "book on behalf of a patient" UI.)

`POST /api/appointments` (`src/api/routers/appointments.py`) with
`{patient_id, doctor_id, hospital_id, slot_id}` calls the identical
`MedplumClient.create_appointment` used in §5 step 5, then also fires
`workflows.engine.on_appointment_booked(...)` (§8 step 1) so the confirmation/reminder
behavior is consistent regardless of whether the booking came from a phone call, a
browser voice call, or a direct API request. Reschedule/cancel/questionnaire-submit
endpoints follow the same pattern — thin HTTP wrappers over the exact same
`MedplumClient` methods the agent's tools call.
