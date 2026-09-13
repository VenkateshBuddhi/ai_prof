-- ============================================================================
-- ai_prof :: Seed data
-- Mirrors the legacy in-memory registries in src/voice/capabilities.py so the
-- voice pipeline can migrate off them gradually. Runs after database/schema.sql.
-- Idempotent: guarded re-runs (PK ON CONFLICT + NOT EXISTS on partial unique
-- indexes, because PostgreSQL cannot use a partial unique index as an
-- ON CONFLICT arbiter).
-- ============================================================================

SET TIME ZONE 'America/New_York';

BEGIN;

-- 1. Tenant network + hospitals
INSERT INTO tenants (tenant_id, name, slug, status, default_timezone)
VALUES ('11111111-1111-4111-8111-111111111111', 'St. Mary Health Network', 'st-mary-network', 'Active', 'America/New_York')
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO hospitals (hospital_id, tenant_id, name, code, address, timezone) VALUES
('22222222-2222-4222-8222-222222222222', '11111111-1111-4111-8111-111111111111', 'St. Mary Medical Center', 'SMMC',
 '{"line1":"101 Healing Way","city":"North Sector","state":"NY","postal_code":"10001","country":"US"}', 'America/New_York'),
('33333333-3333-4333-8333-333333333333', '11111111-1111-4111-8111-111111111111', 'Downtown General Hospital', 'DGH',
 '{"line1":"55 Recovery Ave","city":"Downtown","state":"NY","postal_code":"10002","country":"US"}', 'America/New_York')
ON CONFLICT (hospital_id) DO NOTHING;

-- 2. Doctors (mirrors DOCTORS_DB)
INSERT INTO doctors (doctor_id, tenant_id, first_name, last_name, specialty, languages) VALUES
('44444444-4444-4444-8444-444444444444', '11111111-1111-4111-8111-111111111111', 'Aarav', 'Sharma', 'Dermatology', ARRAY['en','hi']),
('55555555-5555-4555-8555-555555555555', '11111111-1111-4111-8111-111111111111', 'Priya', 'Rao', 'Cardiology', ARRAY['en','hi']),
('66666666-6666-4666-8666-666666666666', '11111111-1111-4111-8111-111111111111', 'Sarah', 'Jenkins', 'Orthopedics', ARRAY['en'])
ON CONFLICT (doctor_id) DO NOTHING;

-- 2b. Affiliations (partial unique index on (doctor_id, hospital_id) WHERE active)
INSERT INTO doctor_hospital_affiliations (doctor_id, hospital_id, is_primary)
SELECT aff.doctor_id, aff.hospital_id, aff.is_primary
  FROM (VALUES
    ('44444444-4444-4444-8444-444444444444'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, true),
    ('55555555-5555-4555-8555-555555555555'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, true),
    ('66666666-6666-4666-8666-666666666666'::uuid, '33333333-3333-4333-8333-333333333333'::uuid, true)
  ) AS aff(doctor_id, hospital_id, is_primary)
 WHERE NOT EXISTS (SELECT 1 FROM doctor_hospital_affiliations a
                    WHERE a.doctor_id = aff.doctor_id AND a.hospital_id = aff.hospital_id);

-- 3. Patient (mirrors PATIENTS_DB: John Doe pat_992)
INSERT INTO patients (patient_id, tenant_id, ehr_patient_id, first_name, last_name, date_of_birth, phone, preferred_doctor_id, communication_preference)
VALUES ('99999999-9999-4999-8999-999999999999', '11111111-1111-4111-8111-111111111111', 'EHR-PAT-000992',
        'John', 'Doe', '1985-04-12', '+15550192834', '55555555-5555-4555-8555-555555555555', 'Voice')
ON CONFLICT (patient_id) DO NOTHING;

