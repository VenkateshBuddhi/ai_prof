# src/api/routers/appointments.py — appointment list / get / book / reschedule / cancel
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api import adapters
from src.api.deps import Scope, get_scope, require_medplum

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


class CreateAppointmentBody(BaseModel):
    patient_id: str
    doctor_id: str
    hospital_id: Optional[str] = None
    slot_id: str


class RescheduleBody(BaseModel):
    slot_id: str


class CancelBody(BaseModel):
    reason: Optional[str] = None


class SubmitAnswersBody(BaseModel):
    answers: list
    questionnaire_ref: Optional[str] = None


@router.get("")
async def list_appointments(status: Optional[str] = None, scope: Scope = Depends(get_scope)):
    mp = require_medplum()
    kwargs = {}
    if scope.role == "patient" and scope.patient_id:
        kwargs["patient_id"] = scope.patient_id
    elif scope.role == "doctor" and scope.doctor_id:
        kwargs["practitioner_id"] = scope.doctor_id
    if status:
        kwargs["status"] = status
    matches, by_ref = await mp.search_appointments(**kwargs)
    return [adapters.appointment_dto(a, by_ref) for a in matches]


@router.get("/{appointment_id}")
async def get_appointment(appointment_id: str):
    mp = require_medplum()
    appt = await mp.read_appointment(appointment_id)
    if not appt:
        raise HTTPException(404, "appointment not found")
    return adapters.appointment_dto(appt, {})


@router.post("")
async def create_appointment(body: CreateAppointmentBody):
    mp = require_medplum()
    result = await mp.create_appointment(
        patient_id=body.patient_id, practitioner_id=body.doctor_id,
        location_id=body.hospital_id, slot_id=body.slot_id,
    )
    if not result or result.get("error"):
        raise HTTPException(409, (result or {}).get("error", "booking_failed"))
    # Fire the post-booking workflow (confirmation + reminder), best-effort.
    try:
        from src.workflows import engine
        await engine.on_appointment_booked(
            patient_id=body.patient_id, appointment_id=result["appointment_id"],
            start=result.get("start"),
        )
    except Exception:  # noqa: BLE001
        pass
    return {**result, "verification_status": "EHR_VERIFIED"}


@router.post("/{appointment_id}/reschedule")
async def reschedule(appointment_id: str, body: RescheduleBody):
    mp = require_medplum()
    result = await mp.reschedule_appointment(appointment_id, body.slot_id)
    if not result.get("success"):
        raise HTTPException(409, result.get("error", "reschedule_failed"))
    return result


@router.post("/{appointment_id}/cancel")
async def cancel(appointment_id: str, body: CancelBody):
    mp = require_medplum()
    result = await mp.cancel_appointment(appointment_id, body.reason)
    if not result.get("success"):
        raise HTTPException(409, result.get("error", "cancel_failed"))
    return result


@router.post("/{appointment_id}/questionnaire-response")
async def submit_questionnaire(appointment_id: str, body: SubmitAnswersBody):
    mp = require_medplum()
    result = await mp.save_questionnaire_response(appointment_id, body.answers, body.questionnaire_ref)
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "submit_failed"))
    return result
