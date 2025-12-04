--
-- PostgreSQL database dump
--

-- Local
--container_name: postgres_multi_tenant
--Host : host.docker.internal
--DATABASE_NAME=authz_db
--#DATABASE_USER=qlaws_app
--#DATABASE_PASSWORD=app_password
--port=5432


-- 1) Open a shell inside the container
docker exec -it postgres_multi_tenant bash

-- 2) From inside the container, connect as superuser
psql -U postgres -d postgres

-- 3) Create the login role used by your app
CREATE ROLE qlaws_app WITH LOGIN PASSWORD 'app_password';

 docker exec -it postgres_multi_tenant \
  psql -U postgres -d authz_db

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS pgcrypto;
SELECT pgp_sym_encrypt_bytea('secret-data'::bytea, 'my-passphrase');

  --pgp_sym_encrypt_bytea
--------------------------------------------------------------------------------------------------------------------------------------------------------------
-- \xc30d040703028b2e2669c017e7e467d23c013df23bcc09eaa443727b820c85604f83193690441470b77e60dbccc822565e90022fe311e137729c93fcc431b509ba733d66b28ce9ba17be539e44

ALTER DATABASE authz_db OWNER TO qlaws_app;
GRANT USAGE, CREATE ON SCHEMA public TO qlaws_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO qlaws_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO qlaws_app;




-- =============================================================================
-- 2. CORE IDENTITY MODULE (Tenants & Users)
-- =============================================================================

-- A. Tenants Table
CREATE TABLE IF NOT EXISTS tenants (
  tenant_id        uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name             text NOT NULL,
  domain           text UNIQUE,
  plan             text DEFAULT 'startup',
  region           text DEFAULT 'us-east-1',
  config           jsonb DEFAULT '{}'::jsonb,
  status           text DEFAULT 'active',
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT check_tenant_status CHECK (status IN ('active', 'suspended', 'deleted'))
);

-- B. Global Users Table
CREATE TABLE IF NOT EXISTS users (
  user_id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  primary_email    text NOT NULL,
  display_name     text,
  hashed_password  text NOT NULL,
  global_metadata  jsonb DEFAULT '{}'::jsonb,
  is_system        boolean NOT NULL DEFAULT false,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email ON users(lower(primary_email));

-- C. User-Tenant Link (The Pivot Table)
CREATE TABLE IF NOT EXISTS user_tenants (
  user_tenant_id   uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id        uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  user_id          uuid NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  tenant_email     text,
  tenant_role      text DEFAULT 'member', -- Basic role ('admin', 'member')
  status           text DEFAULT 'active',
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, user_id),
  CONSTRAINT check_ut_status CHECK (status IN ('invited', 'active', 'suspended'))
);

-- =============================================================================
-- 3. AUTHENTICATION MODULE (Sessions, Tokens, MFA)
-- =============================================================================

-- A. Sessions
CREATE TABLE IF NOT EXISTS sessions (
  session_id       uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_tenant_id   uuid NOT NULL REFERENCES user_tenants(user_tenant_id) ON DELETE CASCADE,
  tenant_id        uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  ip_address       inet,
  device_info      jsonb,
  revoked          boolean DEFAULT false,
  last_seen_at     timestamptz NOT NULL DEFAULT now(),
  created_at       timestamptz NOT NULL DEFAULT now()
);

-- B. Refresh Tokens
CREATE TABLE IF NOT EXISTS refresh_tokens (
  refresh_id       uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id       uuid NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  token_hash       text NOT NULL,
  expires_at       timestamptz NOT NULL,
  revoked          boolean DEFAULT false,
  created_at       timestamptz NOT NULL DEFAULT now()
);

-- C. Token Blacklist (For Logout/Revocation)
CREATE TABLE IF NOT EXISTS token_blacklist (
  jti              text PRIMARY KEY,
  tenant_id        uuid REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  revoked_at       timestamptz NOT NULL DEFAULT now(),
  expires_at       timestamptz -- Used for cleanup jobs
);
CREATE INDEX IF NOT EXISTS idx_token_blacklist_expires ON token_blacklist(expires_at);

