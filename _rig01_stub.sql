-- Rig part 1: test-only auth stub + baseline migration + setup rows.
-- Run as superuser (postgres) with ON_ERROR_STOP=1.

-- 1. Test-only stub of the Supabase auth schema (real stack provides natively).
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (
  id uuid PRIMARY KEY,
  email text,
  phone text,
  raw_app_meta_data jsonb NOT NULL DEFAULT '{}',
  raw_user_meta_data jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb
LANGUAGE sql STABLE AS $$ SELECT NULLIF(current_setting('request.jwt.claims', true), '')::jsonb $$;
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
LANGUAGE sql STABLE AS $$ SELECT NULLIF((auth.jwt() ->> 'sub'), '')::uuid $$;
