# src/database/medplum_client.py
"""Medplum (FHIR R4) data layer — the core scheduling + clinical engine.

Replaces PostgreSQL/Supabase for the agent. One client handles:
  * OAuth2 client-credentials (SYSTEM app) auth, with token caching.
  * Identity:      phone -> Patient + managing Organization (compartment).
  * Scheduling:    PractitionerRole (doctors), Slot (availability),
                   Appointment (book / reschedule / cancel).
  * Intake:        Questionnaire / QuestionnaireResponse.
  * Writeback:     call transcript as Communication / Encounter.

FHIR data-model assumptions (must exist in your Medplum project):
  * Doctors are PractitionerRole rows with `specialty`, `practitioner`
    (Practitioner) and `location` (Location = the hospital/facility).
  * Availability is `Slot` (status free/busy) whose `Schedule.actor` includes
    the Practitioner and the Location.
  * Pre-visit questionnaires are active `Questionnaire` resources whose
    title / name / useContext text names the specialty.

Privacy: never logs PHI; error logs carry the exception *type* only.

Configuration (environment):
    MEDPLUM_BASE_URL       default https://api.medplum.com
    MEDPLUM_CLIENT_ID      system app client id      (required to enable)
    MEDPLUM_CLIENT_SECRET  system app client secret  (required to enable)
"""
from __future__ import annotations

import asyncio
import logging
import re
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("MedplumClient")

IDENTIFIER_SYSTEM = "https://ai-prof.example/appointment"
APPOINTMENT_EXT_URL = "https://ai-prof.example/appointment"
WORKFLOW_SYSTEM = "https://ai-prof.example/workflow"

# Retry policy for the retryable EHR failure classes (§15.1).
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 0.5  # seconds; doubles each attempt
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _safe_path(url: str) -> str:
    """Strip query string so retry logs never leak PHI (e.g. telecom=phone)."""
    return url.split("?", 1)[0]


def _outcome_summary(resp) -> str:
    """Concise reason from a FHIR OperationOutcome (server-side validation text;
    no PHI). Falls back to a truncated body."""
    try:
        data = resp.json()
        if data.get("resourceType") == "OperationOutcome":
            parts = [
                i.get("diagnostics") or (i.get("details") or {}).get("text") or i.get("code", "")
                for i in data.get("issue", [])
            ]
            return "; ".join(p for p in parts if p)[:300] or "OperationOutcome (no detail)"
    except Exception:  # noqa: BLE001
        pass
    return (resp.text or "")[:200]


class MedplumClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str, timeout: float = 10.0):
        self._base = base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._lock = asyncio.Lock()

    @classmethod
    def from_env(cls) -> Optional["MedplumClient"]:
        client_id = os.environ.get("MEDPLUM_CLIENT_ID")
        client_secret = os.environ.get("MEDPLUM_CLIENT_SECRET")
        if not (client_id and client_secret):
            logger.warning("Medplum not configured (MEDPLUM_CLIENT_ID/SECRET missing).")
            return None
        base_url = os.environ.get("MEDPLUM_BASE_URL", "https://api.medplum.com")
        return cls(base_url, client_id, client_secret)

    # ------------------------------------------------------------------ auth
    async def _access_token(self) -> str:
        async with self._lock:
            if self._token and time.monotonic() < self._token_expiry - 30:
                return self._token
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base}/oauth2/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                )
                resp.raise_for_status()
                body = resp.json()
            self._token = body["access_token"]
            self._token_expiry = time.monotonic() + float(body.get("expires_in", 3600))
            return self._token

    async def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        token = await self._access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/fhir+json"}
        if extra:
            headers.update(extra)
        return headers

    # --------------------------------------------------------- FHIR REST core
    async def _send(
        self, method: str, url: str, *, headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None, json: Optional[Any] = None, timeout: Optional[float] = None,
    ) -> httpx.Response:
        """Single HTTP path with bounded exponential backoff on the retryable
        EHR failure classes (§15.1): connection/timeout/network errors and
        429 / 5xx responses. Non-retryable statuses (4xx) return immediately.

        Note: an instant DNS failure (no resolver) also surfaces as a transport
        error and will be retried, but retrying cannot fix broken DNS — that is
        an environment issue, not a transient one."""
        delay = _RETRY_BASE_DELAY
        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=timeout or self._timeout) as client:
                    resp = await client.request(method, url, headers=headers, params=params, json=json)
            except (httpx.TransportError, httpx.TimeoutException) as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    logger.warning("EHR %s %s failed (%s); retry %d/%d in %.1fs",
                                   method, _safe_path(url), type(e).__name__, attempt + 1, _MAX_RETRIES - 1, delay)
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise
            if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES - 1:
                logger.warning("EHR %s %s -> %d; retry %d/%d in %.1fs",
                               method, _safe_path(url), resp.status_code, attempt + 1, _MAX_RETRIES - 1, delay)
                await asyncio.sleep(delay)
                delay *= 2
                continue
            if resp.status_code >= 400:
                # Surface the FHIR OperationOutcome reason so 4xx failures are diagnosable.
                logger.error("EHR %s %s -> %d: %s",
                             method, _safe_path(url), resp.status_code, _outcome_summary(resp))
            return resp
        raise last_exc  # pragma: no cover - loop always returns or raises above

    async def _search(self, resource_type: str, params: Dict[str, Any]) -> Tuple[List[Dict], Dict[str, Dict]]:
        """Return (matched resources, {"Type/id": resource} for all incl. _include)."""
        headers = await self._headers()
        resp = await self._send("GET", f"{self._base}/fhir/R4/{resource_type}", params=params, headers=headers)
        resp.raise_for_status()
        bundle = resp.json()
        matches: List[Dict] = []
        by_ref: Dict[str, Dict] = {}
        for entry in bundle.get("entry") or []:
            res = entry.get("resource") or {}
            ref = f"{res.get('resourceType')}/{res.get('id')}"
            by_ref[ref] = res
            if (entry.get("search") or {}).get("mode", "match") == "match":
                matches.append(res)
        return matches, by_ref

    async def _read(self, resource_type: str, resource_id: str) -> Optional[Dict]:
        headers = await self._headers()
        resp = await self._send("GET", f"{self._base}/fhir/R4/{resource_type}/{resource_id}", headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def _create(self, resource: Dict, if_none_exist: Optional[str] = None) -> Optional[Dict]:
        headers = await self._headers({"If-None-Exist": if_none_exist} if if_none_exist else None)
        resp = await self._send(
            "POST", f"{self._base}/fhir/R4/{resource['resourceType']}", headers=headers, json=resource
        )
        resp.raise_for_status()
        return resp.json()

    async def _patch(self, resource_type: str, resource_id: str, ops: List[Dict]) -> Optional[Dict]:
        headers = await self._headers({"Content-Type": "application/json-patch+json"})
        resp = await self._send(
            "PATCH", f"{self._base}/fhir/R4/{resource_type}/{resource_id}", headers=headers, json=ops
        )
        resp.raise_for_status()
        return resp.json()

    async def _update(self, resource: Dict) -> Optional[Dict]:
        """Full-resource update (PUT). Medplum validates the whole resource."""
        headers = await self._headers()
        resp = await self._send(
            "PUT", f"{self._base}/fhir/R4/{resource['resourceType']}/{resource['id']}",
            headers=headers, json=resource,
        )
        resp.raise_for_status()
        return resp.json()

    async def _set_slot_status(self, slot_id: str, status: str) -> None:
        await self._patch("Slot", slot_id, [{"op": "replace", "path": "/status", "value": status}])

    async def transaction(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """POST a FHIR transaction/batch Bundle to the base endpoint."""
        headers = await self._headers()
        resp = await self._send("POST", f"{self._base}/fhir/R4", headers=headers, json=bundle, timeout=60.0)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------- identity
    async def find_patient_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        if not phone:
            return None
        try:
            headers = await self._headers()
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                for value in _phone_variants(phone):
                    resp = await client.get(
                        f"{self._base}/fhir/R4/Patient",
                        params={"telecom": value, "_count": "1"},
                        headers=headers,
                    )
                    resp.raise_for_status()
                    entries = (resp.json().get("entry")) or []
                    if entries:
                        return _parse_patient(entries[0]["resource"])
            return None
        except Exception as e:  # noqa: BLE001 - fail-open, type only
            logger.error(f"Medplum patient lookup failed: {type(e).__name__}")
            return None

    async def create_patient(
        self, first_name: str, last_name: str, phone: Optional[str] = None, *,
        birth_date: Optional[str] = None, organization_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Register a new FHIR Patient — idempotent via conditional create. Dedup
        key is the phone (telecom) when known, otherwise name + date-of-birth, so a
        caller registering again (e.g. from the browser, where there's no phone)
        matches the existing record instead of creating a duplicate."""
        valid_dob = bool(birth_date and re.match(r"^\d{4}-\d{2}-\d{2}$", birth_date))
        resource: Dict[str, Any] = {
            "resourceType": "Patient",
            "name": [{"given": [first_name] if first_name else [], "family": last_name}],
        }
        if phone:
            resource["telecom"] = [{"system": "phone", "value": phone, "use": "mobile"}]
        if valid_dob:
            resource["birthDate"] = birth_date
        if organization_id:
            resource["managingOrganization"] = {"reference": f"Organization/{organization_id}"}

        if phone:
            if_none = f"telecom={phone}"
        else:
            parts = []
            if last_name:
                parts.append(f"family={last_name}")
            if first_name:
                parts.append(f"given={first_name}")
            if valid_dob:
                parts.append(f"birthdate={birth_date}")
            if_none = "&".join(parts) or None

        created = await self._create(resource, if_none_exist=if_none)
        return _parse_patient(created) if created else None

    # ------------------------------------------------------------ scheduling
    async def search_practitioners(
        self, specialty: Optional[str] = None, organization_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "active": "true",
            "_count": "20",
            "_include": ["PractitionerRole:practitioner", "PractitionerRole:location"],
        }
        if specialty:
            params["specialty:text"] = specialty
        if organization_id:
            params["organization"] = f"Organization/{organization_id}"

        matches, by_ref = await self._search("PractitionerRole", params)
        results: List[Dict[str, Any]] = []
        for role in matches:
            prac = by_ref.get((role.get("practitioner") or {}).get("reference", ""), {})
            loc_ref = ((role.get("location") or [{}])[0]).get("reference", "")
            loc = by_ref.get(loc_ref, {})
            name = (prac.get("name") or [{}])[0]
            specialty_cc = (role.get("specialty") or [{}])[0]
            results.append({
                "id": prac.get("id") or role.get("id"),
                "doctor_id": prac.get("id") or role.get("id"),
                "first_name": (name.get("given") or [None])[0],
                "last_name": name.get("family"),
                "specialty": specialty_cc.get("text") or _first_display(specialty_cc),
                "hospitals": {
                    "id": loc_ref.split("/")[-1] if loc_ref else None,
                    "name": loc.get("name") or "Clinic",
                },
            })
        return results

    async def get_available_slots(
        self, practitioner_id: str, date: Optional[str] = None, count: int = 10
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "schedule.actor": f"Practitioner/{practitioner_id}",
            "status": "free",
            "_sort": "start",
            "_count": str(count),
            "_include": "Slot:schedule",
        }
        if date:
            params["start"] = [f"ge{date}T00:00:00Z", f"le{date}T23:59:59Z"]

        matches, by_ref = await self._search("Slot", params)
        results: List[Dict[str, Any]] = []
        for slot in matches:
            schedule = by_ref.get((slot.get("schedule") or {}).get("reference", ""), {})
            location_id = None
            for actor in schedule.get("actor", []):
                ref = actor.get("reference", "")
                if ref.startswith("Location/"):
                    location_id = ref.split("/")[-1]
            results.append({
                "id": slot.get("id"),
                "slot_id": slot.get("id"),
                "doctor_id": practitioner_id,
                "hospital_id": location_id,
                "start_time": slot.get("start"),
                "end_time": slot.get("end"),
                "slot": _human_time(slot.get("start")),
                "status": "free",
            })
        return results

    async def create_appointment(
        self, patient_id: str, practitioner_id: str, location_id: Optional[str], slot_id: str
    ) -> Optional[Dict[str, Any]]:
        slot = await self._read("Slot", slot_id)
        if not slot:
            return None
        if slot.get("status") == "busy":
            return {"error": "slot_unavailable"}

        appointment: Dict[str, Any] = {
            "resourceType": "Appointment",
            "status": "booked",
            "slot": [{"reference": f"Slot/{slot_id}"}],
            "start": slot.get("start"),
            "end": slot.get("end"),
            "participant": [
                {"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"},
                {"actor": {"reference": f"Practitioner/{practitioner_id}"}, "status": "accepted"},
            ],
            "identifier": [{"system": IDENTIFIER_SYSTEM, "value": f"{patient_id}-{slot_id}"}],
        }
        if location_id:
            appointment["participant"].append(
                {"actor": {"reference": f"Location/{location_id}"}, "status": "accepted"}
            )

        # Exactly-once: conditional create on the identifier (replaces the SQL
        # idempotency_key unique index).
        created = await self._create(
            appointment,
            if_none_exist=f"identifier={IDENTIFIER_SYSTEM}|{patient_id}-{slot_id}",
        )
        if not created:
            return None
        await self._set_slot_status(slot_id, "busy")
        return {
            "id": created.get("id"),
            "appointment_id": created.get("id"),
            "status": created.get("status", "booked"),
            "start": created.get("start") or slot.get("start"),
            "end": created.get("end") or slot.get("end"),
        }

    async def reschedule_appointment(self, appointment_id: str, new_slot_id: str) -> Dict[str, Any]:
        appt = await self._read("Appointment", appointment_id)
        if not appt:
            return {"success": False, "error": "appointment_not_found"}
        new_slot = await self._read("Slot", new_slot_id)
        if not new_slot:
            return {"success": False, "error": "slot_not_found"}
        if new_slot.get("status") == "busy":
            return {"success": False, "error": "slot_unavailable"}

        old_slot_id = _first_slot_id(appt)
        # Read-modify-PUT: mutate the fetched resource and let Medplum validate
        # the whole Appointment (more reliable than multi-op JSON Patch).
        appt["slot"] = [{"reference": f"Slot/{new_slot_id}"}]
        appt["start"] = new_slot.get("start")
        appt["end"] = new_slot.get("end")
        appt["status"] = "booked"
        await self._update(appt)

        if old_slot_id and old_slot_id != new_slot_id:
            await self._set_slot_status(old_slot_id, "free")
        await self._set_slot_status(new_slot_id, "busy")
        return {
            "success": True,
            "appointment_id": appointment_id,
            "new_slot_id": new_slot_id,
            "new_slot": _human_time(new_slot.get("start")),
            "status": "booked",
        }

    async def cancel_appointment(self, appointment_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        appt = await self._read("Appointment", appointment_id)
        if not appt:
            return {"success": False, "error": "appointment_not_found"}
        appt["status"] = "cancelled"
        if reason:
            appt["cancelationReason"] = {"text": reason}
        await self._update(appt)
        old_slot_id = _first_slot_id(appt)
        if old_slot_id:
            await self._set_slot_status(old_slot_id, "free")
        return {"success": True, "appointment_id": appointment_id, "status": "cancelled"}

    async def get_appointments(self, patient_id: str, status: str = "booked") -> List[Dict[str, Any]]:
        """List a patient's appointments (default status=booked) so the agent can
        reschedule/cancel an EXISTING appointment or disambiguate between several."""
        params: Dict[str, Any] = {
            "patient": f"Patient/{patient_id}",
            "_sort": "date",
            "_count": "20",
            "_include": "Appointment:actor",
        }
        if status:
            params["status"] = status
        matches, by_ref = await self._search("Appointment", params)
        results: List[Dict[str, Any]] = []
        for appt in matches:
            practitioner_name = None
            for part in appt.get("participant") or []:
                ref = (part.get("actor") or {}).get("reference", "")
                if ref.startswith("Practitioner/"):
                    prac = by_ref.get(ref, {})
                    name = (prac.get("name") or [{}])[0]
                    given = (name.get("given") or [None])[0]
                    practitioner_name = " ".join(filter(None, [given, name.get("family")])) or None
            results.append({
                "appointment_id": appt.get("id"),
                "status": appt.get("status"),
                "start_time": appt.get("start"),
                "start": _human_time(appt.get("start")),
                "doctor": practitioner_name,
            })
        return results

    # ----------------------------------------------------------------- intake
    async def get_questionnaire(self, practitioner_id: str) -> Optional[Dict[str, Any]]:
        # Resolve the doctor's specialty, then match an active Questionnaire.
        roles, _ = await self._search(
            "PractitionerRole", {"practitioner": f"Practitioner/{practitioner_id}", "_count": "1"}
        )
        specialty = None
        if roles:
            cc = (roles[0].get("specialty") or [{}])[0]
            specialty = cc.get("text") or _first_display(cc)

        questionnaires, _ = await self._search("Questionnaire", {"status": "active", "_count": "50"})
        chosen = None
        if specialty:
            needle = specialty.lower()
            for q in questionnaires:
                haystack = " ".join(filter(None, [q.get("title"), q.get("name"), _use_context_text(q)])).lower()
                if needle in haystack:
                    chosen = q
                    break
        if not chosen:
            return None

        return {
            "questionnaire_id": chosen.get("id"),
            "questionnaire_ref": chosen.get("url") or f"Questionnaire/{chosen.get('id')}",
            "title": chosen.get("title"),
            "specialty": specialty,
            "questions": [_map_question_item(it) for it in (chosen.get("item") or [])],
        }

    async def save_questionnaire_response(
        self, appointment_id: str, answers: List[Dict[str, Any]], questionnaire_ref: Optional[str]
    ) -> Dict[str, Any]:
        appt = await self._read("Appointment", appointment_id)
        if not appt:
            return {"success": False, "error": "appointment_not_found"}
        patient_ref = _patient_ref(appt)
        if not patient_ref:
            return {"success": False, "error": "no_patient_on_appointment"}

        resource: Dict[str, Any] = {
            "resourceType": "QuestionnaireResponse",
            "status": "completed",
            "subject": {"reference": patient_ref},
            "authored": datetime.now(timezone.utc).isoformat(),
            "item": [
                {
                    "linkId": a["question_id"],
                    "answer": [{"valueString": a.get("raw_patient_input", "")}],
                }
                for a in answers
            ],
            "extension": [
                {"url": APPOINTMENT_EXT_URL, "valueReference": {"reference": f"Appointment/{appointment_id}"}}
            ],
        }
        if questionnaire_ref:
            resource["questionnaire"] = questionnaire_ref

        created = await self._create(resource)
        if not created:
            return {"success": False, "error": "write_failed"}
        return {"success": True, "response_id": created.get("id"), "answers_saved": len(answers)}

    # ------------------------------------------------------------- writeback
    async def create_communication(
        self, patient_id: str, transcript: str, *, organization_id: Optional[str] = None,
        summary: Optional[str] = None, category_text: str = "AI voice intake transcript",
    ) -> Optional[str]:
        if not patient_id:
            logger.info("No FHIR patient resolved; skipping Communication writeback.")
            return None
        payload: List[Dict[str, Any]] = []
        if summary:
            payload.append({"contentString": f"Summary: {summary}"})
        payload.append({"contentString": transcript})
        resource: Dict[str, Any] = {
            "resourceType": "Communication",
            "status": "completed",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/communication-category",
                    "code": "notification",
                    "display": "Notification",
                }],
                "text": category_text,
            }],
            "subject": {"reference": f"Patient/{patient_id}"},
            "sent": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        if organization_id:
            resource["sender"] = {"reference": f"Organization/{organization_id}"}
        try:
            created = await self._create(resource)
            created_id = (created or {}).get("id")
            logger.info(f"Medplum Communication created (id={created_id}).")
            return created_id
        except Exception as e:  # noqa: BLE001
            logger.error(f"Medplum Communication write failed: {type(e).__name__}")
            return None

    # -------------------------------------------------------- workflow (Tasks)
    async def create_task(
        self, code: str, *, patient_id: Optional[str], focus_ref: Optional[str],
        due: str, description: str,
    ) -> Optional[str]:
        """Create a workflow job as a FHIR Task (status=requested). `due` is an
        ISO-8601 time stored in executionPeriod.start; the runner executes it
        once due <= now."""
        resource: Dict[str, Any] = {
            "resourceType": "Task",
            "status": "requested",
            "intent": "order",
            "code": {"coding": [{"system": WORKFLOW_SYSTEM, "code": code}], "text": code},
            "description": description,
            "authoredOn": datetime.now(timezone.utc).isoformat(),
            "executionPeriod": {"start": due},
        }
        if patient_id:
            resource["for"] = {"reference": f"Patient/{patient_id}"}
        if focus_ref:
            resource["focus"] = {"reference": focus_ref}
        created = await self._create(resource)
        return (created or {}).get("id")

    async def list_open_tasks(self, limit: int = 200) -> List[Dict[str, Any]]:
        """All workflow Tasks still awaiting execution (status=requested)."""
        matches, _ = await self._search("Task", {"status": "requested", "_count": str(limit)})
        out: List[Dict[str, Any]] = []
        for t in matches:
            code = ((t.get("code") or {}).get("coding") or [{}])[0].get("code")
            out.append({
                "id": t.get("id"),
                "code": code,
                "due": (t.get("executionPeriod") or {}).get("start"),
                "for": (t.get("for") or {}).get("reference"),
                "focus": (t.get("focus") or {}).get("reference"),
                "description": t.get("description"),
                "resource": t,
            })
        return out

    async def set_task_status(self, task: Dict[str, Any], status: str, note: Optional[str] = None) -> None:
        """Advance a Task (completed / failed), read-modify-PUT."""
        task = dict(task)
        task["status"] = status
        if status in ("completed", "failed"):
            period = dict(task.get("executionPeriod") or {})
            period["end"] = datetime.now(timezone.utc).isoformat()
            task["executionPeriod"] = period
        if note:
            task.setdefault("note", []).append({"text": note})
        await self._update(task)

    # ----------------------------------------------------------------- audit
    async def create_audit_event(
        self, *, description: str, action: str = "E", outcome: str = "0",
        patient_id: Optional[str] = None, organization_id: Optional[str] = None,
    ) -> Optional[str]:
        """Record a FHIR AuditEvent (operational audit trail, PRD 5.40).
        `action`: C/R/U/D/E; `outcome`: 0=success, 4=minor failure, 8=serious."""
        resource: Dict[str, Any] = {
            "resourceType": "AuditEvent",
            "type": {"system": "http://dicom.nema.org/resources/ontology/DCM",
                     "code": "110100", "display": "Application Activity"},
            "action": action,
            "recorded": datetime.now(timezone.utc).isoformat(),
            "outcome": outcome,
            "outcomeDesc": description,
            "agent": [{"who": {"display": "ai-prof voice agent"}, "requestor": True}],
            "source": {"observer": {"display": "ai-prof"}},
        }
        entities = []
        if patient_id:
            entities.append({"what": {"reference": f"Patient/{patient_id}"}})
        if organization_id:
            entities.append({"what": {"reference": f"Organization/{organization_id}"}})
        if entities:
            resource["entity"] = entities
        try:
            created = await self._create(resource)
            return (created or {}).get("id")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Medplum AuditEvent write failed: {type(e).__name__}")
            return None

    # ------------------------------------------------------- read/list (API)
    async def read_patient(self, patient_id: str) -> Optional[Dict]:
        return await self._read("Patient", patient_id)

    async def read_appointment(self, appointment_id: str) -> Optional[Dict]:
        return await self._read("Appointment", appointment_id)

    async def search_appointments(
        self, *, patient_id: Optional[str] = None, practitioner_id: Optional[str] = None,
        location_id: Optional[str] = None, status: Optional[str] = None, count: int = 50,
    ) -> Tuple[List[Dict], Dict[str, Dict]]:
        """List appointments with participants included (for name resolution)."""
        params: Dict[str, Any] = {"_sort": "-date", "_count": str(count), "_include": "Appointment:actor"}
        if patient_id:
            params["patient"] = f"Patient/{patient_id}"
        if practitioner_id:
            params["practitioner"] = f"Practitioner/{practitioner_id}"
        if location_id:
            params["location"] = f"Location/{location_id}"
        if status:
            params["status"] = status
        return await self._search("Appointment", params)

    async def list_patients(self, organization_id: Optional[str] = None, count: int = 50) -> List[Dict]:
        params: Dict[str, Any] = {"_count": str(count)}
        if organization_id:
            params["organization"] = f"Organization/{organization_id}"
        matches, _ = await self._search("Patient", params)
        return matches

    async def list_organizations(self, count: int = 50) -> List[Dict]:
        matches, _ = await self._search("Organization", {"_count": str(count)})
        return matches

    async def list_audit_events(self, count: int = 50) -> List[Dict]:
        # AuditEvent's search param for `recorded` is `date`.
        matches, _ = await self._search("AuditEvent", {"_sort": "-date", "_count": str(count)})
        return matches

    async def list_communications(self, patient_id: Optional[str] = None, count: int = 50) -> List[Dict]:
        params: Dict[str, Any] = {"_sort": "-sent", "_count": str(count)}
        if patient_id:
            params["subject"] = f"Patient/{patient_id}"
        matches, _ = await self._search("Communication", params)
        return matches

    async def list_tasks(self, count: int = 100) -> List[Dict]:
        """All workflow Tasks (any status) for the ops dashboard."""
        matches, _ = await self._search("Task", {"_sort": "-authored-on", "_count": str(count)})
        return matches

    async def count_resources(self, resource_type: str, params: Optional[Dict[str, Any]] = None) -> int:
        headers = await self._headers()
        p = dict(params or {})
        p["_summary"] = "count"
        resp = await self._send("GET", f"{self._base}/fhir/R4/{resource_type}", params=p, headers=headers)
        resp.raise_for_status()
        return int(resp.json().get("total", 0))


# --------------------------------------------------------------------- helpers
def _phone_variants(phone: str) -> List[str]:
    phone = phone.strip()
    variants = [phone, phone[1:] if phone.startswith("+") else "+" + phone]
    seen: set = set()
    return [v for v in variants if v and not (v in seen or seen.add(v))]


def _parse_patient(resource: Dict[str, Any]) -> Dict[str, Any]:
    managing = (resource.get("managingOrganization") or {}).get("reference", "")
    org_id = managing.split("/", 1)[1] if managing.startswith("Organization/") else None
    name = (resource.get("name") or [{}])[0]
    return {
        "patient_id": resource.get("id"),
        "organization_id": org_id,
        "first_name": (name.get("given") or [None])[0],
        "last_name": name.get("family"),
    }


def _first_display(codeable: Dict[str, Any]) -> Optional[str]:
    return ((codeable.get("coding") or [{}])[0]).get("display")


def _use_context_text(questionnaire: Dict[str, Any]) -> str:
    parts: List[str] = []
    for uc in questionnaire.get("useContext") or []:
        cc = uc.get("valueCodeableConcept") or {}
        parts.append(cc.get("text") or _first_display(cc) or "")
    return " ".join(p for p in parts if p)


def _first_slot_id(appointment: Dict[str, Any]) -> Optional[str]:
    ref = ((appointment.get("slot") or [{}])[0]).get("reference", "")
    return ref.split("/")[-1] if ref.startswith("Slot/") else None


def _patient_ref(appointment: Dict[str, Any]) -> Optional[str]:
    for part in appointment.get("participant") or []:
        ref = (part.get("actor") or {}).get("reference", "")
        if ref.startswith("Patient/"):
            return ref
    return None


_FHIR_TYPE_TO_RESPONSE = {
    "boolean": "Yes/No",
    "choice": "Single Choice",
    "open-choice": "Multiple Choice",
    "integer": "Numeric",
    "decimal": "Numeric",
    "date": "Date",
    "dateTime": "Date",
    "string": "Short Text",
    "text": "Long Text",
}


def _map_question_item(item: Dict[str, Any]) -> Dict[str, Any]:
    options = []
    for opt in item.get("answerOption") or []:
        vc = opt.get("valueCoding") or {}
        options.append(opt.get("valueString") or vc.get("display") or vc.get("code"))
    return {
        "question_id": item.get("linkId"),
        "prompt_text": item.get("text"),
        "response_type": _FHIR_TYPE_TO_RESPONSE.get(item.get("type"), "Short Text"),
        "options": [o for o in options if o],
        "is_required": bool(item.get("required", False)),
    }


def _human_time(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%A %B %d, %I:%M %p")
    except Exception:  # noqa: BLE001
        return iso


# --------------------------------------------------------- process-wide client
_CLIENT: Optional[MedplumClient] = None
_CLIENT_RESOLVED = False


def get_medplum_client() -> Optional[MedplumClient]:
    """Cached process-wide client (shares the auth-token cache across calls)."""
    global _CLIENT, _CLIENT_RESOLVED
    if not _CLIENT_RESOLVED:
        _CLIENT = MedplumClient.from_env()
        _CLIENT_RESOLVED = True
    return _CLIENT
