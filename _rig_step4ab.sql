SELECT 'step4ab-wcte-insert-select-count' AS step;
SET ROLE rig_app;
SET request.jwt.claims = '{"sub":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","app_metadata":{"tenant_id":"11111111-1111-4111-8111-111111111111"}}';
WITH held AS (
  SELECT ts.slot_id, ts.tenant_id, ts.hospital_id, ts.doctor_id,
         ts.start_time, ts.end_time, ts.appointment_type
    FROM time_slots ts WHERE ts.status = 'Held' ORDER BY ts.start_time LIMIT 1
), ins AS (
  INSERT INTO appointments (tenant_id, patient_id, hospital_id, doctor_id,
                            calendar_slot_id, appointment_type, start_time, end_time,
                            status, idempotency_key)
  SELECT h.tenant_id, '99999999-9999-4999-8999-999999999999', h.hospital_id, h.doctor_id,
         h.slot_id, COALESCE(h.appointment_type, 'Standard'),
         h.start_time, h.end_time,
         'Confirmed', 'jwt-clean-key-012'
    FROM held h
  RETURNING appointment_id
)
SELECT count(*) AS inserted FROM ins;
RESET ROLE;
