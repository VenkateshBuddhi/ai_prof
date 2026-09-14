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

# CORS setup: allow local dev, any Vercel preview/production deployments, and custom env origins
_origins_env = os.environ.get("FRONTEND_ORIGIN", "")
_allowed_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]
_default_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "https://ai-prof-eight.vercel.app",
]
for origin in _default_origins:
    if origin not in _allowed_origins:
        _allowed_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/api/health")
async def health():
    from src.database.medplum_client import get_medplum_client
    return {"status": "ok", "ehr_configured": get_medplum_client() is not None}


for r in (catalog, appointments, patients, ops, voice):
    app.include_router(r.router)
