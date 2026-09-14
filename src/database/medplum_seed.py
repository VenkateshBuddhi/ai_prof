# src/database/medplum_seed.py
"""Seed a Medplum project with rich FHIR R4 clinical and scheduling data.

Generates 3-4 records for each core FHIR resource type:
  * Organizations      — 3 Healthcare Networks / Health Systems
  * Locations          — 4 Medical Centers, Hospitals, and Outpatient Clinics
  * Practitioners      — 5 Doctors across multiple specialties
  * PractitionerRoles  — 5 Roles linking doctors, facilities, and specialties
  * Schedules & Slots  — ~14 days of free booking slots per doctor (~100+ slots)
  * Patients           — 4 diverse test patients with phone numbers & demographics
  * Conditions         — 6 chronic and acute conditions linked to patients
  * AllergyIntolerances— 4 allergies with criticality and manifestations
  * MedicationRequests — 5 active prescriptions with dosage, instructions, and refills
  * Observations       — 8 clinical labs and vitals (A1C, BP, Cholesterol, Glucose, Creatinine)
  * Appointments       — 4 existing appointments (booked / fulfilled / follow-up)
  * Questionnaires     — 4 specialty pre-visit questionnaires (Cardiology, Derm, Ortho, Primary Care)
  * CarePlans & Tasks  — 4 clinical workflows, care gaps, and doctor review tasks

Everything is packaged into one idempotent FHIR **transaction Bundle** with
conditional creates (`ifNoneExist` on unique seed identifiers) and `urn:uuid`
references for intra-bundle resolution.

Usage:
    uv run python -m src.database.medplum_seed --dry-run     # build + inspect bundle
    uv run python -m src.database.medplum_seed               # POST seed bundle to Medplum
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, ".env")

SEED_SYSTEM = "https://ai-prof.example/seed"
TZ = ZoneInfo("America/New_York")
DAYS_AHEAD = 14
SLOT_MINUTES = 30

# ---------------------------------------------------------------------------
# Seed Data Definitions (3-4+ records per category)
# ---------------------------------------------------------------------------

ORGANIZATIONS = {
    "org-st-mary": {
        "name": "St. Mary Health Network",
        "alias": ["SMMC Health System"],
        "type": "prov",
    },
    "org-metro-health": {
        "name": "Metro Community Health Partners",
        "alias": ["Metro Health"],
        "type": "prov",
    },
    "org-valley-specialty": {
        "name": "Valley Specialty Healthcare Group",
        "alias": ["Valley Specialists"],
        "type": "prov",
    },
}

LOCATIONS = {
    "loc-smmc": {
        "name": "St. Mary Medical Center",
        "org_key": "org-st-mary",
        "address": {"line": ["100 Health Park Blvd"], "city": "Springfield", "state": "IL", "postalCode": "62701"},
    },
    "loc-dgh": {
        "name": "Downtown General Hospital",
        "org_key": "org-st-mary",
        "address": {"line": ["450 Center Street"], "city": "Springfield", "state": "IL", "postalCode": "62702"},
    },
    "loc-wfhc": {
        "name": "Westside Family Health Center",
        "org_key": "org-metro-health",
        "address": {"line": ["782 Westland Ave"], "city": "Springfield", "state": "IL", "postalCode": "62704"},
    },
    "loc-nsc": {
        "name": "Northside Specialty Pavilion",
        "org_key": "org-valley-specialty",
        "address": {"line": ["300 Northview Road"], "city": "Springfield", "state": "IL", "postalCode": "62703"},
    },
}

DOCTORS = {
    "doc-sharma": {
        "given": "Aarav", "family": "Sharma", "prefix": "Dr.", "specialty": "Dermatology",
        "snomed": "394582007", "loc_key": "loc-smmc", "org_key": "org-st-mary",
        "windows": [("Monday", "09:00", "12:00"), ("Friday", "13:00", "17:00")],
    },
    "doc-rao": {
        "given": "Priya", "family": "Rao", "prefix": "Dr.", "specialty": "Cardiology",
        "snomed": "394579002", "loc_key": "loc-smmc", "org_key": "org-st-mary",
        "windows": [("Thursday", "13:00", "17:00"), ("Friday", "09:00", "12:00")],
    },
    "doc-jenkins": {
        "given": "Sarah", "family": "Jenkins", "prefix": "Dr.", "specialty": "Orthopedics",
        "snomed": "394801008", "loc_key": "loc-dgh", "org_key": "org-st-mary",
        "windows": [("Wednesday", "09:00", "12:00"), ("Thursday", "13:00", "17:00")],
    },
    "doc-vance": {
        "given": "Marcus", "family": "Vance", "prefix": "Dr.", "specialty": "Internal Medicine",
        "snomed": "419192003", "loc_key": "loc-wfhc", "org_key": "org-metro-health",
        "windows": [("Tuesday", "09:00", "13:00"), ("Thursday", "09:00", "13:00")],
    },
    "doc-rostova": {
        "given": "Elena", "family": "Rostova", "prefix": "Dr.", "specialty": "Neurology",
        "snomed": "394591006", "loc_key": "loc-nsc", "org_key": "org-valley-specialty",
        "windows": [("Monday", "13:00", "17:00"), ("Wednesday", "13:00", "17:00")],
    },
}

PATIENTS = {
    "pat-john-doe": {
        "given": ["John"], "family": "Doe", "gender": "male", "birthDate": "1985-04-12",
        "phone": "+15550192834", "email": "john.doe@example.com", "org_key": "org-st-mary",
    },
    "pat-jane-smith": {
        "given": ["Jane"], "family": "Smith", "gender": "female", "birthDate": "1990-08-23",
        "phone": "+15550192835", "email": "jane.smith@example.com", "org_key": "org-st-mary",
    },
    "pat-robert-chen": {
        "given": ["Robert"], "family": "Chen", "gender": "male", "birthDate": "1974-11-05",
        "phone": "+15550192836", "email": "robert.chen@example.com", "org_key": "org-metro-health",
    },
    "pat-emily-davis": {
        "given": ["Emily"], "family": "Davis", "gender": "female", "birthDate": "1968-02-19",
        "phone": "+15550192837", "email": "emily.davis@example.com", "org_key": "org-valley-specialty",
    },
}


def _load_env() -> None:
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip("'").strip('"'))


class _Bundle:
    """Accumulates transaction entries with unique urn:uuid references."""

    def __init__(self) -> None:
        self.entries: list = []
        self.urn: dict = {}

    def add(self, seed_value: str, resource: dict) -> str:
        ref = self.urn.get(seed_value)
        if ref:
            return ref
        ref = f"urn:uuid:{uuid.uuid4()}"
        self.urn[seed_value] = ref
        resource.setdefault("identifier", [{"system": SEED_SYSTEM, "value": seed_value}])
        self.entries.append({
            "fullUrl": ref,
            "resource": resource,
            "request": {
                "method": "POST",
                "url": resource["resourceType"],
                "ifNoneExist": f"identifier={SEED_SYSTEM}|{seed_value}",
            },
        })
        return ref

    def bundle(self) -> dict:
        return {"resourceType": "Bundle", "type": "transaction", "entry": self.entries}


def _slot_times(weekday: str, start_hhmm: str, end_hhmm: str):
    """Yield (start_dt, end_dt) for each SLOT_MINUTES block on matching weekdays."""
    sh, sm = map(int, start_hhmm.split(":"))
    eh, em = map(int, end_hhmm.split(":"))
    today = datetime.now(TZ).date()
    for offset in range(DAYS_AHEAD):
        day = today + timedelta(days=offset)
        if day.strftime("%A") != weekday:
            continue
        cursor = datetime.combine(day, time(sh, sm), tzinfo=TZ)
        window_end = datetime.combine(day, time(eh, em), tzinfo=TZ)
        while cursor + timedelta(minutes=SLOT_MINUTES) <= window_end:
            nxt = cursor + timedelta(minutes=SLOT_MINUTES)
            yield cursor, nxt
            cursor = nxt


def build_bundle() -> dict:
    b = _Bundle()

    # 1. Organizations (3 records)
    org_refs = {}
    for key, data in ORGANIZATIONS.items():
        org_refs[key] = b.add(key, {
            "resourceType": "Organization",
            "name": data["name"],
            "alias": data.get("alias", []),
            "active": True,
        })

    # 2. Locations (4 records)
    loc_refs = {}
    for key, data in LOCATIONS.items():
        loc_refs[key] = b.add(key, {
            "resourceType": "Location",
            "name": data["name"],
            "status": "active",
            "address": data.get("address", {}),
            "managingOrganization": {"reference": org_refs[data["org_key"]]},
        })

    # 3. Patients (4 records)
    pat_refs = {}
    for key, data in PATIENTS.items():
        pat_refs[key] = b.add(key, {
            "resourceType": "Patient",
            "active": True,
            "name": [{"given": data["given"], "family": data["family"]}],
            "gender": data["gender"],
            "birthDate": data["birthDate"],
            "telecom": [
                {"system": "phone", "value": data["phone"], "use": "mobile"},
                {"system": "email", "value": data["email"]},
            ],
            "managingOrganization": {"reference": org_refs[data["org_key"]]},
        })

    # 4. Practitioners, PractitionerRoles, Schedules, and Slots (5 doctors, ~100+ slots)
    prac_refs = {}
    role_refs = {}
    sched_refs = {}
    first_free_slot_refs = {}

    for key, doc in DOCTORS.items():
        prac_ref = b.add(key, {
            "resourceType": "Practitioner",
            "active": True,
            "name": [{"given": [doc["given"]], "family": doc["family"], "prefix": [doc["prefix"]]}],
        })
        prac_refs[key] = prac_ref

        specialty_cc = {
            "coding": [{"system": "http://snomed.info/sct", "code": doc["snomed"], "display": doc["specialty"]}],
            "text": doc["specialty"],
        }
        role_ref = b.add(f"role-{key}", {
            "resourceType": "PractitionerRole",
            "active": True,
            "practitioner": {"reference": prac_ref},
            "organization": {"reference": org_refs[doc["org_key"]]},
            "location": [{"reference": loc_refs[doc["loc_key"]]}],
            "specialty": [specialty_cc],
        })
        role_refs[key] = role_ref

        sched_ref = b.add(f"sched-{key}", {
            "resourceType": "Schedule",
            "active": True,
            "actor": [{"reference": prac_ref}, {"reference": loc_refs[doc["loc_key"]]}],
        })
        sched_refs[key] = sched_ref

        for weekday, start_hhmm, end_hhmm in doc["windows"]:
            for start_dt, end_dt in _slot_times(weekday, start_hhmm, end_hhmm):
                iso_start = start_dt.isoformat()
                iso_end = end_dt.isoformat()
                slot_ref = b.add(f"slot-{key}-{iso_start}", {
                    "resourceType": "Slot",
                    "schedule": {"reference": sched_ref},
                    "status": "free",
                    "start": iso_start,
                    "end": iso_end,
                })
                if key not in first_free_slot_refs:
                    first_free_slot_refs[key] = (slot_ref, iso_start, iso_end)

    # 5. Conditions / Medical Problems (6 records)
    conditions = [
        ("cond-john-htn", "pat-john-doe", "Essential (primary) hypertension", "I10", "38341003", "active"),
        ("cond-john-dm2", "pat-john-doe", "Type 2 diabetes mellitus without complications", "E11.9", "44054006", "active"),
        ("cond-jane-asthma", "pat-jane-smith", "Moderate persistent asthma", "J45.40", "195967001", "active"),
        ("cond-robert-cad", "pat-robert-chen", "Coronary artery disease", "I25.10", "53741008", "active"),
        ("cond-robert-lipid", "pat-robert-chen", "Hyperlipidemia, unspecified", "E78.5", "55822004", "active"),
        ("cond-emily-ckd", "pat-emily-davis", "Chronic kidney disease, stage 3", "N18.3", "433144002", "active"),
    ]
    for seed_id, pat_key, display, icd10, snomed, status in conditions:
        b.add(seed_id, {
            "resourceType": "Condition",
            "clinicalStatus": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": status}]
            },
            "verificationStatus": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]
            },
            "category": [{
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-category", "code": "problem-list-item"}]
            }],
            "code": {
                "coding": [
                    {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": icd10, "display": display},
                    {"system": "http://snomed.info/sct", "code": snomed, "display": display},
                ],
                "text": display,
            },
            "subject": {"reference": pat_refs[pat_key]},
            "recordedDate": "2024-01-15",
        })

    # 6. AllergyIntolerances (4 records)
    allergies = [
        ("alg-john-pnc", "pat-john-doe", "Penicillin G", "70618", "high", "hives, facial swelling"),
        ("alg-jane-sulfa", "pat-jane-smith", "Sulfonamide antibacterial", "10168", "medium", "maculopapular rash"),
        ("alg-robert-peanut", "pat-robert-chen", "Peanut", "91935009", "high", "anaphylaxis"),
        ("alg-emily-latex", "pat-emily-davis", "Latex", "300916003", "low", "contact dermatitis"),
    ]
    for seed_id, pat_key, substance, code, crit, reaction in allergies:
        b.add(seed_id, {
            "resourceType": "AllergyIntolerance",
            "clinicalStatus": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "code": "active"}]
            },
            "verificationStatus": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification", "code": "confirmed"}]
            },
            "type": "allergy",
            "criticality": crit,
            "code": {
                "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": code, "display": substance}],
                "text": substance,
            },
            "patient": {"reference": pat_refs[pat_key]},
            "reaction": [{"manifestation": [{"text": reaction}]}],
        })

    # 7. MedicationRequests / Prescriptions & Refill State (5 records)
    medications = [
        ("med-john-metformin", "pat-john-doe", "doc-vance", "Metformin hydrochloride 500 MG Oral Tablet", "860975", "Take 1 tablet by mouth twice daily with meals", 2),
        ("med-john-lisinopril", "pat-john-doe", "doc-rao", "Lisinopril 10 MG Oral Tablet", "314076", "Take 1 tablet by mouth once daily in the morning", 1),
        ("med-jane-albuterol", "pat-jane-smith", "doc-vance", "Albuterol 0.09 MG/ACTUAT Inhalation Aerosol", "745679", "Inhale 2 puffs every 4-6 hours as needed for wheezing", 0),
        ("med-robert-atorvastatin", "pat-robert-chen", "doc-rao", "Atorvastatin 20 MG Oral Tablet", "617314", "Take 1 tablet by mouth daily at bedtime", 3),
        ("med-emily-amlodipine", "pat-emily-davis", "doc-vance", "Amlodipine 5 MG Oral Tablet", "197361", "Take 1 tablet by mouth once daily", 2),
    ]
    for seed_id, pat_key, doc_key, med_name, rxnorm, sig, refills in medications:
        b.add(seed_id, {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": rxnorm, "display": med_name}],
                "text": med_name,
            },
            "subject": {"reference": pat_refs[pat_key]},
            "requester": {"reference": prac_refs[doc_key]},
            "dosageInstruction": [{"text": sig}],
            "dispenseRequest": {
                "numberOfRepeatsAllowed": refills,
                "quantity": {"value": 30, "unit": "TAB", "system": "http://unitsofmeasure.org", "code": "TAB"},
                "expectedSupplyDuration": {"value": 30, "unit": "days", "system": "http://unitsofmeasure.org", "code": "d"},
            },
            "authoredOn": "2024-02-01T10:00:00Z",
        })

    # 8. Observations / Labs & Vitals (8 records)
    observations = [
        ("obs-john-a1c-1", "pat-john-doe", "Hemoglobin A1c/Hemoglobin.total in Blood", "4548-4", 7.2, "%", "2024-01-10T09:00:00Z", "H"),
        ("obs-john-a1c-2", "pat-john-doe", "Hemoglobin A1c/Hemoglobin.total in Blood", "4548-4", 6.8, "%", "2024-04-12T09:30:00Z", "H"),
        ("obs-john-bp", "pat-john-doe", "Blood Pressure", "85354-9", 138, "mmHg", "2024-04-12T09:30:00Z", "H"),
        ("obs-robert-chol", "pat-robert-chen", "Cholesterol in Serum or Plasma", "2093-3", 215, "mg/dL", "2024-02-20T11:00:00Z", "H"),
        ("obs-robert-ldl", "pat-robert-chen", "Low Density Lipoprotein Cholesterol", "13457-7", 134, "mg/dL", "2024-02-20T11:00:00Z", "H"),
        ("obs-jane-fev1", "pat-jane-smith", "Forced Expiratory Volume in 1 second", "20150-9", 82.0, "%", "2024-03-15T14:00:00Z", "N"),
        ("obs-emily-creat", "pat-emily-davis", "Creatinine in Serum or Plasma", "2160-0", 1.4, "mg/dL", "2024-03-01T10:15:00Z", "H"),
        ("obs-emily-egfr", "pat-emily-davis", "Glomerular filtration rate/1.73 sq M.predicted", "33914-3", 52.0, "mL/min/1.73m2", "2024-03-01T10:15:00Z", "L"),
    ]
    for seed_id, pat_key, lab_name, loinc, val, unit, eff_dt, interp in observations:
        b.add(seed_id, {
            "resourceType": "Observation",
            "status": "final",
            "category": [{
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory"}]
            }],
            "code": {
                "coding": [{"system": "http://loinc.org", "code": loinc, "display": lab_name}],
                "text": lab_name,
            },
            "subject": {"reference": pat_refs[pat_key]},
            "effectiveDateTime": eff_dt,
            "valueQuantity": {
                "value": val,
                "unit": unit,
                "system": "http://unitsofmeasure.org",
                "code": unit,
            },
            "interpretation": [{
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": interp}]
            }],
        })

    # 9. Appointments (4 records)
    now_utc = datetime.now(timezone.utc)
    appt_1_start = (now_utc + timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)
    appt_2_start = (now_utc + timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0)
    appt_3_start = (now_utc - timedelta(days=10)).replace(hour=9, minute=0, second=0, microsecond=0)
    appt_4_start = (now_utc + timedelta(days=7)).replace(hour=15, minute=0, second=0, microsecond=0)

    appointments = [
        ("appt-john-cardio", "pat-john-doe", "doc-rao", "loc-smmc", "booked", "Follow-up Cardiology Consult", appt_1_start),
        ("appt-jane-derm", "pat-jane-smith", "doc-sharma", "loc-smmc", "booked", "Dermatology Evaluation: Skin Rash", appt_2_start),
        ("appt-robert-wellness", "pat-robert-chen", "doc-vance", "loc-wfhc", "fulfilled", "Annual Comprehensive Wellness Visit", appt_3_start),
        ("appt-emily-ortho", "pat-emily-davis", "doc-jenkins", "loc-dgh", "booked", "Orthopedic Knee Pain Assessment", appt_4_start),
    ]
    for seed_id, pat_key, doc_key, loc_key, status, desc, start_dt in appointments:
        end_dt = start_dt + timedelta(minutes=30)
        b.add(seed_id, {
            "resourceType": "Appointment",
            "status": status,
            "description": desc,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "created": now_utc.isoformat(),
            "participant": [
                {"actor": {"reference": pat_refs[pat_key]}, "status": "accepted"},
                {"actor": {"reference": prac_refs[doc_key]}, "status": "accepted"},
                {"actor": {"reference": loc_refs[loc_key]}, "status": "accepted"},
            ],
        })

    # 10. Questionnaires (4 specialty intake questionnaires)
    questionnaires = [
        ("q-cardiology-previsit", "CardiologyPreVisitIntake", "Cardiology Pre-visit Intake", "394579002", "Cardiology", [
            {"linkId": "q1", "text": "Are you experiencing chest pain, tightness, or pressure?", "type": "boolean", "required": True},
            {"linkId": "q2", "text": "How long have you noticed these cardiovascular symptoms?", "type": "string", "required": True},
            {"linkId": "q3", "text": "Do you have a personal or family history of heart disease or heart attacks?", "type": "boolean", "required": False},
            {"linkId": "q4", "text": "Have you experienced any shortness of breath or dizziness when climbing stairs?", "type": "boolean", "required": False},
        ]),
        ("q-dermatology-previsit", "DermatologyPreVisitIntake", "Dermatology Pre-visit Intake", "394582007", "Dermatology", [
            {"linkId": "q1", "text": "Where on your body is the skin lesion or rash located?", "type": "string", "required": True},
            {"linkId": "q2", "text": "Is the area itchy, burning, painful, or bleeding?", "type": "string", "required": True},
            {"linkId": "q3", "text": "Have you started any new medications or applied over-the-counter creams?", "type": "boolean", "required": False},
            {"linkId": "q4", "text": "Has the lesion changed in size, shape, or color recently?", "type": "boolean", "required": False},
        ]),
        ("q-orthopedics-previsit", "OrthopedicsPreVisitIntake", "Orthopedics Pre-visit Intake", "394801008", "Orthopedics", [
            {"linkId": "q1", "text": "Which joint or bone is causing pain (e.g. knee, shoulder, lower back)?", "type": "string", "required": True},
            {"linkId": "q2", "text": "On a scale of 1-10, how severe is the pain during everyday movement?", "type": "integer", "required": True},
            {"linkId": "q3", "text": "Did this pain start after a specific injury, fall, or athletic activity?", "type": "boolean", "required": False},
            {"linkId": "q4", "text": "Are you experiencing joint swelling, locking, or giving way?", "type": "boolean", "required": False},
        ]),
        ("q-primary-care-previsit", "PrimaryCarePreVisitIntake", "Internal Medicine & Primary Care Intake", "419192003", "Internal Medicine", [
            {"linkId": "q1", "text": "What is the primary reason or main health concern for your visit today?", "type": "string", "required": True},
            {"linkId": "q2", "text": "Have you had any unexpected weight changes, fever, or chronic fatigue?", "type": "boolean", "required": False},
            {"linkId": "q3", "text": "Do you require any routine prescription refills during this visit?", "type": "boolean", "required": True},
            {"linkId": "q4", "text": "Are you up to date on your annual vaccinations (Flu, COVID, Tdap)?", "type": "boolean", "required": False},
        ]),
    ]
    for seed_id, name, title, snomed, specialty, items in questionnaires:
        b.add(seed_id, {
            "resourceType": "Questionnaire",
            "status": "active",
            "name": name,
            "title": title,
            "useContext": [{
                "code": {"system": "http://terminology.hl7.org/CodeSystem/usage-context-type", "code": "focus"},
                "valueCodeableConcept": {
                    "coding": [{"system": "http://snomed.info/sct", "code": snomed, "display": specialty}],
                    "text": specialty,
                },
            }],
            "item": items,
        })

    # 11. CarePlans & Tasks (4 workflow and clinical review records)
    tasks = [
        ("task-john-a1c-review", "pat-john-doe", "doc-vance", "Review 90-day HbA1c lab trend and adjust Metformin dosage", "ready"),
        ("task-jane-refill-auth", "pat-jane-smith", "doc-vance", "Authorize Albuterol Inhaler renewal for persistent asthma", "requested"),
        ("task-robert-lipid-gap", "pat-robert-chen", "doc-rao", "Schedule fasting lipid panel follow-up & CAD care plan check", "in-progress"),
        ("task-emily-renal-check", "pat-emily-davis", "doc-vance", "Monitor Stage 3 CKD eGFR stability prior to medication adjustment", "ready"),
    ]
    for seed_id, pat_key, doc_key, desc, status in tasks:
        b.add(seed_id, {
            "resourceType": "Task",
            "status": status,
            "intent": "order",
            "priority": "routine",
            "description": desc,
            "for": {"reference": pat_refs[pat_key]},
            "owner": {"reference": prac_refs[doc_key]},
            "authoredOn": "2024-04-10T08:30:00Z",
        })

    b.add("cp-john-diabetes", {
        "resourceType": "CarePlan",
        "status": "active",
        "intent": "plan",
        "title": "Type 2 Diabetes & Hypertension Integrated Care Plan",
        "description": "Quarterly A1C monitoring, daily blood pressure tracking, low sodium diabetic diet.",
        "subject": {"reference": pat_refs["pat-john-doe"]},
        "author": {"reference": prac_refs["doc-vance"]},
        "category": [{
            "coding": [{"system": "http://snomed.info/sct", "code": "698360004", "display": "Diabetes management care plan"}]
        }],
    })

    return b.bundle()


def _summarize(bundle: dict) -> None:
    counts: dict = {}
    for entry in bundle["entry"]:
        rt = entry["resource"]["resourceType"]
        counts[rt] = counts.get(rt, 0) + 1
    print("\n=======================================================")
    print("  FHIR R4 Medplum Transaction Bundle Summary")
    print("=======================================================")
    for rt, n in sorted(counts.items()):
        print(f"  {rt:22} {n:>4} records")
    print("-------------------------------------------------------")
    print(f"  {'TOTAL':22} {len(bundle['entry']):>4} resources")
    print("=======================================================\n")


async def _run(dry_run: bool) -> None:
    bundle = build_bundle()
    _summarize(bundle)

    if dry_run:
        print("[DRY-RUN] Sample patient & questionnaire resources from generated bundle:\n")
        sample_pat = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient")
        print("Patient sample:")
        print(json.dumps(sample_pat, indent=2))
        print("\nMedicationRequest sample:")
        sample_med = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "MedicationRequest")
        print(json.dumps(sample_med, indent=2))
        print("\n(dry-run: nothing sent to Medplum. Run without --dry-run to seed live instance.)")
        return

    from src.database.medplum_client import get_medplum_client
    medplum = get_medplum_client()
    if not medplum:
        print("Medplum client is not configured (check MEDPLUM_CLIENT_ID / MEDPLUM_CLIENT_SECRET in .env). Aborting.")
        return

    print("Posting transaction bundle to Medplum...")
    result = await medplum.transaction(bundle)
    created = sum(
        1 for e in result.get("entry", [])
        if str((e.get("response") or {}).get("status", "")).startswith(("200", "201"))
    )
    print(f"\nMedplum transaction complete: {created}/{len(bundle['entry'])} entries OK.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Medplum with rich clinical and scheduling FHIR data")
    parser.add_argument("--dry-run", action="store_true", help="Build and print the bundle without sending")
    args = parser.parse_args()
    _load_env()
    from src.logging_setup import setup_logging
    setup_logging()
    asyncio.run(_run(args.dry_run))


if __name__ == "__main__":
    main()
