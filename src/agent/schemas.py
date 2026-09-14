# src/agent/schemas.py
"""Pydantic v2 input models for every agent tool.

These mirror schemas/*.json but expose ONLY the fields the LLM should supply.
Server-owned fields (patient_id, tenant_id, idempotency_key) are injected from
the AgentSession by the capability layer, never trusted from the model.

The executor validates raw LLM arguments through these before any DB call.
"""
from typing import List, Optional, Any
from pydantic import BaseModel, Field


class TimeRange(BaseModel):
    start_time: Optional[str] = None  # "HH:MM"
    end_time: Optional[str] = None


class SearchDoctorsInput(BaseModel):
    specialty: Optional[str] = Field(
        default=None, description="Clinical specialty, e.g. Orthopedics, Cardiology, Dermatology"
    )


class CheckAvailabilityInput(BaseModel):
    doctor_id: str = Field(description="Doctor UUID from search_doctors")
    date: Optional[str] = Field(default=None, description="Preferred date, YYYY-MM-DD")
    time_range: Optional[TimeRange] = None
    appointment_type: Optional[str] = None


class CreateAppointmentInput(BaseModel):
    doctor_id: str
    hospital_id: str
    slot_id: str = Field(description="Slot UUID from check_availability")
    appointment_type: Optional[str] = "Standard"


class RescheduleAppointmentInput(BaseModel):
    appointment_id: str
    slot_id: str = Field(description="New slot UUID from check_availability")
    reason_code: Optional[str] = None


class CancelAppointmentInput(BaseModel):
    appointment_id: str
    reason_code: Optional[str] = None


class GetQuestionnaireInput(BaseModel):
    doctor_id: str = Field(description="Doctor UUID whose pre-visit questionnaire to load")


class QuestionnaireAnswer(BaseModel):
    question_id: str
    raw_patient_input: str
    structured_value: Optional[Any] = None


class SubmitQuestionnaireResponseInput(BaseModel):
    appointment_id: str
    answers: List[QuestionnaireAnswer]


class LookupPatientInput(BaseModel):
    phone: Optional[str] = Field(
        default=None, description="Caller phone in E.164; defaults to the current caller's number"
    )


class RegisterPatientInput(BaseModel):
    first_name: str
    last_name: str
    phone: Optional[str] = Field(default=None, description="E.164; defaults to the caller's number")
    date_of_birth: Optional[str] = Field(default=None, description="Date of birth as YYYY-MM-DD")


class GetAppointmentInput(BaseModel):
    status: Optional[str] = Field(
        default="booked", description="Appointment status filter, e.g. booked (default)"
    )


class TransferToHumanInput(BaseModel):
    reason: str
    context_summary: Optional[str] = None


class EndCallInput(BaseModel):
    reason: Optional[str] = Field(
        default=None, description="Why the call is ending, e.g. 'booking complete' or 'patient said goodbye'"
    )
