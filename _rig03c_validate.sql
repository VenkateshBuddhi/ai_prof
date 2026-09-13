-- Rig part 3c: confirm the held slot, then double-booking + replay guards.

-- R7c: confirm the slot (superuser joins on the idempotency key)
UPDATE time_slots ts SET status = 'Booked', hold_token = NULL, hold_until = NULL,
       row_version = row_version + 1
  FROM appointments a
 WHERE a.idempotency_key = 'rig-validation-key-001' AND ts.slot_id = a.calendar_slot_id;
SELECT 'R7c-booked' AS check,
       CASE WHEN (SELECT ts.status FROM time_slots ts JOIN appointments a
                   ON a.calendar_slot_id = ts.slot_id
                  WHERE a.idempotency_key = 'rig-validation-key-001') = 'Booked'
            THEN 'PASS' ELSE 'FAIL' END AS result;

-- R8: second booking on the same slot rejected (partial unique index)
SET ROLE rig_app;
SET request.jwt.claims = '{"sub":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","app_metadata":{"tenant_id":"11111111-1111-4111-8111-111111111111"}}';
DO $$
BEGIN
  INSERT INTO appointments (tenant_id, patient_id, hospital_id, doctor_id,
                            calendar_slot_id, appointment_type, start_time, end_time,
                            status, idempotency_key)
  SELECT a.tenant_id, '7cd99a61-4aa2-461f-9188-1c6770145bef', a.hospital_id, a.doctor_id,
         a.calendar_slot_id, 'Standard', a.start_time, a.end_time,
         'Confirmed', 'rig-validation-key-002'
    FROM appointments a WHERE a.idempotency_key = 'rig-validation-key-001';
  RAISE NOTICE 'R8-double-booking: FAIL (duplicate unexpectedly allowed)';
EXCEPTION WHEN unique_violation THEN
  RAISE NOTICE 'R8-double-booking: PASS (rejected: slot already booked)';
END
$$;
RESET ROLE;

-- R9: idempotency-key replay rejected (retried agent call collapses safely)
SET ROLE rig_app;
SET request.jwt.claims = '{"sub":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","app_metadata":{"tenant_id":"11111111-1111-4111-8111-111111111111"}}';
DO $$
BEGIN
  INSERT INTO appointments (tenant_id, patient_id, hospital_id, doctor_id,
                            calendar_slot_id, appointment_type, start_time, end_time,
                            status, idempotency_key)
  SELECT a.tenant_id, a.patient_id, a.hospital_id, a.doctor_id,
         a.calendar_slot_id, 'Standard', a.start_time, a.end_time,
         'Confirmed', 'rig-validation-key-001'
    FROM appointments a WHERE a.idempotency_key = 'rig-validation-key-001';
  RAISE NOTICE 'R9-idempotency-replay: FAIL (replay unexpectedly inserted)';
EXCEPTION WHEN unique_violation THEN
  RAISE NOTICE 'R9-idempotency-replay: PASS (rejected: key already used)';
END
$$;
RESET ROLE;
