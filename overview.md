# Autonomous Multi-Hospital Patient Intake & AI Operations Platform
## System Overview & Technical Blueprint for AI Coding Agents

> **Document Type**: Comprehensive System Blueprint & Agent Developer Guide  
> **Platform Version**: 2.0 (AI-Native, Multi-Tenant, Real-Time Voice & Workflow-Driven)  
> **Target Audience**: AI Coding Assistants (Cline, Cursor, Roo-Code) & Engineering Teams  

---

## 1. Executive Summary & Core Mission

This platform is an **AI-native, multi-tenant healthcare operations and patient-access system** designed to bridge the gap between patients, multi-hospital networks, doctors, administrative staff, and external Electronic Health Record (EHR) systems. 

Rather than acting as a traditional booking website or static chatbot, the platform operates as an **intelligent, event-driven operational layer**. It converts natural language patient requests (via WebRTC real-time streaming voice or telephony) into structured, authorized administrative actions while enforcing strict multi-tenant isolation, ACID-compliant scheduling, external EHR verification, pre-visit questionnaire intake, and asynchronous workflow orchestration.

### Core Product Principle
> *"Hospitals configure the network. Doctors control their schedules. Patients describe what they need naturally. The AI understands and coordinates. Capabilities execute authorized actions. Scheduling engines verify availability. Healthcare integrations perform real-world operations. External outcomes are verified. Platform and external states synchronize. Workflows execute follow-ups. Useful context improves continuity. Operational logging maintains auditability. Humans make clinical decisions."*

---

## 2. Platform Architecture & Production Tech Stack

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND: Next.js 14+ + Tailwind + WebRTC               │
│               (Platform Admin | Hospital Admin | Doctor | Patient)               │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │ (WebSockets / REST)
┌────────────────────────────────────────▼─────────────────────────────────────────┐
│              BACKEND API & AI CAPABILITY GATEWAY: FastAPI (Python 3.12)           │
├────────────────────────────────────────┬─────────────────────────────────────────┤
│ Real-Time Voice: Twilio + Groq STT/LLM │ AI Reasoning: Llama-3.3 / Gemini 1.5   │
│                  + Cartesia TTS        │ Tool Routing & Pydantic Schemas         │
└──────────────────┬─────────────────────┴────────────────────┬────────────────────┘
                   │                                          │
┌──────────────────▼─────────────────────┐  ┌─────────────────▼──────────────────┐
│ IN-MEMORY STORE: Redis (ElastiCache)   │  │ PRIMARY DATABASE: PostgreSQL 16 + RLS│
│ (Active Session State & Redlock Mutex) │  │ (ACID Transactions & JSONB Storage)  │
└────────────────────────────────────────┘  └─────────────────┬────────────────────┘
                                                              │
┌─────────────────────────────────────────────────────────────▼────────────────────┐
│                    WORKFLOW ENGINE: Temporal.io (Async Reminders)                │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │
┌────────────────────────────────────────▼─────────────────────────────────────────┐
│                 EHR INTEGRATION LAYER: FHIR Adapters + Verification              │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Technology Matrix

| Layer | Selected Technology | Purpose & Key Rationale |
| :--- | :--- | :--- |
| **Frontend UI** | **Next.js 14+ (App Router)** + **Tailwind CSS** + **shadcn/ui** | Server-side rendering, role-based route protection, responsive accessibility, and FullCalendar.js schedule management. |
| **Backend Framework** | **FastAPI (Python 3.12)** | Async native (`asyncio`), Pydantic v2 payload validation, automatic OpenAPI spec generation for AI capability schemas. |
| **Real-Time Voice** | **Twilio Voice WebSockets** + **Groq STT** + **Groq LLM** + **Cartesia TTS** | Sub-2-second perceived response latency. Groq Whisper (`whisper-large-v3`) + Groq Llama-3.3 70B (`llama-3.3-70b-versatile`) + Cartesia Sonic (`sonic-english`). |
| **Primary Database** | **PostgreSQL 16+** | Relational core for entities, Row-Level Security (RLS) for tenant isolation, `JSONB` for questionnaires/events, `SELECT FOR UPDATE` locks for double-booking prevention. |
| **In-Memory Cache & State** | **Redis** | Millisecond active session state, distributed `Redlock` mutexes for concurrent slot reservations, event streams. |
| **Interoperability / EHR** | **HL7 FHIR (R4 / US Core)** | Standardized healthcare adapter mapping platform IDs to external EHR IDs with a Mock EHR provider for testing. |
| **Workflow Engine** | **Temporal.io** | Fault-tolerant orchestration of async reminders, EHR sync retries, reconciliation, and human escalations. |
| **Observability & Tracing** | **OpenTelemetry (OTel)** + **ClickHouse / Elasticsearch** | End-to-end trace binding via `correlation_id` across voice turns, LLM calls, DB queries, EHR calls, and workflow steps. |

