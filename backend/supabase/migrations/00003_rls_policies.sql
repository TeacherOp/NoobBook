-- Migration: Row Level Security Policies
-- Description: Enable RLS and create security policies for all tables
-- Created: 2026-01-01

-- ============================================================================
-- ENABLE ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE studio_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE background_tasks ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- USERS TABLE POLICIES
-- ============================================================================

-- Users can view their own profile
CREATE POLICY "Users can view own profile"
ON users FOR SELECT
USING (auth.uid() = id);

-- Users can update their own profile
CREATE POLICY "Users can update own profile"
ON users FOR UPDATE
USING (auth.uid() = id);

-- Note: INSERT is handled by Supabase Auth
-- Note: DELETE should be handled through a dedicated account deletion flow

-- ============================================================================
-- PROJECTS TABLE POLICIES
-- ============================================================================

-- Users can view their own projects
CREATE POLICY "Users can view own projects"
ON projects FOR SELECT
USING (auth.uid() = user_id);

-- Users can create projects
CREATE POLICY "Users can create own projects"
ON projects FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- Users can update their own projects
CREATE POLICY "Users can update own projects"
ON projects FOR UPDATE
USING (auth.uid() = user_id);

-- Users can delete their own projects
CREATE POLICY "Users can delete own projects"
ON projects FOR DELETE
USING (auth.uid() = user_id);

-- ============================================================================
-- SOURCES TABLE POLICIES
-- ============================================================================

-- Users can view sources in their own projects
CREATE POLICY "Users can view sources in own projects"
ON sources FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM projects
    WHERE projects.id = sources.project_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can create sources in their own projects
CREATE POLICY "Users can create sources in own projects"
ON sources FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM projects
    WHERE projects.id = sources.project_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can update sources in their own projects
