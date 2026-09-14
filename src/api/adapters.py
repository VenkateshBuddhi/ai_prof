# src/api/adapters.py
"""Map FHIR resources (and our friendly search results) to the frontend DTO
shapes in frontend/src/types/index.ts. Best-effort: fields we don't model yet
get sensible defaults rather than failing.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# FHIR Appointment.status -> frontend AppointmentStatus
_APPT_STATUS = {
    "proposed": "requested", "pending": "pending", "booked": "confirmed",
    "arrived": "confirmed", "checked-in": "confirmed", "fulfilled": "completed",
    "cancelled": "cancelled", "noshow": "no_show", "entered-in-error": "failed",
    "waitlist": "requested",
}


def _human_name(resource: Dict[str, Any]) -> str:
    name = (resource.get("name") or [{}])[0]
    given = " ".join(name.get("given") or [])
    full = f"{given} {name.get('family', '')}".strip()
    return full or resource.get("id", "")


def _ref_id(reference: str, prefix: str) -> Optional[str]:
    return reference.split("/", 1)[1] if reference.startswith(prefix + "/") else None


# --- doctors (from search_practitioners friendly dict) ------------------------
def doctor_dto(d: Dict[str, Any]) -> Dict[str, Any]:
    first, last = d.get("first_name") or "", d.get("last_name") or ""
    return {
        "id": d.get("doctor_id"),
        "name": (f"Dr. {first} {last}").strip(),
        "email": "",
        "specialty": d.get("specialty") or "",
        "department": d.get("specialty") or "",
        "qualifications": [],
        "experience_years": 0,
        "languages": [],
        "consultation_types": [],
        "consultation_duration": 30,
        "hospital_id": (d.get("hospitals") or {}).get("id"),
        "hospital_name": (d.get("hospitals") or {}).get("name"),
        "status": "active",
        "created_at": "",
    }


# --- slots (from get_available_slots friendly dict) ---------------------------
def slot_dto(s: Dict[str, Any]) -> Dict[str, Any]:
    start = s.get("start_time") or ""
    return {
        "id": s.get("slot_id"),
        "doctor_id": s.get("doctor_id"),
        "date": start[:10],
        "start_time": start,
        "end_time": s.get("end_time"),
        "is_available": s.get("status") == "free",
        "is_blocked": False,
        "label": s.get("slot"),
    }


# --- appointments (FHIR Appointment + included actors) ------------------------
def appointment_dto(appt: Dict[str, Any], by_ref: Dict[str, Dict]) -> Dict[str, Any]:
    patient_id = doctor_id = location_id = None
    for part in appt.get("participant") or []:
        ref = (part.get("actor") or {}).get("reference", "")
        if ref.startswith("Patient/"):
            patient_id = _ref_id(ref, "Patient")
        elif ref.startswith("Practitioner/"):
            doctor_id = _ref_id(ref, "Practitioner")
        elif ref.startswith("Location/"):
            location_id = _ref_id(ref, "Location")

    patient = by_ref.get(f"Patient/{patient_id}", {})
    doctor = by_ref.get(f"Practitioner/{doctor_id}", {})
    location = by_ref.get(f"Location/{location_id}", {})
    start = appt.get("start") or ""
    return {
        "id": appt.get("id"),
        "patient_id": patient_id,
        "patient_name": _human_name(patient) if patient else "",
        "doctor_id": doctor_id,
        "doctor_name": (f"Dr. {_human_name(doctor)}") if doctor else "",
        "hospital_id": location_id,
        "hospital_name": location.get("name", ""),
        "specialty": "",
        "appointment_type": appt.get("appointmentType", {}).get("text", "Standard"),
        "date": start[:10],
        "time": start[11:16],
        "duration": 30,
        "status": _APPT_STATUS.get(appt.get("status", ""), appt.get("status", "")),
        "external_appointment_id": None,
        "created_at": start,
    }


def patient_dto(p: Dict[str, Any]) -> Dict[str, Any]:
    phone = next((t.get("value") for t in (p.get("telecom") or []) if t.get("system") == "phone"), "")
    return {
        "id": p.get("id"),
        "name": _human_name(p),
        "email": next((t.get("value") for t in (p.get("telecom") or []) if t.get("system") == "email"), ""),
        "phone": phone,
        "date_of_birth": p.get("birthDate", ""),
        "preferred_communication": "phone",
        "created_at": (p.get("meta") or {}).get("lastUpdated", ""),
    }


def organization_dto(o: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": o.get("id"),
        "name": o.get("name", ""),
        "status": "approved" if o.get("active", True) else "suspended",
        "specialties": [],
        "tenant_id": o.get("id"),
    }


def task_to_workflow_dto(t: Dict[str, Any]) -> Dict[str, Any]:
    status_map = {"requested": "running", "in-progress": "running",
                  "completed": "completed", "failed": "failed", "cancelled": "cancelled"}
    period = t.get("executionPeriod") or {}
    return {
        "id": t.get("id"),
        "type": ((t.get("code") or {}).get("coding") or [{}])[0].get("code", "workflow"),
        "status": status_map.get(t.get("status", ""), t.get("status", "")),
        "trigger": "appointment",
        "related_id": (t.get("focus") or {}).get("reference"),
        "started_at": t.get("authoredOn", period.get("start", "")),
        "completed_at": period.get("end"),
        "retries": 0,
    }


def auditevent_dto(a: Dict[str, Any]) -> Dict[str, Any]:
    agent = (a.get("agent") or [{}])[0]
    entity = (a.get("entity") or [{}])[0]
    return {
        "id": a.get("id"),
        "event_type": ((a.get("type") or {}).get("display")) or "Application Activity",
        "actor_id": "ai-agent",
        "actor_name": (agent.get("who") or {}).get("display", "ai-prof"),
        "actor_role": "patient",
        "resource_type": (entity.get("what") or {}).get("reference", "").split("/")[0],
        "resource_id": (entity.get("what") or {}).get("reference", ""),
        "details": {"outcome": a.get("outcomeDesc", "")},
        "timestamp": a.get("recorded", ""),
    }


def communication_dto(c: Dict[str, Any]) -> Dict[str, Any]:
    payload = (c.get("payload") or [{}])
    return {
        "id": c.get("id"),
        "user_id": (c.get("subject") or {}).get("reference", ""),
        "type": ((c.get("category") or [{}])[0]).get("text", "notification"),
        "title": ((c.get("category") or [{}])[0]).get("text", "Notification"),
        "message": payload[-1].get("contentString", "") if payload else "",
        "read": True,
        "created_at": c.get("sent", ""),
    }