---

## 3. Real-Time Streaming Voice Pipeline Architecture

The voice pipeline is engineered as an asynchronous, bi-directional streaming loop designed for **sub-2-second perceived response latency**, native turn-taking, interruption handling (barge-in), and natural audio fillers.

### Pipeline Streaming Flow
```
Patient (Phone / Web) 
   │
   ▼ (audio/x-mulaw @ 8kHz)
Twilio Voice Media Stream (WebSocket)
   │
   ▼
Audio Converter & Resampler (8kHz mu-law <-> 16kHz PCM)
   │
   ▼
Voice Activity Detection (VAD / Silence Detection)
   │
   ▼
Groq STT (Whisper Large v3 Fast Audio API)
   │
   ▼ (Text Transcript)
Groq LLM Agent (Llama-3.3-70b-versatile + Pydantic Capability Tools)
   │
   ├─► [If Tool Execution > 500ms] ──► Synthesize Audio Filler ("Checking Dr. Sharma's calendar...")
   │
   ▼ (Streaming Text Response)
Cartesia TTS (Sonic WebSocket Streaming API)
   │
   ▼ (PCM -> 8kHz mu-law Base64)
Twilio Voice Media Stream -> Patient Playback Queue
```

### Key Conversational & Technical Capabilities
1. **Interruption & Barge-In**: When VAD detects user speech while Cartesia audio is playing, the pipeline immediately cancels the active Cartesia TTS socket and emits `{"event": "clear", "streamSid": streamSid}` to flush Twilio's audio playback queue.
2. **Latency Mitigation**: Operations taking longer than 500ms (e.g., EHR lookups) trigger an immediate, non-blocking synthetic filler phrase to eliminate dead silence.
3. **Telephony Integration**: Inbound PSTN calls land on `/voice/incoming`, returning TwiML that establishes a WebSocket media stream.

---

## 4. State Management & Data Separation

To enforce security, performance, and tenant isolation, the agent separates operational data into six distinct states:

1. **Transactional State** *(PostgreSQL)*: Authoritative healthcare records (`Appointment Status`: `Requested`, `Pending`, `Confirmed`, `Rescheduled`, `Cancelled`, `Completed`, `No-show`, `Failed`, `Synchronization Pending`, `Reconciliation Required`).
2. **Conversational State** *(Redis)*: Short-term active turn parameters (`session_id`, `patient_id`, `intent`, `specialty`, `date`, `time_preference`, `selected_doctor_id`, `selected_hospital_id`, `selected_slot_id`).
3. **User Context** *(Redis / PostgreSQL)*:
   - *Short-Term Context*: Active interaction history and recent turns.
   - *Longer-Term Context*: Non-sensitive user preferences (preferred hospital, preferred doctors, communication channels, preferred timing windows).
4. **Workflow State** *(Temporal.io)*: Execution tracking for asynchronous tasks (`Reminder Workflow`: `Scheduled`, `Executing`, `Completed`).
5. **Integration State** *(PostgreSQL)*: Health, mappings, and external verification records (`EHR Integration`: `EHR_VERIFIED`, `UNVERIFIED`, `VERIFICATION_FAILED`).
6. **Operational State** *(ClickHouse / OpenTelemetry)*: Metrics, traces, capability execution logs, and AI evaluation metrics.

---

## 5. Core Entities & Data Schemas

### A. Conversational State Schema (JSON Schema)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ConversationalState",
  "type": "object",
  "properties": {
    "session_id": { "type": "string", "format": "uuid" },
    "patient_id": { "type": ["string", "null"], "format": "uuid" },
    "intent": {
      "type": "string",
      "enum": ["BOOK_APPOINTMENT", "RESCHEDULE", "CANCEL", "COMPLETE_QUESTIONNAIRE", "GENERAL_INQUIRY"]
    },
    "specialty": { "type": ["string", "null"] },
    "date": { "type": ["string", "null"], "format": "date" },
    "time_preference": { "type": ["string", "null"], "enum": ["Morning", "Afternoon", "Evening", null] },
    "selected_hospital_id": { "type": ["string", "null"], "format": "uuid" },
    "selected_doctor_id": { "type": ["string", "null"], "format": "uuid" },
    "selected_slot_id": { "type": ["string", "null"], "format": "uuid" },
    "appointment_status": { "type": "string", "enum": ["Pending", "Confirmed", "Cancelled", "Escalated", "Failed"] }
  },
  "required": ["session_id", "intent", "appointment_status"]
}
```

### B. Appointment Entity Schema (PostgreSQL)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Appointment",
  "type": "object",
  "properties": {
    "appointment_id": { "type": "string", "format": "uuid" },
    "external_appointment_id": { "type": ["string", "null"] },
    "patient_id": { "type": "string", "format": "uuid" },
    "hospital_id": { "type": "string", "format": "uuid" },
    "doctor_id": { "type": "string", "format": "uuid" },
    "calendar_slot_id": { "type": "string", "format": "uuid" },
    "appointment_type": { "type": "string" },
    "start_time": { "type": "string", "format": "date-time" },
    "end_time": { "type": "string", "format": "date-time" },
    "status": {
      "type": "string",
      "enum": [
        "Requested", "Pending", "Confirmed", "Rescheduled", "Cancelled",
        "Completed", "No-show", "Failed", "Synchronization Pending", "Reconciliation Required"
      ]
    },
    "verification_status": {
      "type": "string",
      "enum": ["UNVERIFIED", "EHR_VERIFIED", "VERIFICATION_FAILED"]
    },
    "idempotency_key": { "type": "string" },
    "created_at": { "type": "string", "format": "date-time" }
  },
  "required": ["appointment_id", "patient_id", "hospital_id", "doctor_id", "calendar_slot_id", "start_time", "status", "verification_status"]
}
```

