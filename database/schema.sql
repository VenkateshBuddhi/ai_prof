-- ============================================================================
-- ai_prof :: Multi-tenant Healthcare Operations & Patient-Access Platform
-- PostgreSQL 16 schema (DDL)
-- Target DB: ai_prof  |  Setup guide: database/README.md
--
-- Conventions:
--   * UUID primary keys (gen_random_uuid(), built into PostgreSQL 13+).
--   * tenant_id on every tenant-scoped table to support Row-Level Security.
--   * Enums mirror the JSON Schema catalog in ./schemas.
--   * updated_at is maintained by the set_updated_at() trigger.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Enumerated types (mirror ./schemas/*.json enums)
-- ---------------------------------------------------------------------------

CREATE TYPE tenant_status AS ENUM ('Onboarding', 'Active', 'Suspended', 'Closed');
CREATE TYPE record_status AS ENUM ('Active', 'Inactive', 'Suspended', 'Closed');
CREATE TYPE user_role AS ENUM ('SUPER_ADMIN', 'TENANT_ADMIN', 'HOSPITAL_ADMIN', 'FRONT_DESK', 'CLINICAL_STAFF');

CREATE TYPE appointment_status AS ENUM (
  'Requested', 'Pending', 'Confirmed', 'Rescheduled',
  'Cancelled', 'Completed', 'No-show', 'Failed',
  'Synchronization Pending', 'Reconciliation Required'
);
CREATE TYPE verification_status AS ENUM ('UNVERIFIED', 'EHR_VERIFIED', 'VERIFICATION_FAILED');

CREATE TYPE slot_status AS ENUM ('Open', 'Booked', 'Held', 'Blocked', 'Cancelled', 'Expired');

CREATE TYPE conversation_intent AS ENUM ('BOOK_APPOINTMENT', 'RESCHEDULE', 'CANCEL', 'COMPLETE_QUESTIONNAIRE', 'GENERAL_INQUIRY');
CREATE TYPE time_preference AS ENUM ('Morning', 'Afternoon', 'Evening');
CREATE TYPE conversation_appointment_status AS ENUM ('Pending', 'Confirmed', 'Cancelled', 'Escalated', 'Failed');
CREATE TYPE conversation_channel AS ENUM ('Voice', 'Chat', 'Portal');
CREATE TYPE session_status AS ENUM ('Active', 'Ended', 'Abandoned', 'Escalated');
CREATE TYPE message_role AS ENUM ('User', 'Assistant', 'System', 'Tool');
CREATE TYPE escalation_status AS ENUM ('Open', 'Assigned', 'Resolved', 'Closed');

CREATE TYPE availability_day AS ENUM ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');

CREATE TYPE sync_direction AS ENUM ('Outbound', 'Inbound');
CREATE TYPE sync_status AS ENUM ('Pending', 'Success', 'Failed', 'Retrying');
CREATE TYPE sync_operation AS ENUM ('Create', 'Update', 'Delete', 'Verify');
CREATE TYPE ehr_vendor AS ENUM ('Epic', 'Cerner', 'AthenaHealth', 'Allscripts', 'Custom', 'Other');
CREATE TYPE auth_mode AS ENUM ('None', 'OAuth2', 'Basic', 'Certificate', 'APIKey');

CREATE TYPE consent_scope AS ENUM ('EHR_DATA_SHARING', 'SMS_REMINDERS', 'VOICE_RECORDINGS', 'QUESTIONNAIRE_ANSWERS');
CREATE TYPE consent_source AS ENUM ('Voice', 'Chat', 'Portal', 'Paper', 'Admin');
CREATE TYPE notification_channel AS ENUM ('Voice', 'SMS', 'Email', 'Push');
CREATE TYPE notification_status AS ENUM ('Queued', 'Sent', 'Delivered', 'Failed', 'Suppressed');
CREATE TYPE actor_type AS ENUM ('AdminUser', 'Patient', 'System', 'AIAgent', 'EHR');
-- ---------------------------------------------------------------------------
-- 1. Tenancy & organization
-- ---------------------------------------------------------------------------

CREATE TABLE tenants (
  tenant_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name             text NOT NULL,
  slug             text NOT NULL,
  status           tenant_status NOT NULL DEFAULT 'Active',
  default_timezone text NOT NULL DEFAULT 'UTC',
  settings         jsonb NOT NULL DEFAULT '{}',
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT tenants_slug_uniq UNIQUE (slug)
);
COMMENT ON TABLE tenants IS 'A hospital network / customer organisation (the multi-tenant root).';

CREATE TABLE hospitals (
  hospital_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
  name        text NOT NULL,
  code        text NOT NULL,
  address     jsonb NOT NULL DEFAULT '{}',
  timezone    text NOT NULL DEFAULT 'UTC',
  status      record_status NOT NULL DEFAULT 'Active',
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT hospitals_tenant_code_uniq UNIQUE (tenant_id, code)
);
COMMENT ON TABLE hospitals IS 'A physical facility / branch inside a tenant network.';
CREATE INDEX hospitals_tenant_idx ON hospitals (tenant_id);

CREATE TABLE admin_users (
  admin_user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
  hospital_id   uuid REFERENCES hospitals (hospital_id) ON DELETE SET NULL,
  full_name     text NOT NULL,
  email         text NOT NULL,
  role          user_role NOT NULL,
  scopes        text[] NOT NULL DEFAULT '{}',
  status        record_status NOT NULL DEFAULT 'Active',
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE admin_users IS 'Platform / tenant administrators and operational staff.';
CREATE INDEX admin_users_hospital_idx ON admin_users (hospital_id) WHERE hospital_id IS NOT NULL;
CREATE UNIQUE INDEX admin_users_tenant_email_uidx ON admin_users (tenant_id, (lower(email)));
-- ---------------------------------------------------------------------------
-- 2. Provider directory
-- ---------------------------------------------------------------------------

CREATE TABLE doctors (
  doctor_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
  ehr_doctor_id  text,
  first_name     text NOT NULL,
  last_name      text NOT NULL,
  suffix         text,
  specialty      text NOT NULL,
  license_number text,
  languages      text[] NOT NULL DEFAULT ARRAY['en'],
  status         record_status NOT NULL DEFAULT 'Active',
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE doctors IS 'Providers; specialty kept as text to match the conversational schemas.';
CREATE INDEX doctors_tenant_specialty_idx ON doctors (tenant_id, specialty);

CREATE TABLE doctor_hospital_affiliations (
  affiliation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doctor_id      uuid NOT NULL REFERENCES doctors (doctor_id) ON DELETE CASCADE,
  hospital_id    uuid NOT NULL REFERENCES hospitals (hospital_id) ON DELETE CASCADE,
  is_primary     boolean NOT NULL DEFAULT false,
  status         record_status NOT NULL DEFAULT 'Active',
  created_at     timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE doctor_hospital_affiliations IS 'Many-to-many doctor <-> facility membership.';
CREATE INDEX doctor_hospital_affiliation_hospital_idx ON doctor_hospital_affiliations (hospital_id);
CREATE UNIQUE INDEX doctor_hospital_affiliation_uidx ON doctor_hospital_affiliations (doctor_id, hospital_id) WHERE status = 'Active';

CREATE TABLE patients (
  patient_id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
  ehr_patient_id         text,
  first_name             text NOT NULL,
  last_name              text NOT NULL,
  date_of_birth          date,
  phone                  text NOT NULL,
  email                  text,
  preferred_hospital_id  uuid REFERENCES hospitals (hospital_id) ON DELETE SET NULL,
  preferred_doctor_id    uuid REFERENCES doctors (doctor_id) ON DELETE SET NULL,
  communication_preference notification_channel NOT NULL DEFAULT 'Voice',
  language               text NOT NULL DEFAULT 'en',
  status                 record_status NOT NULL DEFAULT 'Active',
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE patients IS 'Patient demographic + contact + communication profile.';
CREATE INDEX patients_tenant_idx ON patients (tenant_id);
CREATE UNIQUE INDEX patients_tenant_phone_uidx ON patients (tenant_id, phone) WHERE status = 'Active';
CREATE UNIQUE INDEX patients_tenant_ehr_uidx ON patients (tenant_id, ehr_patient_id) WHERE ehr_patient_id IS NOT NULL;
-- ---------------------------------------------------------------------------
-- 3. Scheduling (templates -> materialised slots -> appointments)
-- ---------------------------------------------------------------------------

CREATE TABLE availability_templates (
  template_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doctor_id             uuid NOT NULL REFERENCES doctors (doctor_id) ON DELETE CASCADE,
  hospital_id           uuid NOT NULL REFERENCES hospitals (hospital_id) ON DELETE CASCADE,
  day_of_week           availability_day NOT NULL,
  start_time            time NOT NULL,
  end_time              time NOT NULL,
  slot_duration_minutes integer NOT NULL DEFAULT 30,
  buffer_minutes        integer NOT NULL DEFAULT 0,
  appointment_type      text,
  is_active             boolean NOT NULL DEFAULT true,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT availability_template_time_check     CHECK (start_time < end_time),
  CONSTRAINT availability_template_duration_check CHECK (slot_duration_minutes BETWEEN 5 AND 240),
  CONSTRAINT availability_template_buffer_check   CHECK (buffer_minutes >= 0)
);
COMMENT ON TABLE availability_templates IS 'Recurring weekly availability rules used to materialise concrete time_slots.';
CREATE INDEX availability_templates_doctor_idx ON availability_templates (doctor_id, day_of_week) WHERE is_active;

CREATE TABLE time_slots (
  slot_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
  doctor_id        uuid NOT NULL REFERENCES doctors (doctor_id) ON DELETE CASCADE,
  hospital_id      uuid NOT NULL REFERENCES hospitals (hospital_id) ON DELETE CASCADE,
  template_id      uuid REFERENCES availability_templates (template_id) ON DELETE SET NULL,
  start_time       timestamptz NOT NULL,
  end_time         timestamptz NOT NULL,
  appointment_type text,
  status           slot_status NOT NULL DEFAULT 'Open',
  hold_until       timestamptz,
  hold_token       uuid,
  row_version      integer NOT NULL DEFAULT 0,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT time_slot_time_check    CHECK (start_time < end_time)
);
COMMENT ON TABLE time_slots IS 'Materialised bookable slots; row_version + status + hold_token/until drive optimistic locking.';
CREATE INDEX time_slots_tenant_idx        ON time_slots (tenant_id);
CREATE INDEX time_slots_bookable_idx      ON time_slots (doctor_id, hospital_id, start_time) WHERE status IN ('Open', 'Held');
CREATE INDEX time_slots_hold_expiry_idx   ON time_slots (hold_until) WHERE status = 'Held';
CREATE UNIQUE INDEX time_slot_dedupe_uidx ON time_slots (doctor_id, start_time) WHERE status <> 'Cancelled';

CREATE TABLE appointments (
  appointment_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id               uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
  external_appointment_id text,
  patient_id              uuid NOT NULL REFERENCES patients (patient_id) ON DELETE RESTRICT,
  hospital_id             uuid NOT NULL REFERENCES hospitals (hospital_id) ON DELETE RESTRICT,
  doctor_id               uuid NOT NULL REFERENCES doctors (doctor_id) ON DELETE RESTRICT,
  calendar_slot_id        uuid NOT NULL REFERENCES time_slots (slot_id) ON DELETE RESTRICT,
  appointment_type        text NOT NULL DEFAULT 'Standard',
  start_time              timestamptz NOT NULL,
  end_time                timestamptz NOT NULL,
  status                  appointment_status NOT NULL DEFAULT 'Requested',
  verification_status     verification_status NOT NULL DEFAULT 'UNVERIFIED',
  idempotency_key         text,
  cancelled_by            text,
  cancel_reason           text,
  created_at              timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT appointment_time_check        CHECK (start_time < end_time)
);
COMMENT ON TABLE appointments IS 'Transactional appointment state + EHR verification + exactly-once idempotency guard.';
CREATE INDEX appointments_patient_time_idx ON appointments (patient_id, start_time DESC);
CREATE INDEX appointments_doctor_time_idx  ON appointments (doctor_id, start_time);
CREATE INDEX appointments_tenant_status_idx ON appointments (tenant_id, status);
CREATE UNIQUE INDEX appointment_slot_uidx ON appointments (calendar_slot_id) WHERE status NOT IN ('Cancelled', 'Failed');
CREATE UNIQUE INDEX appointment_idempotency_uidx ON appointments (idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX appointments_verification_idx ON appointments (verification_status) WHERE verification_status <> 'EHR_VERIFIED';
-- ---------------------------------------------------------------------------
-- 4. Active conversational state & history
--    (mirrors ./schemas/conversational_state.json)
-- ---------------------------------------------------------------------------

CREATE TABLE conversation_sessions (
  session_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
  patient_id    uuid REFERENCES patients (patient_id) ON DELETE SET NULL,
  channel       conversation_channel NOT NULL,
  status        session_status NOT NULL DEFAULT 'Active',
  started_at    timestamptz NOT NULL DEFAULT now(),
  ended_at      timestamptz,
  transcript_uri text
);
COMMENT ON TABLE conversation_sessions IS 'One patient voice/chat session end to end.';
CREATE INDEX conversation_sessions_patient_idx ON conversation_sessions (patient_id, started_at DESC);

CREATE TABLE conversation_messages (
  message_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id      uuid NOT NULL REFERENCES conversation_sessions (session_id) ON DELETE CASCADE,
  role            message_role NOT NULL,
  content         text NOT NULL DEFAULT '',
  tool_calls      jsonb,
  intent_snapshot jsonb,
  created_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE conversation_messages IS 'Immutable message log; intent_snapshot captures ConversationalState at emit time.';
CREATE INDEX conversation_messages_session_idx ON conversation_messages (session_id, created_at);

CREATE TABLE conversational_states (
  session_id           uuid PRIMARY KEY REFERENCES conversation_sessions (session_id) ON DELETE CASCADE,
  patient_id           uuid REFERENCES patients (patient_id) ON DELETE SET NULL,
  intent               conversation_intent NOT NULL,
  specialty            text,
  date                 date,
  time_preference      time_preference,
  selected_hospital_id uuid REFERENCES hospitals (hospital_id) ON DELETE SET NULL,
  selected_doctor_id   uuid REFERENCES doctors (doctor_id) ON DELETE SET NULL,
  selected_slot_id     uuid REFERENCES time_slots (slot_id) ON DELETE SET NULL,
  appointment_status   conversation_appointment_status NOT NULL DEFAULT 'Pending',
  updated_at           timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE conversational_states IS 'Short-lived interaction variables for the active session (1 row per session).';
CREATE INDEX conversational_states_updated_idx ON conversational_states (updated_at);

CREATE TABLE escalations (
  escalation_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id           uuid NOT NULL REFERENCES conversation_sessions (session_id) ON DELETE CASCADE,
  reason               text NOT NULL,
  destination_ref      text,
  status               escalation_status NOT NULL DEFAULT 'Open',
  resolved_by_admin_id uuid REFERENCES admin_users (admin_user_id) ON DELETE SET NULL,
  resolution_note      text,
  created_at           timestamptz NOT NULL DEFAULT now(),
  resolved_at          timestamptz
);
COMMENT ON TABLE escalations IS 'Human handoff linked to the originating conversation.';
CREATE INDEX escalations_status_idx ON escalations (status, created_at);
-- ---------------------------------------------------------------------------
-- 5. Pre-visit questionnaires (definition -> response)
-- ---------------------------------------------------------------------------

CREATE TABLE questionnaire_definitions (
  questionnaire_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
  doctor_id        uuid NOT NULL REFERENCES doctors (doctor_id) ON DELETE CASCADE,
  title            text NOT NULL,
  specialty        text,
  version          integer NOT NULL DEFAULT 1,
  questions        jsonb NOT NULL,
  is_active        boolean NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT questionnaire_definition_uniq UNIQUE (doctor_id, title, version)
);
COMMENT ON TABLE questionnaire_definitions IS 'questions JSONB: [{question_id, prompt_text, response_type, options[], is_required}] per ./schemas/questionnaire_definition.json';
CREATE INDEX questionnaire_definitions_specialty_idx ON questionnaire_definitions (specialty);

CREATE TABLE questionnaire_responses (
  response_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  questionnaire_id uuid NOT NULL REFERENCES questionnaire_definitions (questionnaire_id) ON DELETE RESTRICT,
  appointment_id   uuid NOT NULL REFERENCES appointments (appointment_id) ON DELETE CASCADE,
  patient_id       uuid NOT NULL REFERENCES patients (patient_id) ON DELETE RESTRICT,
  answers          jsonb NOT NULL,
  completed_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT questionnaire_response_appointment_uniq UNIQUE (appointment_id)
);
COMMENT ON TABLE questionnaire_responses IS 'answers JSONB: [{question_id, raw_patient_input, structured_value}] per ./schemas/questionnaire_response.json';
CREATE INDEX questionnaire_responses_patient_idx ON questionnaire_responses (patient_id);
-- ---------------------------------------------------------------------------
-- 6. External EHR system integration
-- ---------------------------------------------------------------------------

CREATE TABLE ehr_systems (
  ehr_system_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
  vendor        ehr_vendor NOT NULL,
  name          text NOT NULL,
  base_url      text,
  auth_mode     auth_mode NOT NULL DEFAULT 'OAuth2',
  status        record_status NOT NULL DEFAULT 'Active',
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE ehr_systems IS 'Registered external EHR vendor instance (Epic/Cerner/...).';

CREATE TABLE ehr_connections (
  connection_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ehr_system_id       uuid NOT NULL REFERENCES ehr_systems (ehr_system_id) ON DELETE CASCADE,
  hospital_id         uuid NOT NULL REFERENCES hospitals (hospital_id) ON DELETE CASCADE,
  credentials_ref     text,
  webhook_secret_ref  text,
  status              record_status NOT NULL DEFAULT 'Active',
  last_health_check_at timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ehr_connection_system_hospital_uniq UNIQUE (ehr_system_id, hospital_id)
);
COMMENT ON TABLE ehr_connections IS 'Per-facility EHR handle; secrets live in an external vault, never inline.';
CREATE INDEX ehr_connections_hospital_idx ON ehr_connections (hospital_id);

CREATE TABLE ehr_entity_mappings (
  mapping_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
  connection_id      uuid NOT NULL REFERENCES ehr_connections (connection_id) ON DELETE CASCADE,
  local_entity_type  text NOT NULL,
  local_entity_id    uuid NOT NULL,
  remote_entity_type text NOT NULL,
  remote_entity_id   text NOT NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ehr_entity_mapping_uniq UNIQUE (connection_id, local_entity_type, local_entity_id)
);
COMMENT ON TABLE ehr_entity_mappings IS 'PK bridge between platform UUIDs and remote EHR identifiers.';
CREATE INDEX ehr_entity_mappings_remote_idx ON ehr_entity_mappings (connection_id, remote_entity_type, remote_entity_id);

CREATE TABLE ehr_sync_logs (
  sync_log_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id uuid NOT NULL REFERENCES ehr_connections (connection_id) ON DELETE CASCADE,
  mapping_id    uuid REFERENCES ehr_entity_mappings (mapping_id) ON DELETE SET NULL,
  direction     sync_direction NOT NULL,
  entity_type   text NOT NULL,
  entity_id     uuid NOT NULL,
  operation     sync_operation NOT NULL,
  status        sync_status NOT NULL DEFAULT 'Pending',
  request_ref   text,
  error_detail  text,
  attempts      integer NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now(),
  completed_at  timestamptz
);
COMMENT ON TABLE ehr_sync_logs IS 'Outbox-style audit of every outbound/inbound EHR exchange; drives retries + reconciliation.';
CREATE INDEX ehr_sync_logs_queue_idx ON ehr_sync_logs (connection_id, status) WHERE status IN ('Pending', 'Retrying', 'Failed');
CREATE INDEX ehr_sync_logs_entity_idx ON ehr_sync_logs (entity_type, entity_id);
-- ---------------------------------------------------------------------------
-- 7. Consent, audit & notifications
-- ---------------------------------------------------------------------------

CREATE TABLE patient_consents (
  consent_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients (patient_id) ON DELETE CASCADE,
  scope      consent_scope NOT NULL,
  granted    boolean NOT NULL DEFAULT true,
  granted_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  source     consent_source NOT NULL DEFAULT 'Portal',
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE patient_consents IS 'Current consent per (patient, scope); revoke by setting granted=false / revoked_at.';
CREATE UNIQUE INDEX patient_consent_current_uidx ON patient_consents (patient_id, scope) WHERE granted AND revoked_at IS NULL;

CREATE TABLE audit_logs (
  audit_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
  actor_type  actor_type NOT NULL,
  actor_id    text,
  action      text NOT NULL,
  entity_type text NOT NULL,
  entity_id   text,
  metadata    jsonb,
  ip_address  inet,
  created_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE audit_logs IS 'Append-only operational + clinical audit trail (write-only for the app role).';
CREATE INDEX audit_logs_tenant_time_idx ON audit_logs (tenant_id, created_at DESC);

CREATE TABLE notifications (
  notification_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
  patient_id          uuid NOT NULL REFERENCES patients (patient_id) ON DELETE CASCADE,
  channel             notification_channel NOT NULL,
  template_key        text NOT NULL,
  payload             jsonb,
  status              notification_status NOT NULL DEFAULT 'Queued',
  provider_message_id text,
  sent_at             timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE notifications IS 'Outbound engagement queue (SMS / email / push / outbound voice).';
CREATE INDEX notifications_queue_idx   ON notifications (status, created_at) WHERE status = 'Queued';
CREATE INDEX notifications_patient_idx ON notifications (patient_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- updated_at maintenance trigger
-- ---------------------------------------------------------------------------

CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER tenants_updated_at             BEFORE UPDATE ON tenants                FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER hospitals_updated_at           BEFORE UPDATE ON hospitals              FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER admin_users_updated_at         BEFORE UPDATE ON admin_users            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER doctors_updated_at             BEFORE UPDATE ON doctors                FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER patients_updated_at            BEFORE UPDATE ON patients               FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER availability_templates_updated_at BEFORE UPDATE ON availability_templates FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER time_slots_updated_at          BEFORE UPDATE ON time_slots             FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER appointments_updated_at        BEFORE UPDATE ON appointments           FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER conversational_states_updated_at BEFORE UPDATE ON conversational_states FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER questionnaire_definitions_updated_at BEFORE UPDATE ON questionnaire_definitions FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER ehr_systems_updated_at         BEFORE UPDATE ON ehr_systems            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER ehr_connections_updated_at     BEFORE UPDATE ON ehr_connections        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
-- ---------------------------------------------------------------------------
-- Slot materialisation job
-- Materialises concrete time_slots from recurring availability templates for a
-- date range. Run in a session whose TIME ZONE matches the hospital timezone.
-- ---------------------------------------------------------------------------

CREATE FUNCTION materialize_slots(p_start date, p_end date) RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  cur_day date := p_start;
  tpl     record;
  slot_ts timestamptz;
  slot_end timestamptz;
  n       integer := 0;
  n_ins   integer;
BEGIN
  WHILE cur_day <= p_end LOOP
    FOR tpl IN
      SELECT template_id, doctor_id, hospital_id, start_time, end_time,
             slot_duration_minutes, appointment_type
        FROM availability_templates
       WHERE is_active
         AND day_of_week::text = to_char(cur_day, 'FMDay')
    LOOP
      slot_ts  := (cur_day::timestamp + tpl.start_time)::timestamptz;
      slot_end := (cur_day::timestamp + tpl.end_time)::timestamptz;
      WHILE (slot_ts + make_interval(mins => tpl.slot_duration_minutes)) <= slot_end LOOP
        INSERT INTO time_slots (tenant_id, doctor_id, hospital_id, template_id,
                                start_time, end_time, appointment_type)
        SELECT tenant_id, tpl.doctor_id, tpl.hospital_id, tpl.template_id,
               slot_ts,
               slot_ts + make_interval(mins => tpl.slot_duration_minutes),
               tpl.appointment_type
          FROM doctors
         WHERE doctor_id = tpl.doctor_id
           AND NOT EXISTS (SELECT 1 FROM time_slots x WHERE x.doctor_id = tpl.doctor_id AND x.start_time = slot_ts);
        GET DIAGNOSTICS n_ins = ROW_COUNT;
        n := n + n_ins;
        slot_ts := slot_ts + make_interval(mins => tpl.slot_duration_minutes);
      END LOOP;
    END LOOP;
    cur_day := cur_day + 1;
  END LOOP;
  RETURN n;
END;
$$;
-- ---------------------------------------------------------------------------
-- 8. Multi-tenant Row-Level Security
-- The application connects as a NON-OWNER role (see database/README.md) and
-- sets the session-scoped GUC before running queries:
--     SET app.tenant_id = '<tenant-uuid>';          -- entire session
--     SET LOCAL app.tenant_id = '<tenant-uuid>';    -- current txn (PG16+)
-- RLS is FORCE-enforced: even the table owner must satisfy the policies.
-- Superusers (postgres / migration runner) always bypass RLS.
-- ---------------------------------------------------------------------------

CREATE FUNCTION app_tenant_id() RETURNS uuid
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN NULLIF(current_setting('app.tenant_id'), '')::uuid;
EXCEPTION WHEN OTHERS THEN
  RETURN NULL;
END;
$$;

-- Tenants: an app session can read/update only its own tenant row; onboarding
-- inserts its own tenant during bootstrap.
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY tenants_self_select ON tenants FOR SELECT USING (tenant_id = app_tenant_id());
CREATE POLICY tenants_self_insert ON tenants FOR INSERT WITH CHECK (tenant_id = app_tenant_id());
CREATE POLICY tenants_self_update ON tenants FOR UPDATE USING (tenant_id = app_tenant_id());

-- Tables carrying a direct tenant_id column: enable RLS + FORCE + standard
-- SELECT/INSERT/UPDATE policies in one place.
DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'hospitals', 'admin_users', 'doctors', 'patients',
    'time_slots', 'appointments',
    'conversation_sessions',
    'questionnaire_definitions',
    'ehr_systems', 'ehr_entity_mappings', 'notifications'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', t);
    EXECUTE format('CREATE POLICY %I_tenant_select ON %I FOR SELECT USING (tenant_id = app_tenant_id());', t, t);
    EXECUTE format('CREATE POLICY %I_tenant_insert ON %I FOR INSERT WITH CHECK (tenant_id = app_tenant_id());', t, t);
    EXECUTE format('CREATE POLICY %I_tenant_update ON %I FOR UPDATE USING (tenant_id = app_tenant_id());', t, t);
  END LOOP;
END
$$;
-- conversational_states resolves tenant through its parent conversation_session.
ALTER TABLE conversational_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversational_states FORCE ROW LEVEL SECURITY;
CREATE POLICY conversational_states_tenant_select ON conversational_states FOR SELECT
  USING (EXISTS (SELECT 1 FROM conversation_sessions s WHERE s.session_id = conversational_states.session_id AND s.tenant_id = app_tenant_id()));
CREATE POLICY conversational_states_tenant_insert ON conversational_states FOR INSERT WITH CHECK
  (EXISTS (SELECT 1 FROM conversation_sessions s WHERE s.session_id = conversational_states.session_id AND s.tenant_id = app_tenant_id()));
CREATE POLICY conversational_states_tenant_update ON conversational_states FOR UPDATE
  USING (EXISTS (SELECT 1 FROM conversation_sessions s WHERE s.session_id = conversational_states.session_id AND s.tenant_id = app_tenant_id()));

-- questionnaire_responses resolves tenant through the patient.
ALTER TABLE questionnaire_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE questionnaire_responses FORCE ROW LEVEL SECURITY;
CREATE POLICY questionnaire_responses_tenant_select ON questionnaire_responses FOR SELECT
  USING (EXISTS (SELECT 1 FROM patients p WHERE p.patient_id = questionnaire_responses.patient_id AND p.tenant_id = app_tenant_id()));
CREATE POLICY questionnaire_responses_tenant_insert ON questionnaire_responses FOR INSERT WITH CHECK
  (EXISTS (SELECT 1 FROM patients p WHERE p.patient_id = questionnaire_responses.patient_id AND p.tenant_id = app_tenant_id()));
CREATE POLICY questionnaire_responses_tenant_update ON questionnaire_responses FOR UPDATE
  USING (EXISTS (SELECT 1 FROM patients p WHERE p.patient_id = questionnaire_responses.patient_id AND p.tenant_id = app_tenant_id()));
-- availability_templates carries no tenant_id column; resolve tenant via hospital.
ALTER TABLE availability_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE availability_templates FORCE ROW LEVEL SECURITY;
CREATE POLICY availability_templates_tenant_select ON availability_templates FOR SELECT
  USING (EXISTS (SELECT 1 FROM hospitals h WHERE h.hospital_id = availability_templates.hospital_id AND h.tenant_id = app_tenant_id()));
CREATE POLICY availability_templates_tenant_insert ON availability_templates FOR INSERT WITH CHECK
  (EXISTS (SELECT 1 FROM hospitals h WHERE h.hospital_id = availability_templates.hospital_id AND h.tenant_id = app_tenant_id()));
CREATE POLICY availability_templates_tenant_update ON availability_templates FOR UPDATE
  USING (EXISTS (SELECT 1 FROM hospitals h WHERE h.hospital_id = availability_templates.hospital_id AND h.tenant_id = app_tenant_id()));

-- audit_logs: append-only for the app role (SELECT + INSERT only, no UPDATE).
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_logs_tenant_select ON audit_logs FOR SELECT USING (tenant_id = app_tenant_id());
CREATE POLICY audit_logs_tenant_insert ON audit_logs FOR INSERT WITH CHECK (tenant_id = app_tenant_id());

-- Tables without a tenant_id column (tenant resolved through the FK chain).
ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_messages FORCE ROW LEVEL SECURITY;
CREATE POLICY conversation_messages_tenant_select ON conversation_messages FOR SELECT
  USING (EXISTS (SELECT 1 FROM conversation_sessions s
                  WHERE s.session_id = conversation_messages.session_id
                    AND s.tenant_id = app_tenant_id()));
CREATE POLICY conversation_messages_tenant_insert ON conversation_messages FOR INSERT WITH CHECK
  (EXISTS (SELECT 1 FROM conversation_sessions s
            WHERE s.session_id = conversation_messages.session_id
              AND s.tenant_id = app_tenant_id()));
-- messages are immutable: no UPDATE/DELETE policies.

ALTER TABLE escalations ENABLE ROW LEVEL SECURITY;
ALTER TABLE escalations FORCE ROW LEVEL SECURITY;
CREATE POLICY escalations_tenant_select ON escalations FOR SELECT
  USING (EXISTS (SELECT 1 FROM conversation_sessions s WHERE s.session_id = escalations.session_id AND s.tenant_id = app_tenant_id()));
CREATE POLICY escalations_tenant_insert ON escalations FOR INSERT WITH CHECK
  (EXISTS (SELECT 1 FROM conversation_sessions s WHERE s.session_id = escalations.session_id AND s.tenant_id = app_tenant_id()));
CREATE POLICY escalations_tenant_update ON escalations FOR UPDATE
  USING (EXISTS (SELECT 1 FROM conversation_sessions s WHERE s.session_id = escalations.session_id AND s.tenant_id = app_tenant_id()));

ALTER TABLE ehr_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE ehr_connections FORCE ROW LEVEL SECURITY;
CREATE POLICY ehr_connections_tenant_select ON ehr_connections FOR SELECT
  USING (EXISTS (SELECT 1 FROM hospitals h WHERE h.hospital_id = ehr_connections.hospital_id AND h.tenant_id = app_tenant_id()));
CREATE POLICY ehr_connections_tenant_insert ON ehr_connections FOR INSERT WITH CHECK
  (EXISTS (SELECT 1 FROM hospitals h WHERE h.hospital_id = ehr_connections.hospital_id AND h.tenant_id = app_tenant_id()));
CREATE POLICY ehr_connections_tenant_update ON ehr_connections FOR UPDATE
  USING (EXISTS (SELECT 1 FROM hospitals h WHERE h.hospital_id = ehr_connections.hospital_id AND h.tenant_id = app_tenant_id()));

ALTER TABLE ehr_sync_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ehr_sync_logs FORCE ROW LEVEL SECURITY;
CREATE POLICY ehr_sync_logs_tenant_select ON ehr_sync_logs FOR SELECT
  USING (EXISTS (SELECT 1 FROM ehr_connections c
                  JOIN hospitals h ON h.hospital_id = c.hospital_id
                 WHERE c.connection_id = ehr_sync_logs.connection_id
                   AND h.tenant_id = app_tenant_id()));
CREATE POLICY ehr_sync_logs_tenant_insert ON ehr_sync_logs FOR INSERT WITH CHECK
  (EXISTS (SELECT 1 FROM ehr_connections c
            JOIN hospitals h ON h.hospital_id = c.hospital_id
           WHERE c.connection_id = ehr_sync_logs.connection_id
             AND h.tenant_id = app_tenant_id()));
CREATE POLICY ehr_sync_logs_tenant_update ON ehr_sync_logs FOR UPDATE
  USING (EXISTS (SELECT 1 FROM ehr_connections c
                  JOIN hospitals h ON h.hospital_id = c.hospital_id
                 WHERE c.connection_id = ehr_sync_logs.connection_id
                   AND h.tenant_id = app_tenant_id()));

ALTER TABLE patient_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_consents FORCE ROW LEVEL SECURITY;
CREATE POLICY patient_consents_tenant_select ON patient_consents FOR SELECT
  USING (EXISTS (SELECT 1 FROM patients p WHERE p.patient_id = patient_consents.patient_id AND p.tenant_id = app_tenant_id()));
CREATE POLICY patient_consents_tenant_insert ON patient_consents FOR INSERT WITH CHECK
  (EXISTS (SELECT 1 FROM patients p WHERE p.patient_id = patient_consents.patient_id AND p.tenant_id = app_tenant_id()));
CREATE POLICY patient_consents_tenant_update ON patient_consents FOR UPDATE
  USING (EXISTS (SELECT 1 FROM patients p WHERE p.patient_id = patient_consents.patient_id AND p.tenant_id = app_tenant_id()));

COMMIT;
