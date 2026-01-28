-- Migration: User Roles and Permissions
-- Description: Add role-based access control for users
-- Created: 2026-01-01

-- ============================================================================
-- USER ROLES ENUM
-- ============================================================================

-- Create enum for user roles
CREATE TYPE user_role AS ENUM ('owner', 'admin', 'member');

COMMENT ON TYPE user_role IS 'User roles: owner (full control), admin (manage users), member (standard access)';

-- ============================================================================
-- ADD ROLE COLUMN TO USERS
-- ============================================================================

ALTER TABLE users ADD COLUMN role user_role NOT NULL DEFAULT 'member';

CREATE INDEX idx_users_role ON users(role);

COMMENT ON COLUMN users.role IS 'User role for access control: owner, admin, or member';

-- ============================================================================
-- PROJECT MEMBERS TABLE (for multi-user projects)
-- ============================================================================

CREATE TABLE project_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Member role within this project
  role user_role NOT NULL DEFAULT 'member',
  
  -- Permissions (granular control)
  can_edit BOOLEAN DEFAULT true,
  can_delete BOOLEAN DEFAULT false,
  can_invite BOOLEAN DEFAULT false,
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Unique constraint: one membership per user per project
  CONSTRAINT unique_project_member UNIQUE (project_id, user_id)
);

CREATE INDEX idx_project_members_project_id ON project_members(project_id);
CREATE INDEX idx_project_members_user_id ON project_members(user_id);
CREATE INDEX idx_project_members_role ON project_members(role);

-- Trigger for updated_at
CREATE TRIGGER update_project_members_updated_at BEFORE UPDATE ON project_members
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE project_members IS 'Project membership for collaborative access';
COMMENT ON COLUMN project_members.role IS 'Member role within project: owner, admin, or member';
COMMENT ON COLUMN project_members.can_edit IS 'Can edit sources and chats';
COMMENT ON COLUMN project_members.can_delete IS 'Can delete sources and chats';
COMMENT ON COLUMN project_members.can_invite IS 'Can invite other members';

-- ============================================================================
-- RLS POLICIES FOR PROJECT_MEMBERS
-- ============================================================================

ALTER TABLE project_members ENABLE ROW LEVEL SECURITY;

-- Users can view memberships for projects they belong to
CREATE POLICY "Users can view project memberships"
  ON project_members FOR SELECT
  USING (
    user_id = auth.uid() OR
    EXISTS (
      SELECT 1 FROM project_members pm
      WHERE pm.project_id = project_members.project_id
      AND pm.user_id = auth.uid()
    )
  );

-- Only project owners/admins can add members
CREATE POLICY "Project owners and admins can add members"
  ON project_members FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM project_members pm
      WHERE pm.project_id = project_members.project_id
      AND pm.user_id = auth.uid()
      AND pm.role IN ('owner', 'admin')
      AND pm.can_invite = true
    ) OR
    -- Or if user is the project owner
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = project_members.project_id
      AND p.user_id = auth.uid()
    )
  );

-- Only project owners can update member roles
CREATE POLICY "Project owners can update members"
  ON project_members FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM project_members pm
      WHERE pm.project_id = project_members.project_id
      AND pm.user_id = auth.uid()
      AND pm.role = 'owner'
    ) OR
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = project_members.project_id
      AND p.user_id = auth.uid()
    )
  );

-- Only project owners can remove members (or member removing themselves)
CREATE POLICY "Project owners can remove members"
  ON project_members FOR DELETE
  USING (
    user_id = auth.uid() OR  -- Can remove self
    EXISTS (
      SELECT 1 FROM project_members pm
      WHERE pm.project_id = project_members.project_id
      AND pm.user_id = auth.uid()
      AND pm.role = 'owner'
    ) OR
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = project_members.project_id
      AND p.user_id = auth.uid()
    )
  );

-- ============================================================================
-- HELPER FUNCTIONS FOR ROLE CHECKS
-- ============================================================================

