# src/workflows/engine.py
"""Workflow engine (PRD 5.28).

Two halves:
  * schedulers — called inline when something happens (e.g. a booking) to send an
    immediate notification and enqueue future jobs as FHIR Tasks;
  * `process_due_tasks()` — run by the standalone runner: find Tasks whose due
    time has passed and execute them (send the notification), tracking status.

Workflow codes (Task.code): appointment-reminder, questionnaire-reminder.
Immediate confirmations are sent directly (not enqueued).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from src.database.medplum_client import get_medplum_client, _human_time
from src.workflows import notifications

logger = logging.getLogger("WorkflowEngine")

# Lead time before the appointment to send the reminder (minutes). Default 24h;
# set small (e.g. 2) to see reminders fire during a demo.
REMINDER_LEAD_MINUTES = int(os.environ.get("REMINDER_LEAD_MINUTES", "1440"))


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ schedulers
async def on_appointment_booked(
    *, patient_id: str, appointment_id: str, start: Optional[str],
    doctor_name: Optional[str] = None, organization_id: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Post-booking workflow: immediate confirmation + scheduled reminder."""
    medplum = get_medplum_client()
    if not medplum:
        return {"scheduled": False, "error": "ehr_unavailable"}

    when = _human_time(start) if start else "your scheduled time"
    with_who = f" with Dr. {doctor_name}" if doctor_name else ""
    result: Dict[str, Any] = {}

    # 1. Immediate confirmation.
    await notifications.notify(
        patient_id,
        f"Your appointment{with_who} is confirmed for {when}.",
        organization_id=organization_id, phone=phone, category="Appointment confirmation",
    )
    result["confirmation_sent"] = True

    # 2. Reminder Task, due REMINDER_LEAD_MINUTES before the start (if still future).
    start_dt = _parse_iso(start)
    if start_dt:
        due_dt = start_dt - timedelta(minutes=REMINDER_LEAD_MINUTES)
        if due_dt <= datetime.now(timezone.utc):
            due_dt = datetime.now(timezone.utc) + timedelta(minutes=1)  # near-term for demos
        task_id = await medplum.create_task(
            "appointment-reminder",
            patient_id=patient_id,
            focus_ref=f"Appointment/{appointment_id}",
            due=due_dt.isoformat(),
            description=f"Reminder: your appointment{with_who} is on {when}.",
        )
        result["reminder_task_id"] = task_id
        result["reminder_due"] = due_dt.isoformat()
    return result


async def on_booking_failed(*, patient_id: Optional[str], reason: str,
                            organization_id: Optional[str] = None, phone: Optional[str] = None) -> None:
    """Failure workflow: let the patient know a human will follow up."""
    if not patient_id:
        return
    await notifications.notify(
        patient_id,
        "We couldn't complete your booking automatically. A staff member will follow up shortly.",
        organization_id=organization_id, phone=phone, category="Booking failure",
    )
    logger.info("booking-failed workflow ran (reason=%s)", reason)


# ------------------------------------------------------------------- execution
async def process_due_tasks() -> Dict[str, int]:
    """Execute every workflow Task whose due time has passed. Returns counts."""
    medplum = get_medplum_client()
    if not medplum:
        return {"error": 1}

    now = datetime.now(timezone.utc)
    counts = {"due": 0, "completed": 0, "failed": 0, "skipped": 0}
    for task in await medplum.list_open_tasks():
        due = _parse_iso(task.get("due"))
        if not due or due > now:
            counts["skipped"] += 1
            continue
        counts["due"] += 1
        try:
            ok = await _execute(task)
            if ok:
                await medplum.set_task_status(task["resource"], "completed")
                counts["completed"] += 1
            else:
                # transient failure — leave 'requested' so the next poll retries.
                counts["failed"] += 1
        except Exception as e:  # noqa: BLE001
            logger.error("task %s execution error: %s", task.get("id"), type(e).__name__)
            await medplum.set_task_status(task["resource"], "failed", note=type(e).__name__)
            counts["failed"] += 1
    return counts


async def _execute(task: Dict[str, Any]) -> bool:
    """Dispatch a due Task. Reminder/notification tasks send their description."""
    code = task.get("code")
    patient_ref = task.get("for") or ""
    patient_id = patient_ref.split("/", 1)[1] if patient_ref.startswith("Patient/") else None
    message = task.get("description") or "You have a reminder from your clinic."

    if code in ("appointment-reminder", "questionnaire-reminder"):
        res = await notifications.notify(patient_id, message, category="Appointment reminder")
        return bool((res.get("record") or {}).get("ok"))

    logger.warning("unknown workflow code: %s", code)
    return True  # nothing to do; don't loop forever
