# src/agent/capabilities.py
"""Tool implementations backed by Medplum (FHIR R4) — the core scheduling engine.

Each takes a validated Pydantic input model plus the active AgentSession,
performs the action against Medplum, updates conversation state, and returns a
JSON-serialisable dict for the LLM.

Identity (patient + organization compartment) is resolved by the LiveKit worker
before the conversation and lives on session.context.fhir_patient_id /
fhir_organization_id, keeping every tool scoped to that patient's records.
"""
import logging
import os
from typing import Any, Dict

from src.database.medplum_client import get_medplum_client
from src.agent.state import AgentSession
from src.agent.schemas import (
    SearchDoctorsInput,
    CheckAvailabilityInput,
    CreateAppointmentInput,
    RescheduleAppointmentInput,
    CancelAppointmentInput,
    GetQuestionnaireInput,
    SubmitQuestionnaireResponseInput,
    LookupPatientInput,
    RegisterPatientInput,
    GetAppointmentInput,
    TransferToHumanInput,
    EndCallInput,
)

logger = logging.getLogger("AgentCapabilities")

_NO_EHR = {"success": False, "error": "ehr_unavailable"}


async def search_doctors(inp: SearchDoctorsInput, session: AgentSession) -> Dict[str, Any]:
    medplum = get_medplum_client()
    if not medplum:
        return _NO_EHR
    session.state.intent = "BOOK_APPOINTMENT"
    if inp.specialty:
        session.state.specialty = inp.specialty
    doctors = await medplum.search_practitioners(
        specialty=inp.specialty,
        organization_id=session.context.fhir_organization_id,
    )
    return {"success": True, "count": len(doctors), "results": doctors}


async def check_availability(inp: CheckAvailabilityInput, session: AgentSession) -> Dict[str, Any]:
    medplum = get_medplum_client()
    if not medplum:
        return _NO_EHR
    session.state.selected_doctor_id = inp.doctor_id
    if inp.date:
        session.state.date = inp.date
    slots = await medplum.get_available_slots(inp.doctor_id, date=inp.date)
    return {"success": True, "count": len(slots), "slots": slots}


async def create_appointment(inp: CreateAppointmentInput, session: AgentSession) -> Dict[str, Any]:
    """Book the slot in Medplum. Because Medplum IS the EHR, a successfully
    created (status=booked) Appointment is the verification — no separate sync."""
    medplum = get_medplum_client()
    if not medplum:
        return _NO_EHR
    patient_id = session.context.fhir_patient_id
    if not patient_id:
        return {"success": False, "error": "no_patient_in_session"}

    result = await medplum.create_appointment(
        patient_id=patient_id,
        practitioner_id=inp.doctor_id,
        location_id=inp.hospital_id,
        slot_id=inp.slot_id,
    )
    if not result or result.get("error"):
        session.state.appointment_status = "Failed"
        return {"success": False, "error": (result or {}).get("error", "booking_failed")}

    session.state.appointment_id = result["appointment_id"]
    session.state.selected_doctor_id = inp.doctor_id
    session.state.selected_hospital_id = inp.hospital_id
    session.state.selected_slot_id = inp.slot_id
    session.state.appointment_status = "Confirmed"

    # Post-booking workflow: confirmation notification + scheduled reminder.
    # Best-effort — a workflow hiccup must never fail a confirmed booking.
    try:
        from src.workflows import engine
        await engine.on_appointment_booked(
            patient_id=patient_id,
            appointment_id=result["appointment_id"],
            start=result.get("start"),
            organization_id=session.context.fhir_organization_id,
            phone=session.context.phone,
        )
    except Exception:  # noqa: BLE001
        logger.exception("post-booking workflow failed (booking still confirmed)")

    return {
        "success": True,
        "appointment_id": result["appointment_id"],
        "verification_status": "EHR_VERIFIED",
        "status": result.get("status", "booked"),
    }


async def reschedule_appointment(inp: RescheduleAppointmentInput, session: AgentSession) -> Dict[str, Any]:
    medplum = get_medplum_client()
    if not medplum:
        return _NO_EHR
    result = await medplum.reschedule_appointment(inp.appointment_id, inp.slot_id)
    if result.get("success"):
        session.state.intent = "RESCHEDULE"
        session.state.selected_slot_id = inp.slot_id
        session.state.appointment_status = "Confirmed"
    return result


async def cancel_appointment(inp: CancelAppointmentInput, session: AgentSession) -> Dict[str, Any]:
    medplum = get_medplum_client()
    if not medplum:
        return _NO_EHR
    result = await medplum.cancel_appointment(inp.appointment_id, inp.reason_code)
    if result.get("success"):
        session.state.intent = "CANCEL"
        session.state.appointment_status = "Cancelled"
    return result