### C. Doctor-Configured Pre-Visit Questionnaire Schema
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "QuestionnaireDefinition",
  "type": "object",
  "properties": {
    "questionnaire_id": { "type": "string", "format": "uuid" },
    "doctor_id": { "type": "string", "format": "uuid" },
    "title": { "type": "string" },
    "specialty": { "type": "string" },
    "version": { "type": "integer" },
    "questions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "question_id": { "type": "string" },
          "prompt_text": { "type": "string" },
          "response_type": {
            "type": "string",
            "enum": ["Yes/No", "Multiple Choice", "Single Choice", "Numeric", "Date", "Short Text", "Long Text"]
          },
          "options": { "type": "array", "items": { "type": "string" } },
          "is_required": { "type": "boolean" }
        },
        "required": ["question_id", "prompt_text", "response_type"]
      }
    }
  },
  "required": ["questionnaire_id", "doctor_id", "title", "questions"]
}
```

### D. AI Agent Capability Tool Payloads
- **`check_availability`**: `{ "doctor_id": "uuid", "date": "YYYY-MM-DD", "time_range": { "start_time": "HH:MM", "end_time": "HH:MM" }, "appointment_type": "string" }`
- **`create_appointment`**: `{ "patient_id": "uuid", "doctor_id": "uuid", "hospital_id": "uuid", "slot_id": "uuid", "appointment_type": "string", "idempotency_key": "string" }`
- **`reschedule_appointment`**: `{ "appointment_id": "uuid", "new_slot_id": "uuid", "idempotency_key": "string" }`
- **`cancel_appointment`**: `{ "appointment_id": "uuid", "reason": "string" }`
- **`submit_questionnaire_response`**: `{ "appointment_id": "uuid", "answers": [{ "question_id": "string", "raw_patient_input": "string", "structured_value": "any" }] }`
- **`transfer_to_human`**: `{ "call_sid": "string", "reason": "string", "context_summary": "string" }`

---

## 6. EHR Integration, Verification & Recovery Architecture

```
AI Agent -> Capability Layer -> Scheduling Service -> EHR Integration Layer -> Adapter/Connector -> External EHR
                                                                                               │
                                                                                               ▼
