# src/api/routers/patients.py — patient read / register / notifications
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api import adapters
from src.api.deps import Scope, get_scope, require_medplum

router = APIRouter(prefix="/api/patients", tags=["patients"])


class RegisterPatientBody(BaseModel):
    first_name: str
    last_name: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    organization_id: Optional[str] = None


@router.get("")
async def list_patients(scope: Scope = Depends(get_scope)):
    mp = require_medplum()
    org = scope.organization_id if scope.role == "hospital_admin" else None
    return [adapters.patient_dto(p) for p in await mp.list_patients(organization_id=org)]


@router.get("/by-phone")
async def patient_by_phone(phone: str):
    mp = require_medplum()
    p = await mp.find_patient_by_phone(phone)
    return p or {"found": False}


@router.get("/{patient_id}")
async def get_patient(patient_id: str):
    mp = require_medplum()
    p = await mp.read_patient(patient_id)
    if not p:
        raise HTTPException(404, "patient not found")
    return adapters.patient_dto(p)


@router.post("")
async def register_patient(body: RegisterPatientBody):
    mp = require_medplum()
    p = await mp.create_patient(
        body.first_name, body.last_name, body.phone,
        birth_date=body.date_of_birth, organization_id=body.organization_id,
    )
    if not p or not p.get("patient_id"):
        raise HTTPException(400, "registration_failed")
    return p


@router.get("/{patient_id}/notifications")
async def patient_notifications(patient_id: str):
    mp = require_medplum()
    return [adapters.communication_dto(c) for c in await mp.list_communications(patient_id=patient_id)]
