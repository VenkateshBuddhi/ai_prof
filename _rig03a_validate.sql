-- Rig part 3a: read-path + trigger validation.
-- Every check prints PASS/FAIL; run with ON_ERROR_STOP=0.

-- R1: fail closed with no JWT (non-owner must see zero rows)
SET ROLE rig_app;
SELECT 'R1-nojwt-count-is-0' AS check,
       CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL:' || count(*)::text END AS result
  FROM hospitals;
RESET ROLE;

-- R2: tenant-A JWT sees exactly its own rows
SET ROLE rig_app;
SET request.jwt.claims = '{"sub":"00000000-0000-4000-8000-000000000099","app_metadata":{"tenant_id":"11111111-1111-4111-8111-111111111111"}}';
SELECT 'R2-tenant-visible' AS check,
       CASE WHEN (SELECT count(*) FROM tenants) = 1
             AND (SELECT count(*) FROM hospitals) = 2
             AND (SELECT count(*) FROM doctors) = 3
             AND (SELECT count(*) FROM time_slots) = 84
            THEN 'PASS' ELSE 'FAIL' END AS result;
RESET ROLE;

-- R3: cross-tenant INSERT rejected by policy (expect RLS violation, caught)
DO $$
BEGIN
  PERFORM set_config('request.jwt.claims',
    '{"sub":"00000000-0000-4000-8000-000000000099","app_metadata":{"tenant_id":"11111111-1111-4111-8111-111111111111"}}', true);
  SET ROLE rig_app;
  BEGIN
    INSERT INTO doctor_hospital_affiliations (doctor_id, hospital_id)
    VALUES ('44444444-4444-4444-8444-444444444444', 'bbbbbbbb-1111-4222-8333-cccccccccccc');
    RESET ROLE;
    RAISE NOTICE 'R3-cross-tenant-insert: FAIL (insert unexpectedly allowed)';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'R3-cross-tenant-insert: PASS (rejected: %)', SQLERRM;
  END;
END
$$;

-- R4: signup trigger provisions a patient profile from app_metadata
INSERT INTO auth.users (id, email, raw_app_meta_data, raw_user_meta_data)
VALUES ('12345678-1234-4234-8234-123456789012', 'new.patient@example.test',
        '{"tenant_id":"11111111-1111-4111-8111-111111111111","profile_type":"patient"}',
        '{"first_name":"Nova","last_name":"Patient"}')
ON CONFLICT (id) DO NOTHING;
SELECT 'R4-signup-profile' AS check,
       CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END AS result
  FROM patients WHERE user_id = '12345678-1234-4234-8234-123456789012';

-- R5: identity helpers resolve from the JWT sub claim
SET ROLE rig_app;
SET request.jwt.claims = '{"sub":"12345678-1234-4234-8234-123456789012","app_metadata":{"tenant_id":"11111111-1111-4111-8111-111111111111"}}';
SELECT 'R5-helpers' AS check,
       CASE WHEN my_patient_id() IS NOT NULL
             AND current_tenant_id() = '11111111-1111-4111-8111-111111111111'
            THEN 'PASS' ELSE 'FAIL' END AS result;
RESET ROLE;

-- R6: anonymous helpers return NULL (fail closed)
SET ROLE rig_app;
SELECT 'R6-anon-null' AS check,
       CASE WHEN my_patient_id() IS NULL AND current_tenant_id() IS NULL
            THEN 'PASS' ELSE 'FAIL' END AS result;
RESET ROLE;
