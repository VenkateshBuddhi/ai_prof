# src/observability.py
"""Observability: correlation, per-call metrics, and audit (PRD 5.34–5.36, 5.40).

- **Correlation** (§5.35): a `correlation_id` bound per call/turn and injected into
  every log record by `CorrelationFilter`, so a whole conversation is traceable
  across voice → LLM → tool → EHR.
- **Metrics** (§5.36): a per-call `CallMetrics` collector (tool calls, success/
  failure, per-tool counts, LLM turns, duration). Recorded from the executor so it
  works for every entry point. Only collected when a call is `start`ed, so tests
  and one-off tool calls stay no-ops.
- **Audit** (§5.40): a per-call FHIR `AuditEvent` summarising what the AI did.

No PHI is logged; the audit record references the patient rather than embedding it.
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger("Observability")

# --- correlation --------------------------------------------------------------
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class CorrelationFilter(logging.Filter):
    """Stamps the current correlation id onto every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id.get()
        return True


def bind_correlation(value: Optional[str]) -> None:
    _correlation_id.set((value or "-")[:8])


def get_correlation() -> str:
    return _correlation_id.get()


# --- metrics ------------------------------------------------------------------
@dataclass
class CallMetrics:
    session_id: str
    channel: str = "unknown"           # voice | text | sip
    started: float = field(default_factory=time.monotonic)
    llm_turns: int = 0
    tool_calls: int = 0
    tool_success: int = 0
    tool_failure: int = 0
    tools: Counter = field(default_factory=Counter)

    def record_tool(self, name: str, success: bool, ms: float) -> None:
        self.tool_calls += 1
        self.tools[name] += 1
        if success:
            self.tool_success += 1
        else:
            self.tool_failure += 1

    def record_turn(self) -> None:
        self.llm_turns += 1

    def summary(self) -> dict:
        return {
            "session": self.session_id,
            "channel": self.channel,
            "duration_s": round(time.monotonic() - self.started, 1),
            "llm_turns": self.llm_turns,
            "tool_calls": self.tool_calls,
            "tool_success": self.tool_success,
            "tool_failure": self.tool_failure,
            "tools": dict(self.tools),
        }


_METRICS: Dict[str, CallMetrics] = {}


def start_call(session_id: str, channel: str) -> CallMetrics:
    m = CallMetrics(session_id=session_id, channel=channel)
    _METRICS[session_id] = m
    bind_correlation(session_id)
    return m


def record_tool(session_id: str, name: str, success: bool, ms: float) -> None:
    m = _METRICS.get(session_id)
    if m:
        m.record_tool(name, success, ms)


def record_turn(session_id: str) -> None:
    m = _METRICS.get(session_id)
    if m:
        m.record_turn()


def pop_call(session_id: str) -> Optional[CallMetrics]:
    return _METRICS.pop(session_id, None)


# --- audit --------------------------------------------------------------------
async def write_call_audit(
    session_id: str, *, patient_id: Optional[str] = None,
    organization_id: Optional[str] = None, outcome: str = "0",
) -> Optional[str]:
    """Log the per-call metrics summary and persist it as a FHIR AuditEvent.
    Best-effort — observability must never break a call."""
    metrics = _METRICS.get(session_id)
    summary = metrics.summary() if metrics else {"session": session_id}
    logger.info("call summary: %s", json.dumps(summary, default=str))

    try:
        from src.database.medplum_client import get_medplum_client
        medplum = get_medplum_client()
        if not medplum:
            return None
        return await medplum.create_audit_event(
            description=json.dumps(summary, default=str),
            patient_id=patient_id,
            organization_id=organization_id,
            outcome=outcome,
        )
    except Exception:  # noqa: BLE001
        logger.exception("audit write failed")
        return None
