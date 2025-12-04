-- ============================================================
-- QLAWS MULTI-TENANT SECURITY PLATFORM — FULL SQL SCHEMA
-- Shared Schema, Row-Level Security (RLS)
-- PostgreSQL 15+
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

---------------------------------------------------------------
-- 1. TENANTS
---------------------------------------------------------------
CREATE TABLE tenants (
    tenant_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name               TEXT NOT NULL,
    domain             TEXT UNIQUE,
    plan               TEXT NOT NULL DEFAULT 'startup',
    region             TEXT NOT NULL DEFAULT 'us-east-1',
    status             TEXT NOT NULL DEFAULT 'active',
    config             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tenants_domain ON tenants(lower(domain));

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;

CREATE POLICY tenants_isolation ON tenants
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 2. USERS (global identities with passwords)
---------------------------------------------------------------
CREATE TABLE users (
    user_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    primary_email     TEXT UNIQUE NOT NULL,
    display_name      TEXT NOT NULL,
    hashed_password   TEXT NOT NULL,
    password_updated_at TIMESTAMPTZ DEFAULT now(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users(lower(primary_email));

---------------------------------------------------------------
-- 3. USER → TENANT MAPPING
---------------------------------------------------------------
CREATE TABLE user_tenants (
    user_tenant_id   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id        UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    tenant_email     TEXT NOT NULL,
    tenant_role      TEXT NOT NULL DEFAULT 'member',
    status           TEXT NOT NULL DEFAULT 'active',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id)
);

CREATE INDEX idx_user_tenants_tenant ON user_tenants(tenant_id);

ALTER TABLE user_tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_tenants FORCE ROW LEVEL SECURITY;

CREATE POLICY user_tenants_isolation ON user_tenants
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 4. PERMISSIONS (global)
---------------------------------------------------------------
CREATE TABLE permissions (
    permission_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key            TEXT UNIQUE NOT NULL,
    description    TEXT
);

---------------------------------------------------------------
-- 5. ROLES (tenant-scoped)
---------------------------------------------------------------
CREATE TABLE roles (
    role_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id      UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    description    TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE INDEX idx_roles_tenant ON roles(tenant_id);

ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE roles FORCE ROW LEVEL SECURITY;

CREATE POLICY roles_isolation ON roles
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 6. ROLE → PERMISSIONS (tenant scoped)
---------------------------------------------------------------
CREATE TABLE role_permissions (
    role_id         UUID NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    permission_id   UUID NOT NULL REFERENCES permissions(permission_id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE INDEX idx_role_permissions_tenant ON role_permissions(tenant_id);

ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY;

CREATE POLICY role_permissions_isolation ON role_permissions
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 7. GROUPS (tenant-scoped)
---------------------------------------------------------------
CREATE TABLE groups (
    group_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

ALTER TABLE groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE groups FORCE ROW LEVEL SECURITY;

CREATE POLICY groups_isolation ON groups
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 8. GROUP MEMBERS
---------------------------------------------------------------
CREATE TABLE group_members (
    group_id        UUID REFERENCES groups(group_id) ON DELETE CASCADE,
    user_tenant_id  UUID REFERENCES user_tenants(user_tenant_id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id),
    PRIMARY KEY (group_id, user_tenant_id)
);

ALTER TABLE group_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE group_members FORCE ROW LEVEL SECURITY;

CREATE POLICY gm_isolation ON group_members
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 9. GROUP ROLES
---------------------------------------------------------------
CREATE TABLE group_roles (
    group_id       UUID REFERENCES groups(group_id) ON DELETE CASCADE,
    role_id        UUID REFERENCES roles(role_id) ON DELETE CASCADE,
    tenant_id      UUID NOT NULL REFERENCES tenants(tenant_id),
    PRIMARY KEY (group_id, role_id)
);

ALTER TABLE group_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE group_roles FORCE ROW LEVEL SECURITY;

CREATE POLICY gr_isolation ON group_roles
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 10. SESSIONS
---------------------------------------------------------------
CREATE TABLE sessions (
    session_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_tenant_id   UUID REFERENCES user_tenants(user_tenant_id) ON DELETE CASCADE,
    tenant_id        UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    ip_address       INET,
    device_info      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions FORCE ROW LEVEL SECURITY;

CREATE POLICY sessions_isolation ON sessions
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 11. REFRESH TOKENS
---------------------------------------------------------------
CREATE TABLE refresh_tokens (
    token_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL,
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id),
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_refresh_tokens_expiry ON refresh_tokens(expires_at);
CREATE INDEX idx_refresh_tokens_session ON refresh_tokens(session_id);

ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens FORCE ROW LEVEL SECURITY;

CREATE POLICY refresh_tokens_isolation ON refresh_tokens
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 12. MFA METHODS
---------------------------------------------------------------
CREATE TABLE mfa_methods (
    mfa_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_tenant_id  UUID NOT NULL REFERENCES user_tenants(user_tenant_id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id),
    method_type     TEXT NOT NULL,
    secret          TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE mfa_methods ENABLE ROW LEVEL SECURITY;
ALTER TABLE mfa_methods FORCE ROW LEVEL SECURITY;

CREATE POLICY mfa_isolation ON mfa_methods
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 13. API KEYS
---------------------------------------------------------------
CREATE TABLE api_keys (
    api_key_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id      UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    scopes         TEXT[] NOT NULL,
    key_hash       TEXT NOT NULL,
    prefix         TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at   TIMESTAMPTZ
);

CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);
CREATE INDEX idx_api_keys_prefix ON api_keys(prefix);

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys FORCE ROW LEVEL SECURITY;

CREATE POLICY api_keys_isolation ON api_keys
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 14. SSO PROVIDERS
---------------------------------------------------------------
CREATE TABLE sso_providers (
    sso_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id      UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    provider_type  TEXT NOT NULL,
    name           TEXT NOT NULL,
    config         JSONB NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE sso_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE sso_providers FORCE ROW LEVEL SECURITY;

CREATE POLICY sso_isolation ON sso_providers
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 15. SCIM MAPPINGS
---------------------------------------------------------------
CREATE TABLE scim_mappings (
    scim_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id      UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id        UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    external_id    TEXT NOT NULL,
    active         BOOLEAN NOT NULL DEFAULT true,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, external_id)
);

ALTER TABLE scim_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE scim_mappings FORCE ROW LEVEL SECURITY;

CREATE POLICY scim_isolation ON scim_mappings
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 16. AUDIT LOGS (append-only, tenant-scoped)
---------------------------------------------------------------


CREATE TABLE IF NOT EXISTS audit_logs (
  audit_id      uuid DEFAULT uuid_generate_v4(),
  tenant_id     uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  actor_user_id uuid,
  action_type   text NOT NULL,
  resource_type text,
  resource_id   text,
  details       jsonb DEFAULT '{}'::jsonb,
  ip_address    text,
  event_time    timestamptz NOT NULL DEFAULT now(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
  PRIMARY KEY (audit_id, tenant_id)
);



CREATE INDEX idx_audit_tenant ON audit_logs(tenant_id);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at);

ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;

CREATE POLICY audit_isolation ON audit_logs
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

---------------------------------------------------------------
-- 17. TOKEN BLACKLIST (global)
---------------------------------------------------------------
CREATE TABLE token_blacklist (
    jti           TEXT PRIMARY KEY,
    expires_at    TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_token_blacklist_expiry ON token_blacklist(expires_at);

-- No RLS (global revocation)

---------------------------------------------------------------
-- END SQL SCHEMA
---------------------------------------------------------------
CREATE TABLE invitations (
    invitation_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id          UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    email              TEXT NOT NULL,
    invited_by_user_id UUID NOT NULL REFERENCES users(user_id),
    roles              TEXT[] NOT NULL DEFAULT '{}',
    group_ids          UUID[] NOT NULL DEFAULT '{}',
    token_hash         TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'pending', -- pending | accepted | revoked | expired
    expires_at         TIMESTAMPTZ NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE TABLE IF NOT EXISTS user_roles (
  user_role_id     uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_tenant_id   uuid NOT NULL REFERENCES user_tenants(user_tenant_id) ON DELETE CASCADE,
  role_id          uuid NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
  UNIQUE (user_tenant_id, role_id)
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  password_reset_token_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id          uuid NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  token_hash       text NOT NULL,
  expires_at       timestamptz NOT NULL,
  used_at          timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now()
);

-- Fast lookup by hash
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_hash
  ON password_reset_tokens(token_hash);

-- For cleanup jobs (system cleanup)
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires
  ON password_reset_tokens(expires_at);



CREATE INDEX IF NOT EXISTS idx_user_roles_user_tenant
    ON user_roles(user_tenant_id);

CREATE INDEX IF NOT EXISTS idx_user_roles_role
    ON user_roles(role_id);

 ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS revoked boolean NOT NULL DEFAULT false;

  ALTER TABLE refresh_tokens
    ADD COLUMN IF NOT EXISTS user_id uuid NOT NULL;

ALTER TABLE refresh_tokens
    ADD CONSTRAINT IF NOT EXISTS refresh_tokens_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users(user_id);

-- Add tenant_id and user_id columns if they don't exist yet
ALTER TABLE token_blacklist
    ADD COLUMN IF NOT EXISTS tenant_id uuid;

ALTER TABLE token_blacklist
    ADD COLUMN IF NOT EXISTS user_id uuid;

-- Add tenant_id and user_id columns if they don't exist yet
ALTER TABLE token_blacklist
    ADD COLUMN IF NOT EXISTS token_hash text;

ALTER TABLE token_blacklist
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();


CREATE INDEX idx_token_blacklist_expiry
    ON token_blacklist (expires_at);


   ALTER TABLE user_tenants ADD COLUMN persona TEXT;