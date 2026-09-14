# src/api/routers/catalog.py — doctors, availability, questionnaires (reads)
from typing import Optional

from fastapi import APIRouter, Depends

from src.api import adapters
from src.api.deps import Scope, get_scope, require_medplum

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/doctors")
async def list_doctors(specialty: Optional[str] = None, scope: Scope = Depends(get_scope)):
    mp = require_medplum()
    org = scope.organization_id if scope.role == "hospital_admin" else None
    docs = await mp.search_practitioners(specialty=specialty, organization_id=org)
    return [adapters.doctor_dto(d) for d in docs]


@router.get("/doctors/{doctor_id}/slots")
async def doctor_slots(doctor_id: str, date: Optional[str] = None):
    mp = require_medplum()
    slots = await mp.get_available_slots(doctor_id, date=date)
    return [adapters.slot_dto(s) for s in slots]


@router.get("/doctors/{doctor_id}/questionnaire")
async def doctor_questionnaire(doctor_id: str):
    mp = require_medplum()
    q = await mp.get_questionnaire(doctor_id)
    return q or {"found": False, "questions": []}
