-- Rig part 3b: write-booking validation (separate statements per step:
-- writes in a data-modifying CTE are invisible to same-statement INSERTs
-- under RLS for non-owners, so hold / insert / confirm are sequential).

-- R7a: hold one Open slot under tenant-A JWT
SET ROLE rig_app;
SET request.jwt.claims = '{"sub":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","app_metadata":{"tenant_id":"11111111-1111-4111-8111-111111111111"}}';
WITH target AS (
  SELECT slot_id FROM time_slots
   WHERE tenant_id = '11111111-1111-4111-8111-111111111111' AND status = 'Open'
   ORDER BY start_time LIMIT 1
), held AS (
  UPDATE time_slots ts SET status = 'Held', hold_token = gen_random_uuid(),
         hold_until = now() + interval '10 minutes', row_version = row_version + 1
    FROM target WHERE ts.slot_id = target.slot_id AND ts.status = 'Open'
  RETURNING ts.slot_id
)
SELECT 'R7a-held' AS check, CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS result FROM held;
RESET ROLE;

-- R7b: insert the appointment from the held row (separate statement)
SET ROLE rig_app;
SET request.jwt.claims = '{"sub":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","app_metadata":{"tenant_id":"11111111-1111-4111-8111-111111111111"}}';
INSERT INTO appointments (tenant_id, patient_id, hospital_id, doctor_id,
                          calendar_slot_id, appointment_type, start_time, end_time,
                          status, idempotency_key)
SELECT ts.tenant_id, '99999999-9999-4999-8999-999999999999', ts.hospital_id, ts.doctor_id,
       ts.slot_id, COALESCE(ts.appointment_type, 'Standard'),
       ts.start_time, ts.end_time, 'Confirmed', 'rig-validation-key-001'
  FROM time_slots ts WHERE ts.status = 'Held' ORDER BY ts.start_time LIMIT 1;
SELECT 'R7b-inserted' AS check,
       CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS result
  FROM appointments WHERE idempotency_key = 'rig-validation-key-001';
RESET ROLE;
