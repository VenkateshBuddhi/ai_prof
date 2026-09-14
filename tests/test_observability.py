# tests/test_observability.py — Milestone: observability, metrics, audit
import logging

import pytest

from src import observability as obs
from src.agent.executor import execute_tool


@pytest.fixture(autouse=True)
def _clear_metrics():
    obs._METRICS.clear()
    yield
    obs._METRICS.clear()


def test_correlation_filter_stamps_record():
    obs.bind_correlation("abcdef1234567890")
    rec = logging.LogRecord("n", logging.INFO, __file__, 1, "msg", None, None)
    assert obs.CorrelationFilter().filter(rec) is True
    assert rec.correlation_id == "abcdef12"  # truncated to 8


def test_bind_correlation_default():
    obs.bind_correlation(None)
    assert obs.get_correlation() == "-"


def test_metrics_collected_only_after_start(session, fake_medplum):
    # no start_call yet -> record is a no-op
    obs.record_tool(session.session_id, "search_doctors", True, 5.0)
    assert obs.get_correlation() is not None
    assert obs.pop_call(session.session_id) is None


async def test_executor_records_metrics(session, fake_medplum):
    obs.start_call(session.session_id, "text")
    await execute_tool("search_doctors", {"specialty": "Cardiology"}, session)
    await execute_tool("create_appointment", {"doctor_id": "d"}, session)  # invalid -> failure
    m = obs.pop_call(session.session_id)
    assert m.tool_calls == 2
    assert m.tool_success == 1 and m.tool_failure == 1
    assert m.tools["search_doctors"] == 1


def test_summary_shape():
    m = obs.start_call("sess123", "voice")
    m.record_turn()
    m.record_tool("book", True, 12.0)
    s = m.summary()
    assert s["channel"] == "voice" and s["llm_turns"] == 1 and s["tool_calls"] == 1
    assert "duration_s" in s
    obs.pop_call("sess123")


async def test_write_call_audit_creates_auditevent(fake_medplum, monkeypatch):
    created = {}

    async def fake_audit(*, description, action="E", outcome="0", patient_id=None, organization_id=None):
        created["desc"] = description
        created["patient"] = patient_id
        return "audit1"

    monkeypatch.setattr(fake_medplum, "create_audit_event", fake_audit, raising=False)
    obs.start_call("sessA", "voice")
    obs.record_tool("sessA", "create_appointment", True, 20.0)
    aid = await obs.write_call_audit("sessA", patient_id="patX", organization_id="org1")
    assert aid == "audit1"
    assert "create_appointment" in created["desc"] and created["patient"] == "patX"
    obs.pop_call("sessA")