CREATE POLICY "Users can update sources in own projects"
ON sources FOR UPDATE
USING (
  EXISTS (
    SELECT 1 FROM projects
    WHERE projects.id = sources.project_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can delete sources from their own projects
CREATE POLICY "Users can delete sources from own projects"
ON sources FOR DELETE
USING (
  EXISTS (
    SELECT 1 FROM projects
    WHERE projects.id = sources.project_id
    AND projects.user_id = auth.uid()
  )
);

-- ============================================================================
-- CHATS TABLE POLICIES
-- ============================================================================

-- Users can view chats in their own projects
CREATE POLICY "Users can view chats in own projects"
ON chats FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM projects
    WHERE projects.id = chats.project_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can create chats in their own projects
CREATE POLICY "Users can create chats in own projects"
ON chats FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM projects
    WHERE projects.id = chats.project_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can update chats in their own projects
CREATE POLICY "Users can update chats in own projects"
ON chats FOR UPDATE
USING (
  EXISTS (
    SELECT 1 FROM projects
    WHERE projects.id = chats.project_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can delete chats from their own projects
CREATE POLICY "Users can delete chats from own projects"
ON chats FOR DELETE
USING (
  EXISTS (
    SELECT 1 FROM projects
    WHERE projects.id = chats.project_id
    AND projects.user_id = auth.uid()
  )
);

-- ============================================================================
-- MESSAGES TABLE POLICIES
-- ============================================================================

-- Users can view messages in chats within their own projects
CREATE POLICY "Users can view messages in own chats"
ON messages FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM chats
    JOIN projects ON projects.id = chats.project_id
    WHERE chats.id = messages.chat_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can create messages in chats within their own projects
CREATE POLICY "Users can create messages in own chats"
ON messages FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM chats
    JOIN projects ON projects.id = chats.project_id
    WHERE chats.id = messages.chat_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can update messages in chats within their own projects
CREATE POLICY "Users can update messages in own chats"
ON messages FOR UPDATE
USING (
  EXISTS (
    SELECT 1 FROM chats
    JOIN projects ON projects.id = chats.project_id
    WHERE chats.id = messages.chat_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can delete messages from chats within their own projects
CREATE POLICY "Users can delete messages from own chats"
ON messages FOR DELETE
USING (
  EXISTS (
    SELECT 1 FROM chats
    JOIN projects ON projects.id = chats.project_id
    WHERE chats.id = messages.chat_id
    AND projects.user_id = auth.uid()
  )
);

-- ============================================================================
-- STUDIO SIGNALS TABLE POLICIES
-- ============================================================================

-- Users can view studio signals in chats within their own projects
CREATE POLICY "Users can view studio signals in own chats"
ON studio_signals FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM chats
    JOIN projects ON projects.id = chats.project_id
    WHERE chats.id = studio_signals.chat_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can create studio signals in chats within their own projects
CREATE POLICY "Users can create studio signals in own chats"
ON studio_signals FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM chats
    JOIN projects ON projects.id = chats.project_id
    WHERE chats.id = studio_signals.chat_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can update studio signals in chats within their own projects
CREATE POLICY "Users can update studio signals in own chats"
ON studio_signals FOR UPDATE
USING (
  EXISTS (
    SELECT 1 FROM chats
    JOIN projects ON projects.id = chats.project_id
    WHERE chats.id = studio_signals.chat_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can delete studio signals from chats within their own projects
CREATE POLICY "Users can delete studio signals from own chats"
ON studio_signals FOR DELETE
USING (
  EXISTS (
    SELECT 1 FROM chats
    JOIN projects ON projects.id = chats.project_id
    WHERE chats.id = studio_signals.chat_id
    AND projects.user_id = auth.uid()
  )
);

-- ============================================================================
-- CHUNKS TABLE POLICIES
-- ============================================================================

-- Users can view chunks from sources in their own projects
CREATE POLICY "Users can view chunks from own sources"
ON chunks FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM sources
    JOIN projects ON projects.id = sources.project_id
    WHERE sources.id = chunks.source_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can create chunks for sources in their own projects
CREATE POLICY "Users can create chunks for own sources"
ON chunks FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM sources
    JOIN projects ON projects.id = sources.project_id
    WHERE sources.id = chunks.source_id
    AND projects.user_id = auth.uid()
  )
);

-- Users can delete chunks from sources in their own projects
CREATE POLICY "Users can delete chunks from own sources"
ON chunks FOR DELETE
USING (
  EXISTS (
    SELECT 1 FROM sources
    JOIN projects ON projects.id = sources.project_id
    WHERE sources.id = chunks.source_id
    AND projects.user_id = auth.uid()
  )
);

-- ============================================================================
-- BACKGROUND TASKS TABLE POLICIES
-- ============================================================================

-- Users can view background tasks for their own resources
CREATE POLICY "Users can view own background tasks"
ON background_tasks FOR SELECT
USING (
  -- For source tasks
  (target_type = 'source' AND EXISTS (
    SELECT 1 FROM sources
    JOIN projects ON projects.id = sources.project_id
    WHERE sources.id = background_tasks.target_id
    AND projects.user_id = auth.uid()
  ))
  OR
  -- For studio_signal tasks
  (target_type = 'studio_signal' AND EXISTS (
    SELECT 1 FROM studio_signals
    JOIN chats ON chats.id = studio_signals.chat_id
    JOIN projects ON projects.id = chats.project_id
    WHERE studio_signals.id = background_tasks.target_id
    AND projects.user_id = auth.uid()
  ))
  OR
  -- For chat tasks
  (target_type = 'chat' AND EXISTS (
    SELECT 1 FROM chats
    JOIN projects ON projects.id = chats.project_id
    WHERE chats.id = background_tasks.target_id
    AND projects.user_id = auth.uid()
  ))
);

-- Users can create background tasks for their own resources
CREATE POLICY "Users can create own background tasks"
ON background_tasks FOR INSERT
WITH CHECK (
  -- For source tasks
  (target_type = 'source' AND EXISTS (
    SELECT 1 FROM sources
    JOIN projects ON projects.id = sources.project_id
    WHERE sources.id = background_tasks.target_id
    AND projects.user_id = auth.uid()
  ))
  OR
  -- For studio_signal tasks
  (target_type = 'studio_signal' AND EXISTS (
    SELECT 1 FROM studio_signals
    JOIN chats ON chats.id = studio_signals.chat_id
    JOIN projects ON projects.id = chats.project_id
    WHERE studio_signals.id = background_tasks.target_id
    AND projects.user_id = auth.uid()
  ))
  OR
  -- For chat tasks
  (target_type = 'chat' AND EXISTS (
    SELECT 1 FROM chats
    JOIN projects ON projects.id = chats.project_id
    WHERE chats.id = background_tasks.target_id
    AND projects.user_id = auth.uid()
  ))
);

-- Users can update background tasks for their own resources
CREATE POLICY "Users can update own background tasks"
ON background_tasks FOR UPDATE
USING (
  -- For source tasks
  (target_type = 'source' AND EXISTS (
    SELECT 1 FROM sources
    JOIN projects ON projects.id = sources.project_id
    WHERE sources.id = background_tasks.target_id
    AND projects.user_id = auth.uid()
  ))
  OR
  -- For studio_signal tasks
  (target_type = 'studio_signal' AND EXISTS (
    SELECT 1 FROM studio_signals
    JOIN chats ON chats.id = studio_signals.chat_id
    JOIN projects ON projects.id = chats.project_id
    WHERE studio_signals.id = background_tasks.target_id
    AND projects.user_id = auth.uid()
  ))
  OR
  -- For chat tasks
  (target_type = 'chat' AND EXISTS (
    SELECT 1 FROM chats
    JOIN projects ON projects.id = chats.project_id
    WHERE chats.id = background_tasks.target_id
    AND projects.user_id = auth.uid()
  ))
);

-- Users can delete background tasks for their own resources
CREATE POLICY "Users can delete own background tasks"
ON background_tasks FOR DELETE
USING (
  -- For source tasks
  (target_type = 'source' AND EXISTS (
    SELECT 1 FROM sources
    JOIN projects ON projects.id = sources.project_id
    WHERE sources.id = background_tasks.target_id
    AND projects.user_id = auth.uid()
  ))
  OR
  -- For studio_signal tasks
  (target_type = 'studio_signal' AND EXISTS (
    SELECT 1 FROM studio_signals
    JOIN chats ON chats.id = studio_signals.chat_id
    JOIN projects ON projects.id = chats.project_id
    WHERE studio_signals.id = background_tasks.target_id
    AND projects.user_id = auth.uid()
  ))
  OR
  -- For chat tasks
  (target_type = 'chat' AND EXISTS (
    SELECT 1 FROM chats
    JOIN projects ON projects.id = chats.project_id
    WHERE chats.id = background_tasks.target_id
    AND projects.user_id = auth.uid()
  ))
);
