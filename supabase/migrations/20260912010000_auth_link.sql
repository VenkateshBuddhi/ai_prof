-- ============================================================================
-- ai_prof :: Supabase migration 02 - auth linkage, RLS gap closure, grants
-- Applies on Supabase hosted / CLI stack AFTER 01 baseline.
-- Needs platform roles (anon, authenticated, service_role) and auth.users -
-- both native on Supabase; stubbed on plain PG16 by the validation rig in
-- database/README.md section 11.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. RLS closure: doctor_hospital_affiliations (no tenant_id column, so the
-- baseline loop skipped it). Tenant resolved through the hospital side.
-- ---------------------------------------------------------------------------

ALTER TABLE doctor_hospital_affiliations ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctor_hospital_affiliations FORCE ROW LEVEL SECURITY;

CREATE POLICY dha_tenant_select ON doctor_hospital_affiliations FOR SELECT
  USING (EXISTS (SELECT 1 FROM hospitals h
                  WHERE h.hospital_id = doctor_hospital_affiliations.hospital_id
                    AND h.tenant_id = app_tenant_id()));
CREATE POLICY dha_tenant_insert ON doctor_hospital_affiliations FOR INSERT WITH CHECK
  (EXISTS (SELECT 1 FROM hospitals h
            WHERE h.hospital_id = doctor_hospital_affiliations.hospital_id
              AND h.tenant_id = app_tenant_id()));
CREATE POLICY dha_tenant_update ON doctor_hospital_affiliations FOR UPDATE
  USING (EXISTS (SELECT 1 FROM hospitals h
                  WHERE h.hospital_id = doctor_hospital_affiliations.hospital_id
                    AND h.tenant_id = app_tenant_id()));

-- ---------------------------------------------------------------------------
-- 2. Supabase Auth linkage: profile rows may point at auth.users(id)
-- ---------------------------------------------------------------------------

ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users (id) ON DELETE SET NULL;
ALTER TABLE patients    ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users (id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS admin_users_user_id_uidx ON admin_users (user_id) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS patients_user_id_uidx    ON patients (user_id) WHERE user_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. Signup trigger: provision a profile row from app_metadata.
-- Dashboard / API signup must set raw_app_meta_data, e.g.
--   {"tenant_id": "<uuid>", "profile_type": "patient" | "staff"}
-- Staff rows land as FRONT_DESK (least privilege); promote via admin tooling.
-- Unknown type / missing tenant: no row is created (fail closed).
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION handle_new_auth_user() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  tid   uuid;
  ptype text;
BEGIN
  ptype := NEW.raw_app_meta_data ->> 'profile_type';
  BEGIN
    tid := NULLIF(NEW.raw_app_meta_data ->> 'tenant_id', '')::uuid;
  EXCEPTION WHEN OTHERS THEN
    tid := NULL;
  END;

  IF tid IS NULL THEN
    RETURN NEW;
  ELSIF ptype = 'patient' THEN
    INSERT INTO patients (tenant_id, user_id, first_name, last_name, phone, email)
    VALUES (tid, NEW.id,
            COALESCE(NULLIF(NEW.raw_user_meta_data ->> 'first_name', ''), 'Unknown'),
            COALESCE(NULLIF(NEW.raw_user_meta_data ->> 'last_name', ''), 'Unknown'),
            COALESCE(NEW.phone, NEW.email, 'unknown'),
            NEW.email)
    ON CONFLICT DO NOTHING;
  ELSIF ptype = 'staff' THEN
    INSERT INTO admin_users (tenant_id, user_id, full_name, email, role)
    VALUES (tid, NEW.id,
            COALESCE(NULLIF(NEW.raw_user_meta_data ->> 'full_name', ''), NEW.email, 'Staff'),
            NEW.email, 'FRONT_DESK')
    ON CONFLICT DO NOTHING;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION handle_new_auth_user();
SELECT 'auth-link-ok' AS migration_02;

-- ---------------------------------------------------------------------------
-- 4. Convenience helpers for PostgREST / edge functions
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS uuid
LANGUAGE sql STABLE AS $$ SELECT app_tenant_id() $$;

CREATE OR REPLACE FUNCTION my_patient_id() RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$ SELECT patient_id FROM patients WHERE user_id = auth.uid() LIMIT 1 $$;

CREATE OR REPLACE FUNCTION my_admin_id() RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$ SELECT admin_user_id FROM admin_users WHERE user_id = auth.uid() LIMIT 1 $$;

-- ---------------------------------------------------------------------------
-- 5. PostgREST role grants.
-- Supabase hosted provides anon/authenticated/service_role natively; this
-- DO block applies the grants only when the roles exist, so the migration
-- also replays cleanly on plain PostgreSQL (validation rig, CI).
-- RLS still enforces tenant isolation for authenticated clients.
-- anon gets schema usage only: no direct PHI table access from browsers.
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
     AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
     AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    EXECUTE 'GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role';
    EXECUTE 'GRANT EXECUTE ON FUNCTION app_tenant_id() TO authenticated, service_role';
    EXECUTE 'GRANT EXECUTE ON FUNCTION current_tenant_id() TO authenticated, service_role';
    EXECUTE 'GRANT EXECUTE ON FUNCTION my_patient_id() TO authenticated, service_role';
    EXECUTE 'GRANT EXECUTE ON FUNCTION my_admin_id() TO authenticated, service_role';
    EXECUTE 'GRANT EXECUTE ON FUNCTION materialize_slots(date, date) TO authenticated, service_role';
    EXECUTE 'GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated, service_role';
    EXECUTE 'GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated, service_role';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO authenticated, service_role';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO authenticated, service_role';
  ELSE
    RAISE NOTICE 'PostgREST roles absent (plain Postgres rig): skipping role grants.';
  END IF;
END
$$;

REVOKE ALL ON FUNCTION app_tenant_id() FROM PUBLIC;