INSERT INTO patient_consents (patient_id, scope, granted, source)
SELECT '99999999-9999-4999-8999-999999999999', 'EHR_DATA_SHARING', true, 'Voice'
WHERE NOT EXISTS (SELECT 1 FROM patient_consents c
                   WHERE c.patient_id = '99999999-9999-4999-8999-999999999999'::uuid
                     AND c.scope = 'EHR_DATA_SHARING' AND c.granted AND c.revoked_at IS NULL);

-- 4. Platform administrator
INSERT INTO admin_users (admin_user_id, tenant_id, full_name, email, role, scopes)
VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '11111111-1111-4111-8111-111111111111',
        'Platform Admin', 'admin@stmarynetwork.example', 'SUPER_ADMIN', ARRAY['*'])
ON CONFLICT (admin_user_id) DO NOTHING;
-- 5. Recurring availability templates (mirrors DOCTORS_DB availability strings)
INSERT INTO availability_templates (template_id, doctor_id, hospital_id, day_of_week, start_time, end_time, slot_duration_minutes, appointment_type) VALUES
('00000000-0000-4000-8000-000000000001', '44444444-4444-4444-8444-444444444444'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, 'Monday',   '09:00', '12:00', 30, 'Standard'),
('00000000-0000-4000-8000-000000000002', '44444444-4444-4444-8444-444444444444'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, 'Friday',   '13:00', '17:00', 30, 'Standard'),
('00000000-0000-4000-8000-000000000003', '55555555-5555-4555-8555-555555555555'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, 'Thursday', '13:00', '17:00', 30, 'Standard'),
('00000000-0000-4000-8000-000000000004', '55555555-5555-4555-8555-555555555555'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, 'Friday',   '09:00', '12:00', 30, 'Standard'),
('00000000-0000-4000-8000-000000000005', '66666666-6666-4666-8666-666666666666'::uuid, '33333333-3333-4333-8333-333333333333'::uuid, 'Wednesday','09:00', '12:00', 30, 'Standard'),
('00000000-0000-4000-8000-000000000006', '66666666-6666-4666-8666-666666666666'::uuid, '33333333-3333-4333-8333-333333333333'::uuid, 'Thursday', '13:00', '17:00', 30, 'Standard')
ON CONFLICT (template_id) DO NOTHING;

-- 6. EHR integration (Epic instance + per-facility connections)
INSERT INTO ehr_systems (ehr_system_id, tenant_id, vendor, name, base_url, auth_mode) VALUES
('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '11111111-1111-4111-8111-111111111111', 'Epic', 'Epic MyChart', 'https://ehr.example.test/fhir/', 'OAuth2')
ON CONFLICT (ehr_system_id) DO NOTHING;

INSERT INTO ehr_connections (connection_id, ehr_system_id, hospital_id, credentials_ref) VALUES
('cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '22222222-2222-4222-8222-222222222222', 'vault://epic/smmc/credentials'),
('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '33333333-3333-4333-8333-333333333333', 'vault://epic/dgh/credentials')
ON CONFLICT (connection_id) DO NOTHING;

-- 7. Sample pre-visit questionnaire (Dr. Priya Rao, Cardiology)
INSERT INTO questionnaire_definitions (questionnaire_id, tenant_id, doctor_id, title, specialty, version, questions) VALUES
('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', '11111111-1111-4111-8111-111111111111', '55555555-5555-4555-8555-555555555555',
 'Cardiology Pre-visit Intake', 'Cardiology', 1,
 '[{"question_id":"q1","prompt_text":"Are you experiencing chest pain?","response_type":"Yes/No","options":[],"is_required":true},{"question_id":"q2","prompt_text":"How long have you had symptoms?","response_type":"Short Text","options":[],"is_required":true},{"question_id":"q3","prompt_text":"Family history of heart disease?","response_type":"Yes/No","options":[],"is_required":false}]'::jsonb)
ON CONFLICT (questionnaire_id) DO NOTHING;

-- 8. Materialise concrete slots for the next 14 days from the templates above
SELECT materialize_slots(current_date, current_date + 13) AS slots_created;

COMMIT;
