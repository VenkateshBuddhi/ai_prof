# src/api/deps.py
"""Request dependencies: caller scope (DEV BYPASS) + Medplum gateway.

DEV BYPASS auth: role/scope come from request headers, defaulting to
platform_admin so the dashboards work without a login during development:
    X-Role:          platform_admin | hospital_admin | doctor | patient
    X-Organization:  Organization id (hospital_admin scope)
    X-Patient-Id:    Patient id (patient scope)
    X-Doctor-Id:     Practitioner id (doctor scope)
Replace `get_scope` with Supabase-JWT verification when auth is added — the rest
of the API depends only on the resolved `Scope`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException

from src.database.medplum_client import MedplumClient, get_medplum_client

ROLES = {"platform_admin", "hospital_admin", "doctor", "patient"}


@dataclass
class Scope:
    role: str
    organization_id: Optional[str] = None
    patient_id: Optional[str] = None
    doctor_id: Optional[str] = None


async def get_scope(
    x_role: str = Header(default="platform_admin", alias="X-Role"),
    x_organization: Optional[str] = Header(default=None, alias="X-Organization"),
    x_patient_id: Optional[str] = Header(default=None, alias="X-Patient-Id"),
    x_doctor_id: Optional[str] = Header(default=None, alias="X-Doctor-Id"),
) -> Scope:
    role = x_role if x_role in ROLES else "platform_admin"
    return Scope(role=role, organization_id=x_organization,
                 patient_id=x_patient_id, doctor_id=x_doctor_id)


def require_medplum() -> MedplumClient:
    client = get_medplum_client()
    if not client:
        raise HTTPException(status_code=503, detail="EHR (Medplum) not configured")
    return client
