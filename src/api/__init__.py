# src/api/
"""FastAPI REST layer over the existing engine (Medplum, observability, workflows,
eval). Adapts FHIR + our operational data into the frontend's DTO shapes
(frontend/src/types/index.ts). Auth is a dev bypass for now (header-based scope);
real Supabase-JWT verification is a planned follow-up.

Run:  uv run uvicorn src.api.main:app --reload --port 8000
"""
