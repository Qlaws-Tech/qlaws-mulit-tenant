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