-- D. Password Resets (Transient)
CREATE TABLE IF NOT EXISTS password_resets (
  reset_id         uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id          uuid NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  token_hash       text NOT NULL,
  expires_at       timestamptz NOT NULL,
  used_at          timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_password_resets_hash ON password_resets(token_hash) WHERE used_at IS NULL;

-- E. MFA Methods (TOTP)
CREATE TABLE IF NOT EXISTS mfa_methods (
  mfa_id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id          uuid NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  tenant_id        uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  method_type      text NOT NULL, -- 'totp'
  metadata         jsonb,         -- stores encrypted secret
  enabled          boolean DEFAULT false,
  created_at       timestamptz NOT NULL DEFAULT now()
);

-- =============================================================================
-- 4. RBAC MODULE (Roles & Permissions)
-- =============================================================================

CREATE TABLE IF NOT EXISTS roles (
  role_id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id        uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  name             text NOT NULL,
  description      text,
  is_builtin       boolean DEFAULT false,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS permissions (
  permission_id    uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  key              text NOT NULL UNIQUE, -- e.g., 'user.create'
  description      text,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS role_permissions (
  role_permission_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  role_id           uuid NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
  permission_id     uuid NOT NULL REFERENCES permissions(permission_id) ON DELETE CASCADE,
  UNIQUE (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
  user_role_id     uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_tenant_id   uuid NOT NULL REFERENCES user_tenants(user_tenant_id) ON DELETE CASCADE,
  role_id          uuid NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
  UNIQUE (user_tenant_id, role_id)
);

-- =============================================================================
-- 5. GROUPS MODULE
-- =============================================================================

CREATE TABLE IF NOT EXISTS groups (
  group_id         uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id        uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  name             text NOT NULL,
  description      text,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS group_members (
  group_member_id  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  group_id         uuid NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
  user_tenant_id   uuid NOT NULL REFERENCES user_tenants(user_tenant_id) ON DELETE CASCADE,
  UNIQUE (group_id, user_tenant_id)
);

CREATE TABLE IF NOT EXISTS group_roles (
  group_role_id    uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  group_id         uuid NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
  role_id          uuid NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
  UNIQUE (group_id, role_id)
);

-- =============================================================================
-- 6. INTEGRATIONS (SSO & API Keys)
-- =============================================================================

CREATE TABLE IF NOT EXISTS sso_providers (
  sso_id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id        uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  provider_type    text NOT NULL, -- 'oidc', 'saml'
  name             text NOT NULL,
  config           jsonb NOT NULL, -- Contains encrypted client_secret
  is_default       boolean DEFAULT false,
  enabled          boolean DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_keys (
  api_key_id       uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id        uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  name             text NOT NULL,
  key_hash         text NOT NULL,
  prefix           text NOT NULL,
  scopes           text[] DEFAULT '{}',
  last_used_at     timestamptz,
  expires_at       timestamptz,
  revoked          boolean DEFAULT false,
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(prefix) WHERE revoked = false;

-- =============================================================================
-- 7. OPERATIONS (Audit Logs)
-- =============================================================================

CREATE TABLE IF NOT EXISTS audit_logs (
  audit_id         uuid DEFAULT uuid_generate_v4(),
  tenant_id        uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  actor_user_id    uuid, -- Nullable (system actions)
  action_type      text NOT NULL,
  resource_type    text,
  resource_id      text,
  details          jsonb DEFAULT '{}'::jsonb,
  ip_address       text,
  event_time       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (event_time, audit_id)
) PARTITION BY RANGE (event_time);

-- Create default and initial partition
CREATE TABLE IF NOT EXISTS audit_logs_default PARTITION OF audit_logs DEFAULT;
CREATE TABLE IF NOT EXISTS audit_logs_2025_11 PARTITION OF audit_logs
  FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');





CREATE TABLE public.mfa_challenges (
    challenge_id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    mfa_method_id uuid,
    challenge_token text NOT NULL,
    challenge_type text NOT NULL,
    is_verified boolean DEFAULT false,
    attempts integer DEFAULT 0,
    max_attempts integer DEFAULT 3,
    ip_address text,
    user_agent text,
    verified_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    expires_at timestamp with time zone NOT NULL
);


ALTER TABLE public.mfa_challenges OWNER TO qlaws_app;




CREATE TABLE public.scim_configurations (
    scim_config_id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    scim_endpoint_url text NOT NULL,
    scim_version text DEFAULT '2.0'::text,
    bearer_token text NOT NULL,
    auth_type text DEFAULT 'bearer'::text,
    is_enabled boolean DEFAULT true,
    auto_provision boolean DEFAULT true,
    auto_deprovision boolean DEFAULT false,
    attribute_mapping jsonb DEFAULT '{}'::jsonb,
    group_mapping jsonb DEFAULT '{}'::jsonb,
    sync_frequency_minutes integer DEFAULT 60,
    last_sync_at timestamp with time zone,
    last_sync_status text,
    last_sync_error text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.scim_configurations OWNER TO qlaws_app;

--
-- Name: scim_sync_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.scim_sync_logs (
    sync_log_id uuid DEFAULT gen_random_uuid() NOT NULL,
    scim_config_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    operation text NOT NULL,
    resource_type text,
    resource_id uuid,
    external_id text,
    status text,
    error_message text,
    request_payload jsonb,
    response_payload jsonb,
    started_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    completed_at timestamp with time zone,
    duration_ms integer
);


ALTER TABLE public.scim_sync_logs OWNER TO qlaws_app;


-- =============================================================================
-- 8. ROW LEVEL SECURITY (RLS) POLICIES
-- =============================================================================

-- --- Function helper for safe context reading ---
-- (Optional, but useful if you want strictly typed uuid returns)

-- Enable RLS on All Tenant Tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE mfa_methods ENABLE ROW LEVEL SECURITY;
ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE group_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE group_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE sso_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Force RLS (Applies even to table owners/superusers to prevent accidental leaks)
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE user_tenants FORCE ROW LEVEL SECURITY;
-- (Repeat FORCE for all tables above in production)

-- --- Policy Definitions ---

-- 1. Tenants Table
-- INSERT: Allow everyone (Onboarding)
DROP POLICY IF EXISTS tenant_insert_policy ON tenants;
CREATE POLICY tenant_insert_policy ON tenants FOR INSERT WITH CHECK (true);
-- SELECT/UPDATE: Restrict to current tenant context
DROP POLICY IF EXISTS tenant_select_policy ON tenants;
CREATE POLICY tenant_select_policy ON tenants FOR SELECT
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
DROP POLICY IF EXISTS tenant_update_policy ON tenants;
CREATE POLICY tenant_update_policy ON tenants FOR UPDATE
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- 2. Standard Tenant Tables (Sessions, SSO, MFA, Groups, Roles)
-- These tables simply check if their 'tenant_id' column matches the session variable.
CREATE POLICY tenant_isolation_policy ON user_tenants FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_policy ON sessions FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_policy ON mfa_methods FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_policy ON roles FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_policy ON groups FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_policy ON sso_providers FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_policy ON api_keys FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_policy ON audit_logs FOR SELECT
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
-- Allow Insert on Audit Logs (System writes)
CREATE POLICY tenant_insert_policy ON audit_logs FOR INSERT WITH CHECK (true);

-- 3. Junction Tables (Indirect Links)
-- These check the parent table's tenant_id
CREATE POLICY tenant_isolation_policy ON user_roles FOR ALL
  USING (
    EXISTS (SELECT 1 FROM user_tenants ut WHERE ut.user_tenant_id = user_roles.user_tenant_id AND ut.tenant_id = current_setting('app.current_tenant_id', true)::uuid)
  );

CREATE POLICY tenant_isolation_policy ON group_members FOR ALL
  USING (
    EXISTS (SELECT 1 FROM groups g WHERE g.group_id = group_members.group_id AND g.tenant_id = current_setting('app.current_tenant_id', true)::uuid)
  );

CREATE POLICY tenant_isolation_policy ON group_roles FOR ALL
  USING (
    EXISTS (SELECT 1 FROM groups g WHERE g.group_id = group_roles.group_id AND g.tenant_id = current_setting('app.current_tenant_id', true)::uuid)
  );

CREATE POLICY tenant_isolation_policy ON role_permissions FOR ALL
  USING (
    EXISTS (SELECT 1 FROM roles r WHERE r.role_id = role_permissions.role_id AND r.tenant_id = current_setting('app.current_tenant_id', true)::uuid)
  );

-- 4. Global Tables (Permissions)
-- Readable by all, writable by none (except system admin/seed scripts via BYPASSRLS or special policy)
ALTER TABLE permissions ENABLE ROW LEVEL SECURITY;
CREATE POLICY allow_read_all ON permissions FOR SELECT USING (true);
CREATE POLICY allow_system_insert ON permissions FOR INSERT WITH CHECK (true);

-- =============================================================================
-- 9. APP USER PERMISSIONS
-- =============================================================================

-- Ensure the application user can access everything
GRANT USAGE ON SCHEMA public TO qlaws_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO qlaws_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO qlaws_app;



-- 1. Secure Roles Table
ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
-- CRITICAL: This makes RLS apply even to the table owner/superuser
ALTER TABLE roles FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_policy ON roles;
CREATE POLICY tenant_isolation_policy ON roles
  FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- 2. Secure Role Permissions (Junction Table)
ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_policy ON role_permissions;
CREATE POLICY tenant_isolation_policy ON role_permissions
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM roles r
      WHERE r.role_id = role_permissions.role_id
        AND r.tenant_id = current_setting('app.current_tenant_id', true)::uuid
    )
  );

-- 3. Grant Access to App User
GRANT ALL ON roles TO qlaws_app;
GRANT ALL ON role_permissions TO qlaws_app;
GRANT ALL ON permissions TO qlaws_app;



-- =============================================================================
-- FIX: Groups RLS Enforcement
-- Problem: The 'groups' table was allowing cross-tenant reads because
-- RLS was not FORCED for the table owner.
-- =============================================================================



---pip install "bcrypt==4.0.1"


-- 1. Secure 'groups' Table
ALTER TABLE groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE groups FORCE ROW LEVEL SECURITY; -- <--- Critical Fix

DROP POLICY IF EXISTS tenant_isolation_policy ON groups;
CREATE POLICY tenant_isolation_policy ON groups
  FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- 2. Secure 'group_members' Table
ALTER TABLE group_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE group_members FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_policy ON group_members;
CREATE POLICY tenant_isolation_policy ON group_members
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM groups g
      WHERE g.group_id = group_members.group_id
        AND g.tenant_id = current_setting('app.current_tenant_id', true)::uuid
    )
  );

-- 3. Secure 'group_roles' Table
ALTER TABLE group_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE group_roles FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_policy ON group_roles;
CREATE POLICY tenant_isolation_policy ON group_roles
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM groups g
      WHERE g.group_id = group_roles.group_id
        AND g.tenant_id = current_setting('app.current_tenant_id', true)::uuid
    )
  );

-- 4. Ensure Permissions
GRANT ALL ON groups TO qlaws_app;
GRANT ALL ON group_members TO qlaws_app;
GRANT ALL ON group_roles TO qlaws_app;


-- 1. Enable RLS on the main table
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- 2. CRITICAL: Force RLS for Table Owners
-- Without this, the superuser/owner bypasses policies, causing test failures
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;

-- 3. Define Isolation Policy (SELECT)
-- Only allow viewing logs where tenant_id matches the session variable
DROP POLICY IF EXISTS tenant_select_policy ON audit_logs;
CREATE POLICY tenant_select_policy ON audit_logs
  FOR SELECT
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- 4. Define Insert Policy (INSERT)
-- Allow system to write logs freely (or restrict if needed)
DROP POLICY IF EXISTS tenant_insert_policy ON audit_logs;
CREATE POLICY tenant_insert_policy ON audit_logs
  FOR INSERT
  WITH CHECK (true);

-- 5. Ensure permissions for the app user
GRANT ALL ON audit_logs TO qlaws_app;
GRANT ALL ON audit_logs_default TO qlaws_app;
-- Grant on partition too if it exists
-- GRANT ALL ON audit_logs_2025_11 TO qlaws_app;


-- To retrive the data for any tenant, use -
SET app.current_tenant_id = 'tenant-UUID'

-- =============================================================================
-- STATIC DATA SEEDING
-- This script populates the global 'permissions' table.
-- It is safe to run multiple times (Idempotent).
-- =============================================================================

-- 1. USER MANAGEMENT
INSERT INTO permissions (key, description) VALUES
('user.create', 'Can create new users and send invitations'),
('user.read',   'Can view user profiles and the user directory'),
('user.update', 'Can update user details and status'),
('user.delete', 'Can remove users from the tenant')
ON CONFLICT (key) DO UPDATE SET description = EXCLUDED.description;

-- 2. ROLE & GROUP MANAGEMENT (RBAC)
INSERT INTO permissions (key, description) VALUES
('role.create', 'Can create custom roles'),
('role.read',   'Can view available roles and permissions'),
('role.update', 'Can modify existing roles'),
('role.delete', 'Can delete roles'),
('group.create', 'Can create user groups'),
('group.read',   'Can view groups'),
('group.update', 'Can modify groups and assign members'),
('group.delete', 'Can delete groups')
ON CONFLICT (key) DO UPDATE SET description = EXCLUDED.description;

-- 3. SECURITY & COMPLIANCE
INSERT INTO permissions (key, description) VALUES
('audit.read',    'Can access security audit logs'),
('session.read',  'Can view active user sessions'),
('session.revoke','Can force-logout users')
ON CONFLICT (key) DO UPDATE SET description = EXCLUDED.description;

-- 4. INFRASTRUCTURE & SETTINGS
INSERT INTO permissions (key, description) VALUES
('tenant.update', 'Can update organization settings and billing'),
('sso.manage',    'Can configure SSO providers and settings'),
('apikey.manage', 'Can create and revoke API keys')
ON CONFLICT (key) DO UPDATE SET description = EXCLUDED.description;

-- 5. AUTOMATION & INTEGRATION SCOPES
-- These are often used by API Keys rather than humans
INSERT INTO permissions (key, description) VALUES
('scim.write',    'Allows user provisioning via SCIM (Machine-to-Machine)'),
('report.export', 'Can export bulk data reports')
ON CONFLICT (key) DO UPDATE SET description = EXCLUDED.description;

-- =============================================================================
-- OPTIONAL: SYSTEM CONFIG
-- If you had a 'plans' or 'regions' table, you would seed it here.
-- =============================================================================