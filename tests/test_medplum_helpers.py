# tests/test_medplum_helpers.py — Milestone: FHIR engine pure helpers
from src.database import medplum_client as mc


def test_safe_path_strips_query():
    assert mc._safe_path("https://api.medplum.com/fhir/R4/Patient?telecom=+15550192834") \
        == "https://api.medplum.com/fhir/R4/Patient"


def test_phone_variants():
    v = mc._phone_variants("+15550192834")
    assert "+15550192834" in v and "15550192834" in v


def test_parse_patient():
    p = mc._parse_patient({
        "id": "pat1",
        "name": [{"given": ["John"], "family": "Doe"}],
        "managingOrganization": {"reference": "Organization/org9"},
    })
    assert p == {"patient_id": "pat1", "organization_id": "org9",
                 "first_name": "John", "last_name": "Doe"}


def test_human_time_parses_iso():
    out = mc._human_time("2026-09-18T09:00:00-04:00")
    assert "September" in out and "2026" not in out  # weekday/month/time, not raw ISO
    assert mc._human_time(None) == ""
    assert mc._human_time("not-a-date") == "not-a-date"  # falls back to input


def test_map_question_item_types():
    boolean = mc._map_question_item({"linkId": "q1", "text": "Chest pain?", "type": "boolean", "required": True})
    assert boolean == {"question_id": "q1", "prompt_text": "Chest pain?",
                       "response_type": "Yes/No", "options": [], "is_required": True}
    text = mc._map_question_item({"linkId": "q2", "text": "Notes", "type": "text"})
    assert text["response_type"] == "Long Text" and text["is_required"] is False


def test_first_slot_id_and_patient_ref():
    appt = {"slot": [{"reference": "Slot/s1"}],
            "participant": [{"actor": {"reference": "Patient/p1"}},
                            {"actor": {"reference": "Practitioner/d1"}}]}
    assert mc._first_slot_id(appt) == "s1"
    assert mc._patient_ref(appt) == "Patient/p1"


def test_outcome_summary_reads_operationoutcome():
    class R:
        text = "{}"
        def json(self):
            return {"resourceType": "OperationOutcome",
                    "issue": [{"severity": "error", "code": "invalid",
                               "diagnostics": "Invalid additional property \"foo\""}]}
    assert "Invalid additional property" in mc._outcome_summary(R())
