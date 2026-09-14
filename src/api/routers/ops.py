# src/api/routers/ops.py — hospitals, workflows, audit/AI-activity, eval, KPIs
import json
import os
from datetime import date

from fastapi import APIRouter, Depends

from src.api import adapters
from src.api.deps import Scope, get_scope, require_medplum

router = APIRouter(prefix="/api", tags=["ops"])

_REPORT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))), "eval_report.json")


@router.get("/hospitals")
async def hospitals():
    mp = require_medplum()
    return [adapters.organization_dto(o) for o in await mp.list_organizations()]


@router.get("/workflows")
async def workflows():
    mp = require_medplum()
    return [adapters.task_to_workflow_dto(t) for t in await mp.list_tasks()]


@router.get("/audit")
async def audit():
    mp = require_medplum()
    return [adapters.auditevent_dto(a) for a in await mp.list_audit_events()]


@router.get("/ai-activity")
async def ai_activity():
    # Per-call AuditEvents ARE the AI-activity records.
    mp = require_medplum()
    return [adapters.auditevent_dto(a) for a in await mp.list_audit_events()]


@router.get("/evaluation")
async def evaluation():
    """Latest eval scorecard (from `eval_report.json`, produced by src.eval.runner)."""
    if not os.path.exists(_REPORT):
        return {"available": False, "hint": "run: uv run python -m src.eval.runner --offline --no-judge"}
    with open(_REPORT, "r", encoding="utf-8") as f:
        return json.load(f)


def _pct(num: int, denom: int) -> float:
    # Clamp to 100 — denominators are approximate (e.g. more historical
    # questionnaire responses than currently-booked appointments).
    return round(min(100.0, 100 * num / denom), 1) if denom else 0.0


def _aggregate_audit(events: list) -> dict:
    """Reduce per-call AuditEvent metric summaries (stored as JSON in
    `outcomeDesc`) into rates/averages: avg latency, escalation rate, and
    capability (tool) success rate."""
    durations, escalated, calls = [], 0, 0
    tool_success = tool_failure = 0
    for e in events:
        try:
            s = json.loads(e.get("outcomeDesc") or "{}")
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(s, dict) or "duration_s" not in s:
            continue
        calls += 1
        if isinstance(s.get("duration_s"), (int, float)):
            durations.append(s["duration_s"])
        tool_success += int(s.get("tool_success") or 0)
        tool_failure += int(s.get("tool_failure") or 0)
        if "transfer_to_human" in (s.get("tools") or {}):
            escalated += 1
    return {
        "calls": calls,
        "avg_latency": round(sum(durations) / len(durations), 2) if durations else 0.0,
        "escalation_rate": _pct(escalated, calls),
        "capability_success_rate": _pct(tool_success, tool_success + tool_failure),
    }


@router.get("/kpis")
async def kpis(scope: Scope = Depends(get_scope)):
    mp = require_medplum()

    async def count(resource_type, **params):
        try:
            return await mp.count_resources(resource_type, params)
        except Exception:  # noqa: BLE001
            return 0

    today = date.today().isoformat()

    # Counts (exact, via FHIR _summary=count).
    total_appts = await count("Appointment")
    booked = await count("Appointment", status="booked") + await count("Appointment", status="fulfilled")
    cancelled = await count("Appointment", status="cancelled")
    questionnaire_responses = await count("QuestionnaireResponse")

    # Rates/averages (reduced from recent per-call AuditEvent summaries).
    agg = _aggregate_audit(await mp.list_audit_events(count=200))

    return {
        "total_hospitals": await count("Organization"),
        "active_hospitals": await count("Organization", active="true"),
        "total_doctors": await count("Practitioner"),
        "total_patients": await count("Patient"),
        "appointments_today": await count("Appointment", date=f"ge{today}"),
        "cancelled_appointments": cancelled,
        "ai_calls_today": await count("AuditEvent", date=f"ge{today}"),
        "ai_calls_total": agg["calls"],
        # booked (active) out of all appointments made
        "booking_success_rate": _pct(booked, total_appts),
        # questionnaires completed out of booked visits
        "questionnaire_completion_rate": _pct(questionnaire_responses, booked),
        "human_escalation_rate": agg["escalation_rate"],
        "avg_ai_latency": agg["avg_latency"],
        # Medplum is the EHR, so tool/operation success ≈ EHR integration success
        "ehr_integration_success_rate": agg["capability_success_rate"],
    }
