-- Role Audit Log Table
-- Logs all role assignment and revocation operations

CREATE TABLE IF NOT EXISTS role_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action TEXT NOT NULL,  -- 'role_assign', 'role_revoke', 'role_assign_idempotent', etc.
    target_user_id TEXT NOT NULL,  -- User ID receiving role change
    role_key TEXT NOT NULL,  -- Role being assigned/revoked
    performed_by TEXT NOT NULL,  -- Admin user ID who performed action
    result TEXT NOT NULL,  -- 'assigned', 'revoked', 'already_assigned', 'not_assigned'
    metadata JSONB,  -- Additional context (admin roles, IP, etc.)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Index for looking up audit history by user
CREATE INDEX IF NOT EXISTS idx_role_audit_log_target_user
ON role_audit_log(target_user_id);

-- Index for looking up actions by admin
CREATE INDEX IF NOT EXISTS idx_role_audit_log_performed_by
ON role_audit_log(performed_by);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_role_audit_log_created_at
ON role_audit_log(created_at DESC);