-- Check if user has access to a project
CREATE OR REPLACE FUNCTION user_has_project_access(p_project_id UUID, p_user_id UUID DEFAULT auth.uid())
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM projects WHERE id = p_project_id AND user_id = p_user_id
  ) OR EXISTS (
    SELECT 1 FROM project_members WHERE project_id = p_project_id AND user_id = p_user_id
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION user_has_project_access IS 'Check if user owns or is member of a project';

-- Check if user is project owner
CREATE OR REPLACE FUNCTION user_is_project_owner(p_project_id UUID, p_user_id UUID DEFAULT auth.uid())
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM projects WHERE id = p_project_id AND user_id = p_user_id
  ) OR EXISTS (
    SELECT 1 FROM project_members 
    WHERE project_id = p_project_id AND user_id = p_user_id AND role = 'owner'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION user_is_project_owner IS 'Check if user is owner of a project';

-- Check if user is admin (global admin role)
CREATE OR REPLACE FUNCTION user_is_admin(p_user_id UUID DEFAULT auth.uid())
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM users WHERE id = p_user_id AND role IN ('admin', 'owner')
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION user_is_admin IS 'Check if user has admin or owner role globally';

-- Get user role in a project
CREATE OR REPLACE FUNCTION get_user_project_role(p_project_id UUID, p_user_id UUID DEFAULT auth.uid())
RETURNS user_role AS $$
DECLARE
  v_role user_role;
BEGIN
  -- Check if direct owner
  IF EXISTS (SELECT 1 FROM projects WHERE id = p_project_id AND user_id = p_user_id) THEN
    RETURN 'owner';
  END IF;
  
  -- Check membership
  SELECT role INTO v_role
  FROM project_members
  WHERE project_id = p_project_id AND user_id = p_user_id;
  
  RETURN v_role;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION get_user_project_role IS 'Get user role within a specific project';

-- ============================================================================
-- AUTO-CREATE OWNER MEMBERSHIP ON PROJECT CREATION
-- ============================================================================

CREATE OR REPLACE FUNCTION trigger_create_project_owner_membership()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO project_members (project_id, user_id, role, can_edit, can_delete, can_invite)
  VALUES (NEW.id, NEW.user_id, 'owner', true, true, true);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER create_project_owner_membership
AFTER INSERT ON projects
FOR EACH ROW
EXECUTE FUNCTION trigger_create_project_owner_membership();

COMMENT ON TRIGGER create_project_owner_membership ON projects IS 'Auto-create owner membership when project is created';

-- ============================================================================
-- UPDATE EXISTING RLS POLICIES TO INCLUDE PROJECT MEMBERS
-- ============================================================================

-- Drop and recreate source policies to include members
DROP POLICY IF EXISTS "Users can view own sources" ON sources;
CREATE POLICY "Users can view sources in accessible projects"
  ON sources FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = sources.project_id
      AND (p.user_id = auth.uid() OR EXISTS (
        SELECT 1 FROM project_members pm
        WHERE pm.project_id = p.id AND pm.user_id = auth.uid()
      ))
    )
  );

DROP POLICY IF EXISTS "Users can create sources in own projects" ON sources;
CREATE POLICY "Users can create sources in accessible projects"
  ON sources FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = sources.project_id
      AND (p.user_id = auth.uid() OR EXISTS (
        SELECT 1 FROM project_members pm
        WHERE pm.project_id = p.id AND pm.user_id = auth.uid() AND pm.can_edit = true
      ))
    )
  );

DROP POLICY IF EXISTS "Users can update own sources" ON sources;
CREATE POLICY "Users can update sources in accessible projects"
  ON sources FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = sources.project_id
      AND (p.user_id = auth.uid() OR EXISTS (
        SELECT 1 FROM project_members pm
        WHERE pm.project_id = p.id AND pm.user_id = auth.uid() AND pm.can_edit = true
      ))
    )
  );

DROP POLICY IF EXISTS "Users can delete own sources" ON sources;
CREATE POLICY "Users can delete sources in accessible projects"
  ON sources FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = sources.project_id
      AND (p.user_id = auth.uid() OR EXISTS (
        SELECT 1 FROM project_members pm
        WHERE pm.project_id = p.id AND pm.user_id = auth.uid() AND pm.can_delete = true
      ))
    )
  );

-- Update chat policies similarly
DROP POLICY IF EXISTS "Users can view own chats" ON chats;
CREATE POLICY "Users can view chats in accessible projects"
  ON chats FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = chats.project_id
      AND (p.user_id = auth.uid() OR EXISTS (
        SELECT 1 FROM project_members pm
        WHERE pm.project_id = p.id AND pm.user_id = auth.uid()
      ))
    )
  );

DROP POLICY IF EXISTS "Users can create chats in own projects" ON chats;
CREATE POLICY "Users can create chats in accessible projects"
  ON chats FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = chats.project_id
      AND (p.user_id = auth.uid() OR EXISTS (
        SELECT 1 FROM project_members pm
        WHERE pm.project_id = p.id AND pm.user_id = auth.uid() AND pm.can_edit = true
      ))
    )
  );

DROP POLICY IF EXISTS "Users can update own chats" ON chats;
CREATE POLICY "Users can update chats in accessible projects"
  ON chats FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = chats.project_id
      AND (p.user_id = auth.uid() OR EXISTS (
        SELECT 1 FROM project_members pm
        WHERE pm.project_id = p.id AND pm.user_id = auth.uid() AND pm.can_edit = true
      ))
    )
  );

DROP POLICY IF EXISTS "Users can delete own chats" ON chats;
CREATE POLICY "Users can delete chats in accessible projects"
  ON chats FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = chats.project_id
      AND (p.user_id = auth.uid() OR EXISTS (
        SELECT 1 FROM project_members pm
        WHERE pm.project_id = p.id AND pm.user_id = auth.uid() AND pm.can_delete = true
      ))
    )
  );
