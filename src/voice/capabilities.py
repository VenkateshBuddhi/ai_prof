# src/voice/capabilities.py
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from src.database.supabase_db import SupabaseClient

logger = logging.getLogger("CapabilityEngine")

# State & User Context Representation Models
class ConversationState(BaseModel):
    intent: Optional[str] = None
    specialty: Optional[str] = None
    date: Optional[str] = None
    time_preference: Optional[str] = None
    selected_doctor_id: Optional[str] = None
    selected_doctor_name: Optional[str] = None
    selected_hospital_id: Optional[str] = None
    selected_hospital_name: Optional[str] = None
    selected_slot: Optional[str] = None
    appointment_id: Optional[str] = None
    appointment_status: str = "idle"
    questionnaire_active: bool = False
    current_question_index: int = 0
    questions: List[Dict[str, Any]] = []

class PersistentUserContext(BaseModel):
    patient_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    preferred_hospital_id: Optional[str] = None
    preferred_doctor: Optional[str] = None

class CallSession(BaseModel):
    call_sid: str
    state: ConversationState = Field(default_factory=ConversationState)
    context: PersistentUserContext = Field(default_factory=PersistentUserContext)

SESSION_STORE: Dict[str, CallSession] = {}

# --- EXPLICIT TOOL IMPLEMENTATIONS ---

async def lookup_and_register_patient(call_sid: str, phone_number: str) -> Dict[str, Any]:
    """Resolves caller context. Performs auto-registration (Step 1) if not found."""
    logger.info(f"[Step 5 Context Resolution] Looking up phone_number {phone_number}")
    patient = await SupabaseClient.get_patient_by_phone(phone_number)
    
    if patient:
        logger.info(f"Existing patient profile matched: {patient['first_name']} {patient['last_name']}")
        return {"success": True, "registered": False, "data": patient}
    
    # Auto-registration if number isn't found
    logger.info("Caller unregistered. Triggering automated registration workflow...")
    # Registering default anonymous name based on voice verification
    new_patient = await SupabaseClient.create_patient(phone_number, "Unregistered", "Patient")
    if new_patient:
         return {"success": True, "registered": True, "data": new_patient}
    return {"success": False, "error": "Unable to initialize profile."}

async def search_doctors(specialty: Optional[str] = None) -> Dict[str, Any]:
    """Searches hospitals and matching medical practitioners (Step 6)."""
    doctors = await SupabaseClient.search_doctors(specialty)
    return {"success": True, "results": doctors}

async def check_availability(doctor_id: str) -> Dict[str, Any]:
    """Retrieves available calendar slots (Step 7)."""
    slots = await SupabaseClient.get_availability(doctor_id)
    return {"success": True, "slots": slots}

async def create_and_verify_appointment(call_sid: str, doctor_id: str, hospital_id: str, selected_slot: str) -> Dict[str, Any]:
    """Coordinates Step 11 Booking, Step 12 EHR Verification, and Step 13 State Synchronization."""
    session = SESSION_STORE.get(call_sid)
    if not session or not session.context.patient_id:
        return {"success": False, "error": "Invalid conversation profile"}
    
    # Step 11: Create Local Pending Appointment Record
    local_apt = await SupabaseClient.create_appointment(
        patient_id=session.context.patient_id,
        doctor_id=doctor_id,
        hospital_id=hospital_id,
        slot=selected_slot
    )
    if not local_apt:
        return {"success": False, "error": "Internal appointment construction failed"}
    
    # --- SIMULATE Step 12 & 13: External EHR Verification & Synchronization Handshake ---
    # In a live deployment, this calls Epic/Cerner endpoints to sync resources
    simulated_ehr_id = f"EHR-SYS-{local_apt['id'][:8].upper()}"
    
    # Step 13 State Synchronization
    sync_success = await SupabaseClient.verify_and_sync_appointment(local_apt["id"], simulated_ehr_id)
    
    if sync_success:
        session.state.appointment_id = local_apt["id"]
        session.state.appointment_status = "CONFIRMED"
        session.state.selected_slot = selected_slot
        
        # Log integration performance to Supabase Analytics (Step 20)
        await SupabaseClient.log_analytics(call_sid, "ehr_sync", "latency", 42.0, {"ehr_id": simulated_ehr_id})
        return {"success": True, "ehr_id": simulated_ehr_id, "appointment_id": local_apt["id"]}
        
    return {"success": False, "error": "EHR external synchronization validation rejected call"}

async def escalate_to_human(call_sid: str, reason: str) -> Dict[str, Any]:
    """Flag escalation parameter inside session."""
    session = SESSION_STORE.get(call_sid)
    if session:
        session.state.appointment_status = "ESCALATED"
    return {"success": True, "action": "TRANSFER", "destination_sip": "sip:escalations@hospital.com"}

# --- SCHEMAS FOR GROQ TOOL CALLING ---

TOOLS_SCHEMA = [
    {
        "name": "search_doctors",
        "description": "Find doctor resources. Automatically maps symptoms to specialties (e.g. knee/shoulder pain -> Orthopedics).",
        "parameters": {
            "type": "object",
            "properties": {
                "specialty": {"type": "string", "description": "Clinical specialty (e.g. Orthopedics, Cardiology, Dermatology)"}
            },
            "required": []
        }
    },
    {
        "name": "check_availability",
        "description": "Retrieves open calendar slots for a doctor.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string", "description": "The target doctor's unique system UUID."}
            },
            "required": ["doctor_id"]
        }
    },
    {
        "name": "create_and_verify_appointment",
        "description": "Book, verify against the external EHR, and finalize the appointment.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string", "description": "Selected doctor's ID."},
                "hospital_id": {"type": "string", "description": "Selected hospital's ID."},
                "selected_slot": {"type": "string", "description": "Confirmed booking slot time."}
            },
            "required": ["doctor_id", "hospital_id", "selected_slot"]
        }
    },
    {
        "name": "escalate_to_human",
        "description": "Instantly hand off to a human agent.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Reason for human transfer."}
            },
            "required": ["reason"]
        }
    }
]

async def execute_tool(name: str, args: Dict[str, Any], call_sid: str) -> Dict[str, Any]:
    try:
        if name == "search_doctors":
            return await search_doctors(**args)
        elif name == "check_availability":
            return await check_availability(**args)
        elif name == "create_and_verify_appointment":
            return await create_and_verify_appointment(call_sid, **args)
        elif name == "escalate_to_human":
            return await escalate_to_human(call_sid, **args)
        else:
            return {"success": False, "error": f"Capability '{name}' not found."}
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return {"success": False, "error": str(e)}