# tests/test_schemas.py — Milestone: agent capability schemas (input validation)
import pytest
from pydantic import ValidationError

from src.agent import schemas


def test_search_doctors_specialty_optional():
    assert schemas.SearchDoctorsInput().specialty is None
    assert schemas.SearchDoctorsInput(specialty="Cardiology").specialty == "Cardiology"


def test_create_appointment_requires_ids():
    ok = schemas.CreateAppointmentInput(doctor_id="d", hospital_id="h", slot_id="s")
    assert ok.appointment_type == "Standard"  # default
    with pytest.raises(ValidationError):
        schemas.CreateAppointmentInput(doctor_id="d", hospital_id="h")  # missing slot_id


def test_register_patient_requires_names():
    schemas.RegisterPatientInput(first_name="John", last_name="Doe")
    with pytest.raises(ValidationError):
        schemas.RegisterPatientInput(first_name="John")  # missing last_name


def test_submit_questionnaire_nested_answers():
    inp = schemas.SubmitQuestionnaireResponseInput(
        appointment_id="a1",
        answers=[{"question_id": "q1", "raw_patient_input": "Yes", "structured_value": True}],
    )
    assert inp.answers[0].question_id == "q1"
    assert inp.answers[0].structured_value is True


def test_check_availability_time_range_optional():
    inp = schemas.CheckAvailabilityInput(doctor_id="d", date="2026-09-18")
    assert inp.time_range is None