Platform State Sync <─ External State Verification <─ Receive External Identifier <─────────────┘
```

1. **Identifier Mapping Engine**: Maintains bidirectional mappings (`internal_patient_id` $\leftrightarrow$ `external_patient_id`, `internal_appointment_id` $\leftrightarrow$ `external_appointment_id`).
2. **Two-Phase Verification Rule**: The platform **NEVER** communicates a confirmed booking to a patient until the external EHR record is verified (`verification_status = EHR_VERIFIED`).
3. **Failure Classification & Recovery**:
   - *Retryable Errors* (network timeouts, transient HTTP 5xx): Exponential backoff retry via Temporal.
   - *Non-Retryable Errors* (invalid mapping, provider inactive): Immediately flag for human escalation.
4. **Reconciliation Engine**: When an integration call returns an unknown outcome, the system queries the external EHR for a matching record before retrying to prevent duplicate bookings.

---

## 7. Clinical Safety, Guardrails & Privacy Rules

1. **No Autonomous Clinical Decisions**: The AI operates strictly as an administrative assistant. It is strictly forbidden from diagnosing diseases, prescribing medication, modifying drug regimens, or issuing clinical opinions.
2. **Patient-Reported Data Standard**: All symptoms gathered conversationally are tagged as **patient-reported information** ("Patient reported lower back pain for 2 weeks") rather than medical evaluations.
3. **Privacy-Aware Logging**: Under no circumstances are raw PHI audio streams or plain-text transcripts written to persistent log files. All logging relies on structured operational events (`CALL_STARTED`, `STT_SUCCESS`, `TOOL_EXECUTED`, `EHR_SYNC_VERIFIED`).
4. **Tenant Isolation**: Database Row-Level Security (RLS) ensures Hospital A staff/doctors can never query Hospital B data.

---

## 8. Complete Codebase Directory Layout

```
platform_root/
├── apps/
│   ├── web/                        # Next.js 14+ Frontend Application
│   │   ├── app/                    # App Router Pages (admin, hospital, doctor, patient)
│   │   ├── components/             # UI Components (shadcn/ui, FullCalendar, WebRTC voice client)
│   │   └── lib/                    # API clients, hooks, and WebRTC streaming logic
│   │
│   └── voice_service/              # FastAPI Real-Time Voice & AI Pipeline Service
│       ├── app/
│       │   ├── main.py             # FastAPI entry point & WebSocket routes
│       │   ├── config.py           # Pydantic Settings (Groq, Cartesia, Twilio, Redis)
│       │   ├── api/                # TwiML handlers & health checks
│       │   ├── websocket/          # Twilio stream handler, connection manager, buffer manager
│       │   ├── audio/              # Codecs (mu-law <-> PCM), resampler (8kHz <-> 16kHz), VAD
│       │   ├── services/           # Groq STT client, Groq LLM client, Cartesia TTS client, audio fillers
│       │   ├── agent/              # System prompts, tools (Pydantic), tool executor, context resolver
│       │   ├── state/              # Redis session store & user context manager
│       │   └── utils/              # Privacy-aware logger & OpenTelemetry tracer
│       ├── Dockerfile
│       └── requirements.txt
│
├── packages/
│   ├── db/                         # PostgreSQL DDL, Prisma/SQLAlchemy schemas, RLS policies
│   ├── ehr_adapters/               # FHIR R4 integration adapters & Mock EHR connector
│   └── workflows/                  # Temporal.io async background workflows & reminders
│
├── docker-compose.yml              # Local development stack (PostgreSQL, Redis, Temporal, Voice Service)
├── README.md                       # Local setup & ngrok developer guide
└── OVERVIEW.md                     # System blueprint & coding agent context
```

---

## 9. End-to-End Implementation Milestones

### Phase 1: Multi-Tenant Database & Core Scheduling Engine
- [x] PostgreSQL schema setup with Row-Level Security (RLS).
- [x] Hospital onboarding workflow (`Draft` $\rightarrow$ `Submitted` $\rightarrow$ `Approved`).
- [x] Doctor calendar slot engine with row locking (`SELECT FOR UPDATE`) to prevent double-booking.

### Phase 2: AI Capabilities & Context Engine
- [x] Pydantic tool schemas for scheduling and intake.
- [x] Active interaction session management in Redis.
- [x] Clinical safety guardrail prompts and deictic context resolution.

### Phase 3: Real-Time Streaming Voice Pipeline
- [x] Twilio Voice Media Streams WebSocket server.
- [x] Groq STT + Groq LLM + Cartesia TTS integration.
- [x] VAD barge-in audio buffer flushing and synthetic filler phrases.

### Phase 4: EHR Integration & Verification
- [x] FHIR R4 Mock EHR connector factory.
- [x] Bidirectional ID mapping (`internal_id` $\leftrightarrow$ `external_id`).
- [x] External verification and reconciliation state machine.

### Phase 5: Pre-Visit Intake & Async Workflows
- [x] Doctor-configured pre-visit questionnaire engine.
- [x] Conversational intake flow over voice/chat.
- [x] Temporal.io async workflows for reminders and EHR retry backoff.

### Phase 6: Multi-Role Dashboards & Observability
- [x] Platform Admin, Hospital Admin, Doctor, and Patient dashboards.
- [x] OpenTelemetry end-to-end tracing with `correlation_id`.
- [x] Privacy-aware structured event auditing and automated AI quality benchmarks.

---

## 10. Prototype Definition of Done

The system build is complete when the following journey executes end-to-end without errors:

$$\text{Patient Voice Request} \rightarrow \text{Intent/Context Resolution} \rightarrow \text{Hospital/Doctor Discovery} \rightarrow \text{Real Availability Check}$$
$$\rightarrow \text{Booking Capability} \rightarrow \text{EHR Integration Adapter} \rightarrow \text{External State Verification} \rightarrow \text{Pre-Visit Intake}$$
$$\rightarrow \text{Doctor Dashboard Review} \rightarrow \text{Async Reminders} \rightarrow \text{Privacy-Aware Audit Trail}$$
