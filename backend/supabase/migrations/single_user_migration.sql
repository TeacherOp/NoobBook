-- NoobBook Single-User Migration
-- Run this in Supabase SQL Editor for single-user local deployment
-- Created: 2026-01-04

-- ============================================================================
-- EXTENSIONS
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- USERS TABLE (simplified for single-user)
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE,
  memory JSONB DEFAULT '{}'::jsonb,
  settings JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create a default user for single-user mode
INSERT INTO users (id, email, memory, settings)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'local@noobbook.local',
  '{}'::jsonb,
  '{}'::jsonb
) ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- PROJECTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE DEFAULT '00000000-0000-0000-0000-000000000001',
  name TEXT NOT NULL,
  description TEXT,
  custom_prompt TEXT,
  memory JSONB DEFAULT '{}'::jsonb,
  costs JSONB DEFAULT '{
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost_usd": 0,
    "by_model": {}
  }'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_accessed TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_last_accessed ON projects(last_accessed DESC);

-- ============================================================================
-- SOURCES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'uploaded',
  raw_file_path TEXT,
  processed_file_path TEXT,
  token_count INTEGER,
  page_count INTEGER,
  file_size BIGINT,
  embedding_info JSONB DEFAULT '{}'::jsonb,
  summary_info JSONB DEFAULT '{}'::jsonb,
  processing_info JSONB DEFAULT '{}'::jsonb,
  error_message TEXT,
  url TEXT,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sources_project_id ON sources(project_id);
CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status);
CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(type);

-- ============================================================================
-- CHATS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS chats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT 'New Chat',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chats_project_id ON chats(project_id);
CREATE INDEX IF NOT EXISTS idx_chats_updated_at ON chats(updated_at DESC);

-- ============================================================================
-- MESSAGES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content JSONB NOT NULL,
  citations TEXT[] DEFAULT ARRAY[]::TEXT[],
  model TEXT,
  tokens_input INTEGER,
  tokens_output INTEGER,
  cost_usd NUMERIC(10, 6),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- ============================================================================
-- CHUNKS TABLE (for RAG)
-- ============================================================================
CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY,
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  page_number INTEGER,
  chunk_number INTEGER,
  token_count INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks(source_id);

-- ============================================================================
-- BACKGROUND TASKS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS background_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target_id UUID NOT NULL,
  target_type TEXT NOT NULL,
  task_type TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  progress INTEGER DEFAULT 0,
  message TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tasks_target ON background_tasks(target_id, target_type);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON background_tasks(status);

-- ============================================================================
-- STUDIO SIGNALS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS studio_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
  studio_item TEXT NOT NULL,
  direction TEXT NOT NULL,
  source_ids UUID[] DEFAULT ARRAY[]::UUID[],
  status TEXT DEFAULT 'pending',
  output_path TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_studio_signals_chat_id ON studio_signals(chat_id);

-- ============================================================================
-- UPDATED_AT TRIGGER FUNCTION
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_projects_updated_at ON projects;
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_sources_updated_at ON sources;
CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_chats_updated_at ON chats;
CREATE TRIGGER update_chats_updated_at BEFORE UPDATE ON chats
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_background_tasks_updated_at ON background_tasks;
CREATE TRIGGER update_background_tasks_updated_at BEFORE UPDATE ON background_tasks
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_studio_signals_updated_at ON studio_signals;
CREATE TRIGGER update_studio_signals_updated_at BEFORE UPDATE ON studio_signals
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Update project last_accessed
CREATE OR REPLACE FUNCTION update_project_last_accessed(p_project_id UUID)
RETURNS VOID AS $$
BEGIN
  UPDATE projects SET last_accessed = NOW() WHERE id = p_project_id;
END;
$$ LANGUAGE plpgsql;

-- Get project statistics
CREATE OR REPLACE FUNCTION get_project_stats(p_project_id UUID)
RETURNS JSON AS $$
DECLARE
  v_stats JSON;
BEGIN
  SELECT json_build_object(
    'total_sources', (SELECT COUNT(*) FROM sources WHERE project_id = p_project_id),
    'active_sources', (SELECT COUNT(*) FROM sources WHERE project_id = p_project_id AND is_active = true),
    'total_chats', (SELECT COUNT(*) FROM chats WHERE project_id = p_project_id),
    'total_messages', (
      SELECT COUNT(*) FROM messages m
      JOIN chats c ON c.id = m.chat_id
      WHERE c.project_id = p_project_id
    )
  ) INTO v_stats;
  RETURN v_stats;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DONE!
-- ============================================================================
-- Single-user migration complete. Default user ID: 00000000-0000-0000-0000-000000000001
