# src/agent/state.py
"""In-memory conversation state for the agent.

Mirrors schemas/conversational_state.json. This is intentionally in-memory
(a dict keyed by session id) for local testing; the voice path can later swap
in Redis without changing the tool/agent code, since tools only read/write
through the `AgentSession` passed to them.
"""
import uuid
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ConversationState(BaseModel):
    """Short-term turn parameters (schemas/conversational_state.json)."""
    intent: Optional[str] = None  # BOOK_APPOINTMENT | RESCHEDULE | CANCEL | COMPLETE_QUESTIONNAIRE | GENERAL_INQUIRY
    specialty: Optional[str] = None
    date: Optional[str] = None
    time_preference: Optional[str] = None  # Morning | Afternoon | Evening
    selected_hospital_id: Optional[str] = None
    selected_doctor_id: Optional[str] = None
    selected_slot_id: Optional[str] = None
    appointment_id: Optional[str] = None
    appointment_status: str = "Pending"  # Pending | Confirmed | Cancelled | Escalated | Failed
    # Pre-visit questionnaire tracking (set by get_questionnaire, used on submit).
    questionnaire_id: Optional[str] = None
    questionnaire_ref: Optional[str] = None


class PersistentUserContext(BaseModel):
    """Longer-term, non-sensitive caller context."""
    patient_id: Optional[str] = None
    tenant_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    preferred_hospital_id: Optional[str] = None
    preferred_doctor_id: Optional[str] = None
    # FHIR / Medplum identity (resolved by the LiveKit worker before the call).
    # Kept alongside the local scheduling patient_id so tools stay tenant-isolated
    # and the transcript can be written back to the correct compartment.
    fhir_patient_id: Optional[str] = None
    fhir_organization_id: Optional[str] = None


class AgentSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: ConversationState = Field(default_factory=ConversationState)
    context: PersistentUserContext = Field(default_factory=PersistentUserContext)


# Session registry (session_id -> AgentSession). Analogous to voice SESSION_STORE.
SESSION_STORE: Dict[str, AgentSession] = {}


def get_or_create_session(session_id: str) -> AgentSession:
    if session_id not in SESSION_STORE:
        SESSION_STORE[session_id] = AgentSession(session_id=session_id)
    return SESSION_STORE[session_id]
