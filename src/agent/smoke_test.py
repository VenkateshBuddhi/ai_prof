# src/agent/smoke_test.py
"""Exercise every capability directly against Medplum, WITHOUT the LLM.

Validates the tool + FHIR layer independently of Groq, so you can confirm
search/book/reschedule/cancel/questionnaire work before wiring the model or
LiveKit.

Run (needs MEDPLUM_CLIENT_ID/SECRET and a seeded Medplum project):
    uv run python -m src.agent.smoke_test --phone +15550192834
"""
import argparse
import asyncio
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, ".env")


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


def _show(label, result):
    print(f"\n=== {label} ===")
    print(json.dumps(result, indent=2, default=str)[:1200])


async def _run(phone: str, specialty: str) -> None:
    from src.database.medplum_client import get_medplum_client
    from src.agent.state import AgentSession
    from src.agent.executor import execute_tool

    medplum = get_medplum_client()
    if not medplum:
        print("Medplum not configured (set MEDPLUM_CLIENT_ID/SECRET). Aborting.")
        return

    patient = await medplum.find_patient_by_phone(phone)
    if not patient or not patient.get("patient_id"):
        print(f"No FHIR Patient with telecom {phone}. Seed one in Medplum first.")
        return

    session = AgentSession()
    session.context.fhir_patient_id = patient["patient_id"]
    session.context.fhir_organization_id = patient.get("organization_id")
    print(f"Patient: {patient.get('first_name')} {patient.get('last_name')} "
          f"(Patient/{patient['patient_id']}, org={patient.get('organization_id')})")

    # 1. Find a doctor.
    docs = await execute_tool("search_doctors", {"specialty": specialty}, session)
    _show(f"search_doctors({specialty})", docs)
    if not docs.get("results"):
        print("No PractitionerRole matches; seed doctors in Medplum. Aborting.")
        return
    doctor = docs["results"][0]
    doctor_id = doctor["doctor_id"]
    hospital_id = doctor["hospitals"]["id"]

    # 2. Availability.
    avail = await execute_tool("check_availability", {"doctor_id": doctor_id}, session)
    _show("check_availability", {"count": avail.get("count"), "first": avail.get("slots", [])[:2]})
    if not avail.get("slots"):
        print("No free Slots for this practitioner. Aborting.")
        return
    slot_id = avail["slots"][0]["slot_id"]

    # 3. Book.
    booking = await execute_tool(
        "create_appointment",
        {"doctor_id": doctor_id, "hospital_id": hospital_id, "slot_id": slot_id},
        session,
    )
    _show("create_appointment", booking)
    if not booking.get("success"):
        print("Booking failed. Aborting.")
        return
    appointment_id = booking["appointment_id"]

    # 4. Questionnaire.
    q = await execute_tool("get_questionnaire", {"doctor_id": doctor_id}, session)
    _show("get_questionnaire", q)
    if q.get("found"):
        answers = [
            {"question_id": item["question_id"], "raw_patient_input": "Yes", "structured_value": True}
            for item in q["questions"]
        ]
        submitted = await execute_tool(
            "submit_questionnaire_response",
            {"appointment_id": appointment_id, "answers": answers},
            session,
        )
        _show("submit_questionnaire_response", submitted)

    # 5. Reschedule to another free slot.
    avail2 = await execute_tool("check_availability", {"doctor_id": doctor_id}, session)
    other = [s for s in avail2.get("slots", []) if s["slot_id"] != slot_id]
    if other:
        resched = await execute_tool(
            "reschedule_appointment",
            {"appointment_id": appointment_id, "slot_id": other[0]["slot_id"]},
            session,
        )
        _show("reschedule_appointment", resched)

    # 6. Cancel.
    cancelled = await execute_tool(
        "cancel_appointment",
        {"appointment_id": appointment_id, "reason_code": "smoke_test"},
        session,
    )
    _show("cancel_appointment", cancelled)

    # 7. Escalation.
    esc = await execute_tool("transfer_to_human", {"reason": "smoke_test escalation"}, session)
    _show("transfer_to_human", esc)

    print("\nFinal state:")
    print(json.dumps(session.state.model_dump(), indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Medplum-backed capability smoke test")
    parser.add_argument("--phone", default="+15550192834", help="Caller phone to resolve a FHIR Patient")
    parser.add_argument("--specialty", default="Cardiology", help="Specialty to search")
    args = parser.parse_args()
    _load_env()
    from src.logging_setup import setup_logging
    setup_logging()
    asyncio.run(_run(args.phone, args.specialty))


if __name__ == "__main__":
    main()
