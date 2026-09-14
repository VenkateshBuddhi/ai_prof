# tests/conftest.py
"""Shared pytest fixtures.

All tests run fully offline — no Medplum, Groq, or LiveKit network calls. The
`fake_medplum` fixture injects an in-memory stand-in for the cached Medplum
client so the tool / workflow layers exercise real logic against fake data.
"""
import json
import os

import pytest

# ChatGroq is constructed when a ConversationAgent is built; give it a dummy key
# so construction never fails (no network call happens at construction time).
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("GROQ_MODEL", "openai/gpt-oss-120b")

import src.database.medplum_client as mc  # noqa: E402
from src.agent.state import AgentSession  # noqa: E402


class FakeMedplum:
    """In-memory stand-in for MedplumClient covering every method the app calls."""

    def __init__(self):
        self.communications = []
        self.tasks = []
        self.patients = {}          # phone -> patient dict
        self.appointments = {}

    # --- identity ---
    async def find_patient_by_phone(self, phone):
        return self.patients.get(phone)

    async def create_patient(self, first_name, last_name, phone=None, *, birth_date=None, organization_id=None):
        pid = f"pat-{first_name.lower()}"
        rec = {"patient_id": pid, "organization_id": organization_id,
               "first_name": first_name, "last_name": last_name}
        if phone:
            self.patients[phone] = rec
        return rec

    # --- scheduling ---
    async def search_practitioners(self, specialty=None, organization_id=None):
        return [{
            "id": "doc1", "doctor_id": "doc1", "first_name": "Priya", "last_name": "Rao",
            "specialty": specialty or "Cardiology", "hospitals": {"id": "loc1", "name": "SMMC"},
        }]

    async def get_available_slots(self, practitioner_id, date=None, count=10):
        return [
            {"id": "slot1", "slot_id": "slot1", "doctor_id": practitioner_id, "hospital_id": "loc1",
             "start_time": "2026-09-18T09:00:00-04:00", "end_time": "2026-09-18T09:30:00-04:00",
             "slot": "Friday September 18, 09:00 AM", "status": "free"},
            {"id": "slot2", "slot_id": "slot2", "doctor_id": practitioner_id, "hospital_id": "loc1",
             "start_time": "2026-09-18T09:30:00-04:00", "end_time": "2026-09-18T10:00:00-04:00",
             "slot": "Friday September 18, 09:30 AM", "status": "free"},
        ]

    async def create_appointment(self, patient_id, practitioner_id, location_id, slot_id):
        aid = f"appt-{slot_id}"
        self.appointments[aid] = {"patient": patient_id, "slot": slot_id}
        return {"id": aid, "appointment_id": aid, "status": "booked",
                "start": "2026-09-18T09:00:00-04:00", "end": "2026-09-18T09:30:00-04:00"}

    async def reschedule_appointment(self, appointment_id, new_slot_id):
        return {"success": True, "appointment_id": appointment_id, "new_slot_id": new_slot_id,
                "new_slot": "Friday September 18, 09:30 AM", "status": "booked"}

    async def cancel_appointment(self, appointment_id, reason=None):
        return {"success": True, "appointment_id": appointment_id, "status": "cancelled"}

    async def get_appointments(self, patient_id, status="booked"):
        return [{"appointment_id": "appt-slot1", "status": status,
                 "start_time": "2026-09-18T09:00:00-04:00", "start": "Friday September 18, 09:00 AM",
                 "doctor": "Priya Rao"}]

    # --- intake ---
    async def get_questionnaire(self, practitioner_id):
        return {
            "questionnaire_id": "q1", "questionnaire_ref": "Questionnaire/q1",
            "title": "Cardiology Pre-visit Intake", "specialty": "Cardiology",
            "questions": [{"question_id": "q1", "prompt_text": "Any chest pain?",
                           "response_type": "Yes/No", "options": [], "is_required": True}],
        }

    async def save_questionnaire_response(self, appointment_id, answers, questionnaire_ref):
        return {"success": True, "response_id": "qr1", "answers_saved": len(answers)}

    # --- notifications / workflow ---
    async def create_communication(self, patient_id, transcript, *, organization_id=None,
                                   summary=None, category_text="AI voice intake transcript"):
        cid = f"comm{len(self.communications) + 1}"
        self.communications.append({"id": cid, "patient": patient_id, "text": transcript,
                                    "category": category_text})
        return cid

    async def create_task(self, code, *, patient_id, focus_ref, due, description):
        tid = f"task{len(self.tasks) + 1}"
        self.tasks.append({"id": tid, "code": code, "due": due, "for": f"Patient/{patient_id}",
                           "focus": focus_ref, "description": description,
                           "resource": {"id": tid, "status": "requested"}})
        return tid

    async def list_open_tasks(self, limit=200):
        return [t for t in self.tasks if t["resource"]["status"] == "requested"]

    async def set_task_status(self, resource, status, note=None):
        resource["status"] = status

    # --- read/list (API layer) ---
    async def search_appointments(self, *, patient_id=None, practitioner_id=None,
                                  location_id=None, status=None, count=50):
        appt = {"id": "appt-slot1", "status": "booked", "start": "2026-09-18T09:00:00-04:00",
                "participant": [{"actor": {"reference": "Patient/pat-known"}},
                                {"actor": {"reference": "Practitioner/doc1"}},
                                {"actor": {"reference": "Location/loc1"}}]}
        by_ref = {
            "Patient/pat-known": {"id": "pat-known", "name": [{"given": ["John"], "family": "Doe"}]},
            "Practitioner/doc1": {"id": "doc1", "name": [{"given": ["Priya"], "family": "Rao"}]},
            "Location/loc1": {"id": "loc1", "name": "SMMC"},
        }
        return [appt], by_ref

    async def read_appointment(self, appointment_id):
        return {"id": appointment_id, "status": "booked", "start": "2026-09-18T09:00:00-04:00", "participant": []}

    async def read_patient(self, patient_id):
        return {"id": patient_id, "name": [{"given": ["John"], "family": "Doe"}],
                "telecom": [{"system": "phone", "value": "+15550192834"}], "birthDate": "1985-04-12"}

    async def list_patients(self, organization_id=None, count=50):
        return [await self.read_patient("pat-known")]

    async def list_organizations(self, count=50):
        return [{"id": "org1", "name": "St. Mary Health Network", "active": True}]

    async def list_audit_events(self, count=50):
        summary = json.dumps({"session": "s1", "channel": "voice", "duration_s": 1.4, "llm_turns": 2,
                              "tool_calls": 3, "tool_success": 3, "tool_failure": 0,
                              "tools": {"search_doctors": 1, "create_appointment": 1}})
        return [{"id": "ae1", "type": {"display": "Application Activity"}, "recorded": "2026-09-14T00:00:00Z",
                 "agent": [{"who": {"display": "ai-prof"}}], "entity": [{"what": {"reference": "Patient/pat-known"}}],
                 "outcomeDesc": summary}]

    async def list_communications(self, patient_id=None, count=50):
        return [{"id": "c1", "subject": {"reference": "Patient/pat-known"},
                 "category": [{"text": "Appointment reminder"}],
                 "payload": [{"contentString": "Reminder"}], "sent": "2026-09-14T00:00:00Z"}]

    async def list_tasks(self, count=100):
        return self.tasks

    async def count_resources(self, resource_type, params=None):
        return {"Organization": 1, "Practitioner": 3, "Patient": 1}.get(resource_type, 0)


def _inject(client):
    mc._CLIENT = client
    mc._CLIENT_RESOLVED = True


@pytest.fixture
def fake_medplum():
    fake = FakeMedplum()
    _inject(fake)
    yield fake
    mc._CLIENT = None
    mc._CLIENT_RESOLVED = False


@pytest.fixture
def no_medplum():
    _inject(None)
    yield
    mc._CLIENT = None
    mc._CLIENT_RESOLVED = False


@pytest.fixture
def session():
    s = AgentSession()
    s.context.fhir_patient_id = "pat-known"
    s.context.fhir_organization_id = "org1"
    s.context.phone = "+15550192834"
    return s