async def get_questionnaire(inp: GetQuestionnaireInput, session: AgentSession) -> Dict[str, Any]:
    medplum = get_medplum_client()
    if not medplum:
        return _NO_EHR
    q = await medplum.get_questionnaire(inp.doctor_id)
    if not q:
        return {"success": True, "found": False, "questions": []}
    session.state.intent = "COMPLETE_QUESTIONNAIRE"
    session.state.questionnaire_id = q.get("questionnaire_id")
    session.state.questionnaire_ref = q.get("questionnaire_ref")
    return {"success": True, "found": True, **q}


async def submit_questionnaire_response(inp: SubmitQuestionnaireResponseInput, session: AgentSession) -> Dict[str, Any]:
    medplum = get_medplum_client()
    if not medplum:
        return _NO_EHR
    answers = [a.model_dump() for a in inp.answers]
    return await medplum.save_questionnaire_response(
        appointment_id=inp.appointment_id,
        answers=answers,
        questionnaire_ref=session.state.questionnaire_ref,
    )


async def lookup_patient(inp: LookupPatientInput, session: AgentSession) -> Dict[str, Any]:
    """Resolve (or re-resolve) the caller against Medplum by phone and load them
    into the session so subsequent tools are scoped to their compartment."""
    medplum = get_medplum_client()
    if not medplum:
        return _NO_EHR
    phone = inp.phone or session.context.phone
    if not phone:
        return {"success": False, "error": "no_phone"}
    patient = await medplum.find_patient_by_phone(phone)
    if not patient or not patient.get("patient_id"):
        return {"success": True, "found": False}
    session.context.phone = phone
    session.context.fhir_patient_id = patient["patient_id"]
    session.context.fhir_organization_id = patient.get("organization_id")
    session.context.first_name = patient.get("first_name")
    session.context.last_name = patient.get("last_name")
    return {
        "success": True,
        "found": True,
        "patient_id": patient["patient_id"],
        "first_name": patient.get("first_name"),
        "last_name": patient.get("last_name"),
    }


async def register_patient(inp: RegisterPatientInput, session: AgentSession) -> Dict[str, Any]:
    """Create a new patient record when lookup_patient found no existing one, so
    an unidentified caller can still book. Loads them into the session."""
    medplum = get_medplum_client()
    if not medplum:
        return _NO_EHR
    phone = inp.phone or session.context.phone
    org = session.context.fhir_organization_id or os.environ.get("MEDPLUM_DEFAULT_ORG")
    patient = await medplum.create_patient(
        inp.first_name, inp.last_name, phone, birth_date=inp.date_of_birth, organization_id=org,
    )
    if not patient or not patient.get("patient_id"):
        return {"success": False, "error": "registration_failed"}
    session.context.fhir_patient_id = patient["patient_id"]
    session.context.fhir_organization_id = patient.get("organization_id") or org
    session.context.first_name = inp.first_name
    session.context.last_name = inp.last_name
    if phone:
        session.context.phone = phone
    return {
        "success": True,
        "patient_id": patient["patient_id"],
        "first_name": inp.first_name,
        "last_name": inp.last_name,
    }


async def get_appointment(inp: GetAppointmentInput, session: AgentSession) -> Dict[str, Any]:
    """List the caller's existing appointments so an existing one can be
    rescheduled/cancelled or disambiguated ('you have two — which one?')."""
    medplum = get_medplum_client()
    if not medplum:
        return _NO_EHR
    patient_id = session.context.fhir_patient_id
    if not patient_id:
        return {"success": False, "error": "no_patient_in_session"}
    appointments = await medplum.get_appointments(patient_id, status=inp.status or "booked")
    return {"success": True, "count": len(appointments), "appointments": appointments}


async def transfer_to_human(inp: TransferToHumanInput, session: AgentSession) -> Dict[str, Any]:
    session.state.appointment_status = "Escalated"
    logger.info(f"[Escalation] session={session.session_id} reason={inp.reason}")
    return {
        "success": True,
        "action": "TRANSFER",
        "destination_sip": "sip:escalations@hospital.com",
        "reason": inp.reason,
        "context_summary": inp.context_summary,
    }


async def end_call(inp: EndCallInput, session: AgentSession) -> Dict[str, Any]:
    """Signal that the conversation is complete and the call should hang up.
    The voice worker plays the closing line, then disconnects."""
    logger.info(f"[EndCall] session={session.session_id} reason={inp.reason}")
    return {"success": True, "action": "HANGUP", "reason": inp.reason}
