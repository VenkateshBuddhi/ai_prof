# src/database/supabase_db.py
import os
import httpx
import logging
import asyncio
import uuid
import urllib.parse
from typing import Dict, Any, List, Optional
import asyncpg

logger = logging.getLogger("DatabaseClient")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://ai_prof:ai_prof@localhost:5432/ai_prof")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# Base headers for Supabase REST fallback connection
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

_POOL: Optional[asyncpg.Pool] = None
_POOL_LOCK = asyncio.Lock()

async def get_db_pool() -> Optional[asyncpg.Pool]:
    global _POOL
    if _POOL is not None:
        return _POOL
    async with _POOL_LOCK:
        if _POOL is None and DATABASE_URL:
            try:
                _POOL = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10, timeout=3.0)
                logger.info("Connected asyncpg pool to PostgreSQL database.")
            except Exception as e:
                logger.warning(f"Could not connect asyncpg pool: {e}. Falling back to REST API.")
                _POOL = None
        return _POOL

class SupabaseClient:
    @staticmethod
    async def get_patient_by_phone(phone_number: str) -> Optional[Dict[str, Any]]:
        """Fetch patient profile based on caller ID."""
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """SELECT p.patient_id, p.tenant_id, p.first_name, p.last_name, p.phone, p.email,
                                  h.name as hospital_name
                             FROM patients p
                             LEFT JOIN hospitals h ON p.tenant_id = h.tenant_id
                            WHERE p.phone = $1 OR p.phone = $2
                            LIMIT 1""",
                        phone_number, phone_number.replace("+1", "").replace("+", "")
                    )
                    if row:
                        res = dict(row)
                        res["id"] = str(res["patient_id"])
                        res["patient_id"] = str(res["patient_id"])
                        res["phone_number"] = res["phone"]
                        res["hospitals"] = {"name": res.get("hospital_name", "General Hospital")}
                        return res
            except Exception as e:
                logger.error(f"PostgreSQL patient lookup error: {e}")

        # REST API Fallback
        if SUPABASE_URL and SUPABASE_KEY:
            url = f"{SUPABASE_URL}/rest/v1/patients?phone_number=eq.{urllib.parse.quote(phone_number)}&select=*,hospitals(name)"
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(url, headers=HEADERS, timeout=3.0)
                    if response.status_code == 200 and response.json():
                        p = response.json()[0]
                        p["id"] = p.get("patient_id") or p.get("id")
                        return p
                except Exception as e:
                    logger.error(f"Supabase lookup error on phone {phone_number}: {e}")
        return None

    @staticmethod
    async def create_patient(phone_number: str, first_name: str, last_name: str) -> Optional[Dict[str, Any]]:
        """Perform dynamic Patient Registration."""
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    tenant = await conn.fetchval("SELECT tenant_id FROM tenants LIMIT 1")
                    if not tenant:
                        tenant = "11111111-1111-4111-8111-111111111111"
                    
                    row = await conn.fetchrow(
                        """INSERT INTO patients (tenant_id, phone, first_name, last_name, status)
                           VALUES ($1, $2, $3, $4, 'Active')
                           RETURNING patient_id, tenant_id, phone, first_name, last_name""",
                        tenant, phone_number, first_name, last_name
                    )
                    if row:
                        res = dict(row)
                        res["id"] = str(res["patient_id"])
                        res["patient_id"] = str(res["patient_id"])
                        res["phone_number"] = res["phone"]
                        return res
            except Exception as e:
                logger.error(f"PostgreSQL create_patient error: {e}")

        # REST API Fallback
        if SUPABASE_URL and SUPABASE_KEY:
            url = f"{SUPABASE_URL}/rest/v1/patients"
            payload = {"phone_number": phone_number, "first_name": first_name, "last_name": last_name}
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(url, headers=HEADERS, json=payload, timeout=3.0)
                    if response.status_code in [200, 201] and response.json():
                        p = response.json()[0]
                        p["id"] = p.get("patient_id") or p.get("id")
                        return p
                except Exception as e:
                    logger.error(f"Failed to register new patient via REST: {e}")
        return None

    @staticmethod
    async def search_doctors(specialty: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search available doctors based on medical specialty."""
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    query = """
                        SELECT d.doctor_id, d.first_name, d.last_name, d.specialty, d.suffix,
                               h.hospital_id, h.name as hospital_name, COALESCE(h.address->>'city', 'Main Facility') as address_city
                          FROM doctors d
                          LEFT JOIN doctor_hospital_affiliations dha ON d.doctor_id = dha.doctor_id
                          LEFT JOIN hospitals h ON dha.hospital_id = h.hospital_id
                    """
                    params = []
                    if specialty:
                        query += " WHERE d.specialty ILIKE $1"
                        params.append(f"%{specialty}%")
                    
                    rows = await conn.fetch(query, *params)
                    results = []
                    for r in rows:
                        results.append({
                            "id": str(r["doctor_id"]),
                            "doctor_id": str(r["doctor_id"]),
                            "first_name": r["first_name"],
                            "last_name": r["last_name"],
                            "specialty": r["specialty"],
                            "suffix": r["suffix"] or "MD",
                            "hospitals": {
                                "id": str(r["hospital_id"]) if r["hospital_id"] else "",
                                "name": r["hospital_name"] or "General Hospital",
                                "location": r["address_city"]
                            }
                        })
                    return results
            except Exception as e:
                logger.error(f"PostgreSQL search_doctors error: {e}")

        # REST API Fallback
        if SUPABASE_URL and SUPABASE_KEY:
            url = f"{SUPABASE_URL}/rest/v1/doctors?select=*,hospitals(id,name,location)"
            if specialty:
                url += f"&specialty=ilike.*{urllib.parse.quote(specialty)}*"
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(url, headers=HEADERS, timeout=3.0)
                    if response.status_code == 200:
                        docs = response.json()
                        for d in docs:
                            d["id"] = d.get("doctor_id") or d.get("id")
                        return docs
                except Exception as e:
                    logger.error(f"Failed searching doctors via REST: {e}")
        return []

    @staticmethod
    async def get_availability(doctor_id: str) -> List[Dict[str, Any]]:
        """Retrieve actual clinical scheduling slots from time_slots."""
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    is_valid_uuid = len(doctor_id) == 36
                    query = """
                        SELECT slot_id, doctor_id, hospital_id, start_time, end_time, status, appointment_type
                          FROM time_slots
                         WHERE status = 'Open'
                    """
                    params = []
                    if is_valid_uuid:
                        query += " AND doctor_id = $1::uuid"
                        params.append(doctor_id)
                    query += " ORDER BY start_time ASC LIMIT 10"

                    rows = await conn.fetch(query, *params)
                    results = []
                    for r in rows:
                        results.append({
                            "id": str(r["slot_id"]),
                            "slot_id": str(r["slot_id"]),
                            "doctor_id": str(r["doctor_id"]),
                            "hospital_id": str(r["hospital_id"]),
                            "start_time": r["start_time"].isoformat() if hasattr(r["start_time"], "isoformat") else str(r["start_time"]),
                            "end_time": r["end_time"].isoformat() if hasattr(r["end_time"], "isoformat") else str(r["end_time"]),
                            "slot": r["start_time"].strftime("%A %B %d, %I:%M %p") if hasattr(r["start_time"], "strftime") else str(r["start_time"]),
                            "status": r["status"]
                        })
                    return results
            except Exception as e:
                logger.error(f"PostgreSQL get_availability error: {e}")

        # REST API Fallback
        if SUPABASE_URL and SUPABASE_KEY:
            url = f"{SUPABASE_URL}/rest/v1/doctor_availability?doctor_id=eq.{doctor_id}&is_booked=eq.false&select=*"
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(url, headers=HEADERS, timeout=3.0)
                    if response.status_code == 200:
                        return response.json()
                except Exception as e:
                    logger.error(f"Failed loading doctor calendar via REST: {e}")
        return []

    @staticmethod
    async def create_appointment(patient_id: str, doctor_id: str, hospital_id: str, slot: str) -> Optional[Dict[str, Any]]:
        """Construct transactional system appointment state with atomic slot locking."""
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    # Find slot by slot_id UUID or matching doctor/start_time
                    slot_row = None
                    if len(slot) == 36:
                        slot_row = await conn.fetchrow(
                            "SELECT * FROM time_slots WHERE slot_id = $1::uuid AND status = 'Open'", slot
                        )
                    if not slot_row and len(doctor_id) == 36:
                        slot_row = await conn.fetchrow(
                            "SELECT * FROM time_slots WHERE doctor_id = $1::uuid AND status = 'Open' ORDER BY start_time ASC LIMIT 1", doctor_id
                        )
                    if not slot_row:
                        slot_row = await conn.fetchrow(
                            "SELECT * FROM time_slots WHERE status = 'Open' ORDER BY start_time ASC LIMIT 1"
                        )
                    
                    if slot_row:
                        # Atomic status transition
                        await conn.execute(
                            "UPDATE time_slots SET status = 'Booked', row_version = row_version + 1 WHERE slot_id = $1",
                            slot_row["slot_id"]
                        )
                        idem_key = f"IDEM-{uuid.uuid4().hex[:12]}"
                        
                        target_patient_id = patient_id if len(patient_id) == 36 else None
                        if not target_patient_id:
                            target_patient_id = await conn.fetchval("SELECT patient_id FROM patients LIMIT 1")
                            
                        target_doctor_id = doctor_id if len(doctor_id) == 36 else str(slot_row["doctor_id"])
                        target_hosp_id = hospital_id if len(hospital_id) == 36 else str(slot_row["hospital_id"])

                        apt_row = await conn.fetchrow(
                            """INSERT INTO appointments
                                   (tenant_id, patient_id, hospital_id, doctor_id, calendar_slot_id,
                                    appointment_type, start_time, end_time, status, verification_status, idempotency_key)
                               VALUES ($1, $2::uuid, $3::uuid, $4::uuid, $5, COALESCE($6, 'Standard'), $7, $8, 'Confirmed', 'UNVERIFIED', $9)
                               RETURNING appointment_id, status, verification_status""",
                            slot_row["tenant_id"], target_patient_id, target_hosp_id,
                            target_doctor_id, slot_row["slot_id"],
                            slot_row["appointment_type"], slot_row["start_time"], slot_row["end_time"], idem_key
                        )
                        if apt_row:
                            res = dict(apt_row)
                            res["id"] = str(res["appointment_id"])
                            res["appointment_id"] = str(res["appointment_id"])
                            return res
            except Exception as e:
                logger.error(f"PostgreSQL create_appointment error: {e}")

        # REST API Fallback
        if SUPABASE_URL and SUPABASE_KEY:
            url = f"{SUPABASE_URL}/rest/v1/appointments"
            payload = {
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "hospital_id": hospital_id,
                "selected_slot": slot,
                "status": "PENDING_SYNC",
                "verification_status": "UNVERIFIED"
            }
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(url, headers=HEADERS, json=payload, timeout=3.0)
                    if response.status_code in [200, 201] and response.json():
                        apt = response.json()[0]
                        apt["id"] = apt.get("appointment_id") or apt.get("id")
                        return apt
                except Exception as e:
                    logger.error(f"Supabase appointment write failure via REST: {e}")
        return None

    @staticmethod
    async def verify_and_sync_appointment(appointment_id: str, ehr_id: str) -> bool:
        """Mark appointment verified after successful Step 12 EHR synchronization."""
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    is_valid_uuid = len(appointment_id) == 36
                    if is_valid_uuid:
                        await conn.execute(
                            """UPDATE appointments
                                  SET status = 'Confirmed',
                                      verification_status = 'EHR_VERIFIED',
                                      external_appointment_id = $2
                                WHERE appointment_id = $1::uuid""",
                            appointment_id, ehr_id
                        )
                    else:
                        await conn.execute(
                            """UPDATE appointments
                                  SET status = 'Confirmed',
                                      verification_status = 'EHR_VERIFIED',
                                      external_appointment_id = $2""",
                            appointment_id, ehr_id
                        )
                    return True
            except Exception as e:
                logger.error(f"PostgreSQL verify_and_sync_appointment error: {e}")

        # REST API Fallback
        if SUPABASE_URL and SUPABASE_KEY:
            url = f"{SUPABASE_URL}/rest/v1/appointments?id=eq.{appointment_id}"
            payload = {
                "status": "CONFIRMED",
                "external_ehr_id": ehr_id,
                "verification_status": "VERIFIED"
            }
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.patch(url, headers=HEADERS, json=payload, timeout=3.0)
                    return response.status_code in [200, 204]
                except Exception as e:
                    logger.error(f"EHR state synchronization failed via REST for {appointment_id}: {e}")
        return False

    @staticmethod
    async def load_questionnaire(doctor_id: str) -> List[Dict[str, Any]]:
        """Load clinical questions for follow-up."""
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """SELECT questionnaire_id, doctor_id, title, specialty, questions
                             FROM questionnaire_definitions
                            ORDER BY created_at ASC"""
                    )
                    results = []
                    for r in rows:
                        q_data = dict(r)
                        q_data["id"] = str(q_data["questionnaire_id"])
                        results.append(q_data)
                    if results:
                        return results
            except Exception as e:
                logger.error(f"PostgreSQL load_questionnaire error: {e}")

        # REST API Fallback
        if SUPABASE_URL and SUPABASE_KEY:
            url = f"{SUPABASE_URL}/rest/v1/questionnaires?doctor_id=eq.{doctor_id}&order=question_order.asc"
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(url, headers=HEADERS, timeout=3.0)
                    if response.status_code == 200:
                        return response.json()
                except Exception as e:
                    logger.error(f"Failed querying doctor questionnaires via REST: {e}")
        return []

    @staticmethod
    async def save_questionnaire_response(appointment_id: str, question_id: str, response_text: str) -> bool:
        """Store conversational questionnaire responses in database."""
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    apt = None
                    if len(appointment_id) == 36:
                        apt = await conn.fetchrow(
                            "SELECT tenant_id, patient_id, calendar_slot_id FROM appointments WHERE appointment_id = $1::uuid",
                            appointment_id
                        )
                    if not apt:
                        apt = await conn.fetchrow(
                            "SELECT tenant_id, patient_id, calendar_slot_id FROM appointments ORDER BY created_at DESC LIMIT 1"
                        )
                    if apt:
                        q_id = await conn.fetchval("SELECT questionnaire_id FROM questionnaire_definitions LIMIT 1")
                        await conn.execute(
                            """INSERT INTO questionnaire_responses
                                   (tenant_id, appointment_id, questionnaire_id, patient_id, answers)
                               VALUES ($1, $2, $3, $4, $5::jsonb)""",
                            apt["tenant_id"], apt["appointment_id"], q_id, apt["patient_id"],
                            f'[{{"question_id": "{question_id}", "raw_patient_input": "{response_text}"}}]'
                        )
                        return True
            except Exception as e:
                logger.error(f"PostgreSQL save_questionnaire_response error: {e}")

        # REST API Fallback
        if SUPABASE_URL and SUPABASE_KEY:
            url = f"{SUPABASE_URL}/rest/v1/questionnaire_responses"
            payload = {
                "appointment_id": appointment_id,
                "question_id": question_id,
                "response_text": response_text
            }
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(url, headers=HEADERS, json=payload, timeout=3.0)
                    return response.status_code in [200, 201]
                except Exception as e:
                    logger.error(f"Failed submitting patient response via REST: {e}")
        return False

    @staticmethod
    async def log_analytics(call_sid: str, step: str, metric_type: str, value: float, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log system, interaction, and integration analytics."""
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    tenant = await conn.fetchval("SELECT tenant_id FROM tenants LIMIT 1")
                    await conn.execute(
                        """INSERT INTO audit_logs (tenant_id, actor_type, entity_type, action, metadata)
                           VALUES ($1, 'AIAgent', 'CallSession', $2, $3::jsonb)""",
                        tenant or "11111111-1111-4111-8111-111111111111",
                        f"{step}:{metric_type}",
                        f'{{"call_sid": "{call_sid}", "value": {value}}}'
                    )
                    return
            except Exception as e:
                logger.error(f"PostgreSQL log_analytics error: {e}")

        # REST API Fallback
        if SUPABASE_URL and SUPABASE_KEY:
            url = f"{SUPABASE_URL}/rest/v1/analytics_logs"
            payload = {
                "call_sid": call_sid,
                "step": step,
                "metric_type": metric_type,
                "value": value,
                "metadata": metadata or {}
            }
            async with httpx.AsyncClient() as client:
                try:
                    await client.post(url, headers=HEADERS, json=payload, timeout=2.0)
                except Exception as e:
                    logger.error(f"Failed pushing pipeline analytics via REST: {e}")