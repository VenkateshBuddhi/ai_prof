# ai_prof

AI-native, multi-tenant healthcare operations and patient-access platform
connecting patients, multi-hospital networks, doctors, administrators, and
external EHR systems through a voice/chat-first intelligent operational layer.

## Repository layout

```text
app.py                    FastAPI entrypoint (Twilio inbound-call + WebSocket media stream)
src/voice/pipeline.py     Voice pipeline: Deepgram STT -> Groq LLM (tool calls) -> Cartesia TTS
src/voice/capabilities.py Capability engine + current in-memory registries (DOCTORS_DB, HOSPITALS_DB, ...)
schemas/                  JSON Schema (draft-07) catalog for every domain entity
                          (conversational state, appointments, questionnaires, EHR, tenancy, ...)
database/                 PostgreSQL 16 database: DDL, seed, compose, and setup guide
                          -> start with database/README.md
supabase/                 Supabase deployment path: migrations, seed, CLI config
                          -> start with supabase/README.md
```

## Quick start

```powershell
uv sync
docker compose -f database/compose.yml up -d
uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

Voice keys (Groq / Deepgram / Cartesia) live in `.env`.

## Documentation

- Database schema, multi-tenant RLS model, booking/sync patterns: [`database/README.md`](database/README.md)
- Supabase setup, auth model and operations: [supabase/README.md](supabase/README.md)
- JSON Schema catalog: [`schemas/`](schemas/)
