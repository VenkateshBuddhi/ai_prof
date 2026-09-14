# tests/test_api.py — Milestone: FastAPI REST layer (offline, TestClient + FakeMedplum)
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_list_doctors(fake_medplum):
    r = client.get("/api/doctors")
    assert r.status_code == 200
    body = r.json()
    assert body[0]["specialty"] == "Cardiology"
    assert body[0]["hospital_id"] == "loc1"


def test_doctor_slots(fake_medplum):
    r = client.get("/api/doctors/doc1/slots")
    assert r.status_code == 200
    assert r.json()[0]["is_available"] is True


def test_doctor_questionnaire(fake_medplum):
    r = client.get("/api/doctors/doc1/questionnaire")
    assert r.status_code == 200 and r.json()["questionnaire_id"] == "q1"


def test_create_appointment_and_workflow(fake_medplum):
    r = client.post("/api/appointments", json={
        "patient_id": "pat-known", "doctor_id": "doc1", "hospital_id": "loc1", "slot_id": "slot1"})
    assert r.status_code == 200
    assert r.json()["verification_status"] == "EHR_VERIFIED"
    # post-booking workflow fired via the API path too
    assert any(t["code"] == "appointment-reminder" for t in fake_medplum.tasks)


def test_list_appointments_patient_scope(fake_medplum):
    r = client.get("/api/appointments", headers={"X-Role": "patient", "X-Patient-Id": "pat-known"})
    assert r.status_code == 200
    a = r.json()[0]
    assert a["doctor_name"] == "Dr. Priya Rao" and a["status"] == "confirmed"


def test_register_patient(fake_medplum):
    r = client.post("/api/patients", json={"first_name": "Ven", "last_name": "K", "date_of_birth": "2006-03-17"})
    assert r.status_code == 200 and r.json()["patient_id"] == "pat-ven"


def test_ops_endpoints(fake_medplum):
    assert client.get("/api/hospitals").json()[0]["name"].startswith("St. Mary")
    assert client.get("/api/workflows").status_code == 200
    assert client.get("/api/audit").json()[0]["resource_type"] == "Patient"


def test_kpis_on_the_fly_aggregation(fake_medplum):
    kpis = client.get("/api/kpis").json()
    assert kpis["total_doctors"] == 3
    # rates/averages reduced from the fake AuditEvent summary (duration 1.4, all tools ok)
    assert kpis["avg_ai_latency"] == 1.4
    assert kpis["ehr_integration_success_rate"] == 100.0
    assert kpis["human_escalation_rate"] == 0.0
    assert kpis["ai_calls_total"] == 1


def test_aggregate_audit_unit():
    from src.api.routers.ops import _aggregate_audit
    events = [
        {"outcomeDesc": '{"duration_s": 2.0, "tool_success": 2, "tool_failure": 0, "tools": {"search_doctors": 1}}'},
        {"outcomeDesc": '{"duration_s": 4.0, "tool_success": 1, "tool_failure": 1, "tools": {"transfer_to_human": 1}}'},
        {"outcomeDesc": "{}"},          # no metrics -> skipped
        {"outcomeDesc": "not json"},     # malformed -> skipped
    ]
    agg = _aggregate_audit(events)
    assert agg["calls"] == 2
    assert agg["avg_latency"] == 3.0                 # (2+4)/2
    assert agg["escalation_rate"] == 50.0            # 1 of 2 escalated
    assert agg["capability_success_rate"] == 75.0    # 3 success / 4 total


def test_ehr_unavailable_returns_503(no_medplum):
    assert client.get("/api/doctors").status_code == 503
