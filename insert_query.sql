INSERT INTO roles (role_id, tenant_id, name, description, created_at)
VALUES
    (
        uuid_generate_v4(),
        '6d206b3e-9d64-4164-ba25-782f3f05a714',
        'Firm Admin',
        'Full administrative access to all settings, users, matters, and billing for this tenant.',
        NOW()
    ),
    (
        uuid_generate_v4(),
        '6d206b3e-9d64-4164-ba25-782f3f05a714',
        'Managing Partner',
        'Top-level partner with visibility into all matters, performance reports, and financials for the firm.',
        NOW()
    ),
    (
        uuid_generate_v4(),
        '6d206b3e-9d64-4164-ba25-782f3f05a714',
        'Partner',
        'Senior lawyer with ownership of assigned matters and oversight of their team''s work.',
        NOW()
    ),
    (
        uuid_generate_v4(),
        '6d206b3e-9d64-4164-ba25-782f3f05a714',
        'Senior Associate',
        'Handles complex matters, drafts key documents, and supervises associates and juniors.',
        NOW()
    ),
    (
        uuid_generate_v4(),
        '6d206b3e-9d64-4164-ba25-782f3f05a714',
        'Associate',
        'Works on assigned matters including drafting, research, and client communication under supervision.',
        NOW()
    ),
    (
        uuid_generate_v4(),
        '6d206b3e-9d64-4164-ba25-782f3f05a714',
        'Junior Associate',
        'Entry-level lawyer focused on research, drafting, and internal support for senior lawyers.',
        NOW()
    ),
    (
        uuid_generate_v4(),
        '6d206b3e-9d64-4164-ba25-782f3f05a714',
        'Paralegal',
        'Prepares filings, bundles documents, manages case records, and supports lawyers on active matters.',
        NOW()
    ),
    (
        uuid_generate_v4(),
        '6d206b3e-9d64-4164-ba25-782f3f05a714',
        'Legal Assistant',
        'Provides administrative support: scheduling, document organization, and communication coordination.',
        NOW()
    ),
    (
        uuid_generate_v4(),
        '6d206b3e-9d64-4164-ba25-782f3f05a714',
        'Billing Manager',
        'Manages time entries, invoices, payments, and trust accounts for the firm.',
        NOW()
    ),
    (
        uuid_generate_v4(),
        '6d206b3e-9d64-4164-ba25-782f3f05a714',
        'Accounts',
        'Access to firm financials, invoice status, and payment reconciliation, but limited matter details.',
        NOW()
    ),
    (
        uuid_generate_v4(),
        '6d206b3e-9d64-4164-ba25-782f3f05a714',
        'IT/Support',
        'Technical support role with access to configuration and logs, but restricted legal content access.',
        NOW()
    ),
    (
        uuid_generate_v4(),
        '6d206b3e-9d64-4164-ba25-782f3f05a714',
        'Client Portal User',
        'External client contact with access only to their own matters, documents, and messages.',
        NOW()
    );







INSERT INTO permissions (permission_id, key, description) VALUES
    (
        uuid_generate_v4(),
        'sso.manage',
        'Manage SSO configuration and identity provider settings'
    ),
    (
        uuid_generate_v4(),
        'role.read',
        'View roles and their assigned permissions'
    ),
    (
        uuid_generate_v4(),
        'role.create',
        'Create new roles in the system'
    ),
    (
        uuid_generate_v4(),
        'role.update',
        'Update existing roles and their metadata'
    ),
    (
        uuid_generate_v4(),
        'role.delete',
        'Delete roles from the system'
    ),
    (
        uuid_generate_v4(),
        'user.create',
        'Create new users for the tenant'
    ),
    (
        uuid_generate_v4(),
        'user.update',
        'Update user details and settings'
    ),
    (
        uuid_generate_v4(),
        'user.read',
        'View user profiles and basic information'
    ),
    (
        uuid_generate_v4(),
        'user.deactivate',
        'Deactivate or disable existing users'
    ),
    (
        uuid_generate_v4(),
        'sso.read',
        'View SSO configuration and status'
    ),
    (
        uuid_generate_v4(),
        'audit.read',
        'View Audit'
    ),
    (
        uuid_generate_v4(),
        'apikey.manage',
        'API Key manage'
    ),
    (
        uuid_generate_v4(),
        'case.edit',
        'Case Edit'
    ),
    (
        uuid_generate_v4(),
        'case.view',
        'Case View'
    ),
    (
        uuid_generate_v4(),
        'group.create',
        'Create group'
    ),
    (
        uuid_generate_v4(),
        'group.delete',
        'Delete group'
    ),
     (
        uuid_generate_v4(),
        'group.read',
        'Read group'
    ),
    (
        uuid_generate_v4(),
        'group.update',
        'Update group'
    ),
    (
        uuid_generate_v4(),
        'group.manage',
        'Manage group'
    ),
    (
        uuid_generate_v4(),
        'report.export',
        'Export Report'
    ),
    (
        uuid_generate_v4(),
        'scim.write',
        'Write SCIM'
    ),
    (
        uuid_generate_v4(),
        'session.read',
        'Read Session'
    ),
    (
        uuid_generate_v4(),
        'session.revoke',
        'Revoke Session'
    ),
    (
        uuid_generate_v4(),
        'tenant.manage',
        'Manage Tenant'
    ),
    (
        uuid_generate_v4(),
        'tenant.update',
        'Update tenant'
    ),
    (
        uuid_generate_v4(),
        'user.delete',
        'Delete User'
    ),

    (
        uuid_generate_v4(),
        'api_key.manage',
        'Create, revoke, and manage API keys'
    );

