# src/workflows/notifications.py
"""Notification delivery (PRD 5.30).

Every notification is **recorded** in Medplum as a FHIR `Communication` under the
patient's compartment (auditable, needs no paid service). Optionally it is also
delivered over a real channel:

  * `record`  (default, always on) — the Medplum Communication above.
  * `sms`     — Twilio REST SMS, only if TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN /
                TWILIO_PHONE_NUMBER are set AND a recipient phone is known.

Configure channels with NOTIFY_CHANNELS (comma-separated), default "record".
Privacy: logs never include the message body.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

from src.database.medplum_client import get_medplum_client

logger = logging.getLogger("Notifications")


def _channels() -> set[str]:
    raw = os.environ.get("NOTIFY_CHANNELS", "record")
    return {c.strip().lower() for c in raw.split(",") if c.strip()} or {"record"}


async def notify(
    patient_id: Optional[str],
    message: str,
    *,
    organization_id: Optional[str] = None,
    phone: Optional[str] = None,
    category: str = "Appointment notification",
) -> dict:
    """Send/record a notification to a patient. Returns a per-channel result map."""
    results: dict = {}
    channels = _channels()

    # record channel (always) — FHIR Communication in the patient compartment.
    if "record" in channels or True:
        medplum = get_medplum_client()
        if medplum and patient_id:
            comm_id = await medplum.create_communication(
                patient_id, message, organization_id=organization_id, category_text=category,
            )
            results["record"] = {"ok": bool(comm_id), "communication_id": comm_id}
        else:
            results["record"] = {"ok": False, "error": "no_medplum_or_patient"}

    # sms channel (optional) — Twilio REST, best-effort.
    if "sms" in channels:
        results["sms"] = await _send_sms(phone, message)

    logger.info("notification sent (patient=%s, channels=%s, ok=%s)",
                patient_id, sorted(channels), {k: v.get("ok") for k, v in results.items()})
    return results


async def _send_sms(phone: Optional[str], message: str) -> dict:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_ = os.environ.get("TWILIO_PHONE_NUMBER")
    if not (sid and token and from_):
        return {"ok": False, "error": "twilio_not_configured"}
    if not phone:
        return {"ok": False, "error": "no_recipient_phone"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                data={"To": phone, "From": from_, "Body": message},
                auth=(sid, token),
            )
        ok = resp.status_code in (200, 201)
        if not ok:
            logger.error("Twilio SMS failed: HTTP %s", resp.status_code)
        return {"ok": ok, "status": resp.status_code}
    except Exception as e:  # noqa: BLE001
        logger.error("Twilio SMS error: %s", type(e).__name__)
        return {"ok": False, "error": type(e).__name__}
