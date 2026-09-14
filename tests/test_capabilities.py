# tests/test_capabilities.py — Milestone: scheduling + intake capabilities (Medplum-backed)
from src.agent.executor import execute_tool


async def test_search_and_availability(session, fake_medplum):
    docs = await execute_tool("search_doctors", {"specialty": "Cardiology"}, session)
    assert docs["success"] and docs["results"][0]["doctor_id"] == "doc1"

    avail = await execute_tool("check_availability", {"doctor_id": "doc1"}, session)
    assert avail["success"] and avail["count"] == 2
    assert session.state.selected_doctor_id == "doc1"


async def test_create_appointment_verifies_and_triggers_workflow(session, fake_medplum):
    r = await execute_tool(
        "create_appointment",
        {"doctor_id": "doc1", "hospital_id": "loc1", "slot_id": "slot1"},
        session,
    )
    assert r["success"] and r["verification_status"] == "EHR_VERIFIED"
    assert session.state.appointment_status == "Confirmed"
    # post-booking workflow fired: confirmation Communication + reminder Task
    assert any(c["category"] == "Appointment confirmation" for c in fake_medplum.communications)
    assert any(t["code"] == "appointment-reminder" for t in fake_medplum.tasks)


async def test_create_appointment_without_patient(fake_medplum):
    from src.agent.state import AgentSession
    fresh = AgentSession()  # no fhir_patient_id
    r = await execute_tool(
        "create_appointment",
        {"doctor_id": "doc1", "hospital_id": "loc1", "slot_id": "slot1"},
        fresh,
    )
    assert r == {"success": False, "error": "no_patient_in_session"}


async def test_reschedule_and_cancel(session, fake_medplum):
    resched = await execute_tool(
        "reschedule_appointment", {"appointment_id": "appt-slot1", "slot_id": "slot2"}, session)
    assert resched["success"] and session.state.appointment_status == "Confirmed"

    cancelled = await execute_tool(
        "cancel_appointment", {"appointment_id": "appt-slot1", "reason_code": "test"}, session)
    assert cancelled["success"] and session.state.appointment_status == "Cancelled"


async def test_questionnaire_flow(session, fake_medplum):
    q = await execute_tool("get_questionnaire", {"doctor_id": "doc1"}, session)
    assert q["found"] and session.state.questionnaire_ref == "Questionnaire/q1"

    sub = await execute_tool(
        "submit_questionnaire_response",
        {"appointment_id": "appt-slot1",
         "answers": [{"question_id": "q1", "raw_patient_input": "No", "structured_value": False}]},
        session,
    )
    assert sub["success"] and sub["answers_saved"] == 1


async def test_lookup_then_register(fake_medplum):
    from src.agent.state import AgentSession
    s = AgentSession()
    s.context.phone = "+19998887777"

    miss = await execute_tool("lookup_patient", {}, s)
    assert miss["success"] and miss["found"] is False

    reg = await execute_tool(
        "register_patient", {"first_name": "Ven", "last_name": "K", "date_of_birth": "2006-03-17"}, s)
    assert reg["success"] and s.context.fhir_patient_id == "pat-ven"

    hit = await execute_tool("lookup_patient", {}, s)
    assert hit["success"] and hit["found"] is True


async def test_get_appointment(session, fake_medplum):
    r = await execute_tool("get_appointment", {}, session)
    assert r["success"] and r["count"] == 1
    assert r["appointments"][0]["doctor"] == "Priya Rao"


async def test_transfer_and_end_call(session, fake_medplum):
    t = await execute_tool("transfer_to_human", {"reason": "complex"}, session)
    assert t["action"] == "TRANSFER" and session.state.appointment_status == "Escalated"

    e = await execute_tool("end_call", {"reason": "done"}, session)
    assert e["action"] == "HANGUP"


async def test_graceful_degradation_without_ehr(session, no_medplum):
    r = await execute_tool("search_doctors", {"specialty": "Cardiology"}, session)
    assert r == {"success": False, "error": "ehr_unavailable"}
