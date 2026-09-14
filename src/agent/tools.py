# src/agent/tools.py
"""LLM-facing function-calling specifications (OpenAI/Groq tool schema).

Keep these in sync with src/agent/schemas.py (the Pydantic validators) and with
schemas/*.json (the canonical entity shapes). Server-owned fields such as
patient_id and idempotency_key are intentionally NOT exposed to the model.
"""

TOOLS_SCHEMA = [
    {
        "name": "search_doctors",
        "description": (
            "Find doctors, optionally filtered by clinical specialty. Map reported "
            "symptoms to a specialty (knee/shoulder/back -> Orthopedics, chest pain -> "
            "Cardiology, skin -> Dermatology). Returns doctor_id and hospital_id needed to book."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "specialty": {"type": "string", "description": "e.g. Orthopedics, Cardiology, Dermatology"}
            },
            "required": [],
        },
    },
    {
        "name": "check_availability",
        "description": "List open appointment slots for a doctor. Returns slot_id and hospital_id for booking.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string", "description": "Doctor UUID from search_doctors"},
                "date": {"type": "string", "description": "Preferred date YYYY-MM-DD (optional)"},
                "time_range": {
                    "type": "object",
                    "properties": {
                        "start_time": {"type": "string", "description": "HH:MM"},
                        "end_time": {"type": "string", "description": "HH:MM"},
                    },
                },
                "appointment_type": {"type": "string"},
            },
            "required": ["doctor_id"],
        },
    },
    {
        "name": "create_appointment",
        "description": (
            "Book a confirmed slot and verify it against the external EHR. Only announce "
            "confirmation to the patient if the result has verification_status = EHR_VERIFIED."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string"},
                "hospital_id": {"type": "string"},
                "slot_id": {"type": "string", "description": "Slot UUID from check_availability"},
                "appointment_type": {"type": "string"},
            },
            "required": ["doctor_id", "hospital_id", "slot_id"],
        },
    },
    {
        "name": "reschedule_appointment",
        "description": "Move an existing appointment to a new open slot.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string"},
                "slot_id": {"type": "string", "description": "New slot UUID from check_availability"},
                "reason_code": {"type": "string"},
            },
            "required": ["appointment_id", "slot_id"],
        },
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an existing appointment and free its slot.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string"},
                "reason_code": {"type": "string"},
            },
            "required": ["appointment_id"],
        },
    },
    {
        "name": "get_questionnaire",
        "description": (
            "Load the doctor's pre-visit questionnaire after a booking is verified. "
            "Ask the returned questions one at a time, then call submit_questionnaire_response."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string"},
            },
            "required": ["doctor_id"],
        },
    },
    {
        "name": "submit_questionnaire_response",
        "description": "Submit all collected pre-visit questionnaire answers for an appointment.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string"},
                "answers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question_id": {"type": "string"},
                            "raw_patient_input": {"type": "string"},
                            "structured_value": {
                                "type": ["string", "number", "boolean", "array", "null"]
                            },
                        },
                        "required": ["question_id", "raw_patient_input"],
                    },
                },
            },
            "required": ["appointment_id", "answers"],
        },
    },
    {
        "name": "lookup_patient",
        "description": (
            "Resolve the caller against the patient record by phone (defaults to the caller's "
            "number). Use if the caller isn't yet identified before booking."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "E.164 phone; optional, defaults to caller"},
            },
            "required": [],
        },
    },
    {
        "name": "register_patient",
        "description": (
            "Create a new patient record when lookup_patient found no existing patient. Collect "
            "first name, last name, and date of birth (YYYY-MM-DD) from the caller first. Required "
            "before booking for a first-time caller."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "phone": {"type": "string", "description": "E.164; optional, defaults to caller"},
                "date_of_birth": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["first_name", "last_name"],
        },
    },
    {
        "name": "get_appointment",
        "description": (
            "List the caller's existing appointments. Call this before reschedule_appointment or "
            "cancel_appointment when the patient refers to an appointment they already have, and to "
            "pick which one if there are several."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Status filter, default 'booked'"},
            },
            "required": [],
        },
    },
    {
        "name": "transfer_to_human",
        "description": "Hand off to a human agent for anything you cannot handle or on explicit request.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "context_summary": {"type": "string"},
            },
            "required": ["reason"],
        },
    },
    {
        "name": "end_call",
        "description": (
            "Hang up the call once the conversation is complete: the appointment is booked and "
            "any questionnaire is finished and the patient has nothing else, or the patient says "
            "goodbye. Say a brief closing line in the SAME turn as calling this."
        ),
        "parameters": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": [],
        },
    },
]
