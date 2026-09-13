-- Rig part 2: non-superuser role + rival-tenant fixture (run as superuser).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rig_app') THEN
    CREATE ROLE rig_app NOSUPERUSER;
  END IF;
END
$$;
GRANT ALL ON ALL TABLES IN SCHEMA public TO rig_app;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO rig_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rig_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO rig_app;
INSERT INTO tenants (tenant_id, name, slug)
VALUES ('aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee', 'Rival Network', 'rival-network')
ON CONFLICT (tenant_id) DO NOTHING;
INSERT INTO hospitals (hospital_id, tenant_id, name, code)
VALUES ('bbbbbbbb-1111-4222-8333-cccccccccccc', 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee', 'Rival Hospital', 'RIV')
ON CONFLICT (hospital_id) DO NOTHING;
