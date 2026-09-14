# tests/test_workflows.py — Milestone: workflow engine + notifications (§5.28/5.30)
from datetime import datetime, timedelta, timezone

from src.workflows import engine, notifications


async def test_notify_records_communication(fake_medplum):
    res = await notifications.notify("pat1", "hello", category="Reminder")
    assert res["record"]["ok"] is True
    assert fake_medplum.communications[-1]["category"] == "Reminder"


async def test_on_appointment_booked_schedules(fake_medplum):
    r = await engine.on_appointment_booked(
        patient_id="pat1", appointment_id="a1",
        start=(datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
        doctor_name="Rao",
    )
    assert r["confirmation_sent"] is True and r.get("reminder_task_id")
    assert any(c["category"] == "Appointment confirmation" for c in fake_medplum.communications)
    assert fake_medplum.tasks[0]["code"] == "appointment-reminder"


async def test_process_due_tasks_executes_and_completes(fake_medplum):
    # queue a reminder already due
    await fake_medplum.create_task(
        "appointment-reminder", patient_id="pat1", focus_ref="Appointment/a1",
        due=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        description="Reminder: your appointment is soon.",
    )
    counts = await engine.process_due_tasks()
    assert counts["due"] == 1 and counts["completed"] == 1
    assert fake_medplum.tasks[0]["resource"]["status"] == "completed"
    assert any(c["category"] == "Appointment reminder" for c in fake_medplum.communications)


async def test_future_tasks_are_skipped(fake_medplum):
    await fake_medplum.create_task(
        "appointment-reminder", patient_id="pat1", focus_ref="Appointment/a1",
        due=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        description="later",
    )
    counts = await engine.process_due_tasks()
    assert counts["due"] == 0 and counts["skipped"] == 1


async def test_notify_no_ehr(no_medplum):
    res = await notifications.notify("pat1", "hello")
    assert res["record"]["ok"] is False
