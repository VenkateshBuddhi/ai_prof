# src/api/main.py — FastAPI app for the dashboard frontend
"""REST API over the existing engine. Dev-bypass auth (header scope).

Run:  uv run uvicorn src.api.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV = os.path.join(_BASE, ".env")


def _load_env() -> None:
    if not os.path.exists(_ENV):
        return
    with open(_ENV, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))


_load_env()
from src.logging_setup import setup_logging  # noqa: E402
setup_logging()

from src.api.routers import appointments, catalog, ops, patients, voice  # noqa: E402

app = FastAPI(title="ai-prof API", version="0.1.0",
              description="REST layer over Medplum + workflows + eval (dev-bypass auth).")

# CORS for the Next.js frontend (comma-separated origins, default localhost:3000).
_origins = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    from src.database.medplum_client import get_medplum_client
    return {"status": "ok", "ehr_configured": get_medplum_client() is not None}


for r in (catalog, appointments, patients, ops, voice):
    app.include_router(r.router)
