# tests/test_executor.py — Milestone: validated dispatch layer
from src.agent.executor import execute_tool


async def test_unknown_tool(session, fake_medplum):
    r = await execute_tool("does_not_exist", {}, session)
    assert r == {"success": False, "error": "unknown_tool:does_not_exist"}


async def test_invalid_arguments_returned_not_raised(session, fake_medplum):
    # create_appointment requires doctor_id/hospital_id/slot_id
    r = await execute_tool("create_appointment", {"doctor_id": "d"}, session)
    assert r["success"] is False
    assert r["error"] == "invalid_arguments"
    assert "details" in r


async def test_valid_dispatch(session, fake_medplum):
    r = await execute_tool("search_doctors", {"specialty": "Cardiology"}, session)
    assert r["success"] is True
    assert r["count"] == 1


async def test_handler_exception_becomes_error(session, fake_medplum, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(fake_medplum, "search_practitioners", boom)
    r = await execute_tool("search_doctors", {}, session)
    assert r["success"] is False
    assert "kaboom" in r["error"]
