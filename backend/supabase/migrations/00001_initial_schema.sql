-- Migration: Initial Schema
-- Description: Create core tables for NoobBook
-- Created: 2026-01-01

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- USERS TABLE
-- ============================================================================
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  -- Password managed by Supabase Auth (auth.users)

  
  -- Global user preferences and memory
  memory JSONB DEFAULT '{}'::jsonb,
  settings JSONB DEFAULT '{}'::jsonb,
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Email verification
  email_confirmed_at TIMESTAMPTZ,
  
  CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE INDEX idx_users_email ON users(email);

COMMENT ON TABLE users IS 'User accounts with email/password authentication';
COMMENT ON COLUMN users.memory IS 'Global user memory persisted across all projects';
COMMENT ON COLUMN users.settings IS 'User preferences and configuration';

-- ============================================================================
-- PROJECTS TABLE
-- ============================================================================
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Project metadata
  name TEXT NOT NULL,
  description TEXT,
  custom_prompt TEXT,
  
  -- Project-specific memory (separate from user memory)
  memory JSONB DEFAULT '{}'::jsonb,
  
  -- API cost tracking
  costs JSONB DEFAULT '{
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost_usd": 0,
    "by_model": {}
  }'::jsonb,
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_accessed TIMESTAMPTZ DEFAULT NOW(),
  
  CONSTRAINT name_not_empty CHECK (length(trim(name)) > 0)
);

CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_last_accessed ON projects(last_accessed DESC);
CREATE INDEX idx_projects_created_at ON projects(created_at DESC);

COMMENT ON TABLE projects IS 'User projects - containers for sources, chats, and studio outputs';
COMMENT ON COLUMN projects.custom_prompt IS 'Optional custom system prompt for this project';
COMMENT ON COLUMN projects.memory IS 'Project-specific memory for AI context';
COMMENT ON COLUMN projects.costs IS 'Aggregated API usage costs for this project';

-- ============================================================================
-- SOURCES TABLE
-- ============================================================================
CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  
  -- Source metadata
  name TEXT NOT NULL,
  description TEXT,
  type TEXT NOT NULL,
  
  -- Processing status
  status TEXT NOT NULL DEFAULT 'uploaded',
  
  -- File references (storage bucket paths)
  raw_file_path TEXT,
  processed_file_path TEXT,
  
  -- Content metadata
  token_count INTEGER,
  page_count INTEGER,
  file_size BIGINT,
  
  -- Processing information
  embedding_info JSONB DEFAULT '{}'::jsonb,
  summary_info JSONB DEFAULT '{}'::jsonb,
  error_message TEXT,
  
  -- For LINK/YOUTUBE types
  url TEXT,
  
  -- Active flag for RAG (user can toggle sources on/off)
  is_active BOOLEAN DEFAULT true,
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Constraints
  CONSTRAINT valid_type CHECK (type IN ('PDF', 'DOCX', 'PPTX', 'IMAGE', 'AUDIO', 'LINK', 'YOUTUBE', 'TEXT', 'RESEARCH')),
  CONSTRAINT valid_status CHECK (status IN ('uploaded', 'processing', 'embedding', 'ready', 'error', 'cancelled')),
  CONSTRAINT name_not_empty CHECK (length(trim(name)) > 0),
  CONSTRAINT url_required_for_links CHECK (
    (type IN ('LINK', 'YOUTUBE') AND url IS NOT NULL) OR
    (type NOT IN ('LINK', 'YOUTUBE'))
  )
);

CREATE INDEX idx_sources_project_id ON sources(project_id);
CREATE INDEX idx_sources_status ON sources(status);
CREATE INDEX idx_sources_type ON sources(type);
CREATE INDEX idx_sources_is_active ON sources(is_active);
CREATE INDEX idx_sources_created_at ON sources(created_at DESC);

COMMENT ON TABLE sources IS 'Multi-modal sources (documents, images, audio, links, etc.)';
COMMENT ON COLUMN sources.type IS 'Source type: PDF, DOCX, PPTX, IMAGE, AUDIO, LINK, YOUTUBE, TEXT, RESEARCH';
COMMENT ON COLUMN sources.status IS 'Processing status: uploaded, processing, embedding, ready, error, cancelled';
COMMENT ON COLUMN sources.embedding_info IS 'Metadata about vector embeddings (Pinecone IDs, counts, etc.)';
COMMENT ON COLUMN sources.summary_info IS 'AI-generated summary metadata';
COMMENT ON COLUMN sources.is_active IS 'Whether this source is included in RAG searches';

-- ============================================================================
-- CHATS TABLE
-- ============================================================================
CREATE TABLE chats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  
  -- Chat metadata
  title TEXT NOT NULL DEFAULT 'New Chat',
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  CONSTRAINT title_not_empty CHECK (length(trim(title)) > 0)
);

CREATE INDEX idx_chats_project_id ON chats(project_id);
CREATE INDEX idx_chats_updated_at ON chats(updated_at DESC);
CREATE INDEX idx_chats_created_at ON chats(created_at DESC);

COMMENT ON TABLE chats IS 'Conversation containers within projects';
COMMENT ON COLUMN chats.title IS 'Chat title (auto-generated or user-defined)';

-- ============================================================================
-- MESSAGES TABLE
-- ============================================================================
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  
  -- Message content
  role TEXT NOT NULL,
  content JSONB NOT NULL,
  
  -- Citations (array of chunk IDs)
  citations TEXT[] DEFAULT ARRAY[]::TEXT[],
  
  -- API metadata
  model TEXT,
  tokens_input INTEGER,
  tokens_output INTEGER,
  cost_usd NUMERIC(10, 6),
  
  -- Timestamp
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Constraints
  CONSTRAINT valid_role CHECK (role IN ('user', 'assistant', 'tool_use', 'tool_result'))
);

CREATE INDEX idx_messages_chat_id ON messages(chat_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_role ON messages(role);

COMMENT ON TABLE messages IS 'Individual messages within chats';
COMMENT ON COLUMN messages.role IS 'Message role: user, assistant, tool_use, tool_result';
COMMENT ON COLUMN messages.content IS 'Message content (text or structured JSON)';
COMMENT ON COLUMN messages.citations IS 'Array of chunk IDs referenced in this message';

-- ============================================================================
-- STUDIO SIGNALS TABLE
-- ============================================================================
CREATE TABLE studio_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
  
  -- Signal metadata
  studio_item TEXT NOT NULL,
  direction TEXT NOT NULL,
  source_ids UUID[] DEFAULT ARRAY[]::UUID[],
  
  -- Generation status
  status TEXT DEFAULT 'pending',
  output_path TEXT,
  error_message TEXT,
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Constraints
  CONSTRAINT valid_status CHECK (status IN ('pending', 'generating', 'ready', 'error', 'cancelled')),
  CONSTRAINT valid_studio_item CHECK (studio_item IN (
    'audio_overview', 'video_overview', 'flash_cards', 'mind_map', 'quiz',
    'prd', 'blog', 'business_report', 'presentation', 'ads_creative',
    'social_post', 'email_template', 'website', 'component', 'wireframe',
    'flow_diagram'
  ))
);

CREATE INDEX idx_studio_signals_chat_id ON studio_signals(chat_id);
CREATE INDEX idx_studio_signals_message_id ON studio_signals(message_id);
CREATE INDEX idx_studio_signals_status ON studio_signals(status);
CREATE INDEX idx_studio_signals_studio_item ON studio_signals(studio_item);

COMMENT ON TABLE studio_signals IS 'AI-emitted signals for contextual Studio feature activation';
COMMENT ON COLUMN studio_signals.studio_item IS 'Type of Studio content to generate';
COMMENT ON COLUMN studio_signals.direction IS 'AI-provided context and instructions for generation';
COMMENT ON COLUMN studio_signals.source_ids IS 'Array of source UUIDs to use for generation';

-- ============================================================================
-- CHUNKS TABLE (for RAG)
-- ============================================================================
CREATE TABLE chunks (
  id TEXT PRIMARY KEY, -- Format: {source_id}_page_{page}_chunk_{n}
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  
  -- Chunk content
  content TEXT NOT NULL,
  
  -- Metadata
  page_number INTEGER,
  chunk_number INTEGER,
  token_count INTEGER,
  
  -- For future pgvector migration (commented out for now)
  -- embedding vector(1536), -- OpenAI ada-002 dimension
  
  -- Timestamp
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  CONSTRAINT content_not_empty CHECK (length(trim(content)) > 0)
);

CREATE INDEX idx_chunks_source_id ON chunks(source_id);
CREATE INDEX idx_chunks_page_number ON chunks(page_number);
CREATE INDEX idx_chunks_chunk_number ON chunks(chunk_number);

-- For future pgvector search (requires pgvector extension)
-- CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops);

COMMENT ON TABLE chunks IS 'Text chunks for RAG (Retrieval Augmented Generation)';
COMMENT ON COLUMN chunks.id IS 'Chunk ID format: {source_id}_page_{page}_chunk_{n}';
COMMENT ON COLUMN chunks.content IS 'Chunk text content';

-- ============================================================================
-- BACKGROUND TASKS TABLE
-- ============================================================================
CREATE TABLE background_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Task target
  target_id UUID NOT NULL,
  target_type TEXT NOT NULL,
  task_type TEXT NOT NULL,
  
  -- Task status
  status TEXT DEFAULT 'pending',
  progress INTEGER DEFAULT 0,
  message TEXT,
  error_message TEXT,
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  
  -- Constraints
  CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
  CONSTRAINT valid_progress CHECK (progress >= 0 AND progress <= 100),
  CONSTRAINT valid_target_type CHECK (target_type IN ('source', 'studio_signal', 'chat'))
);

CREATE INDEX idx_tasks_target ON background_tasks(target_id, target_type);
CREATE INDEX idx_tasks_status ON background_tasks(status);
CREATE INDEX idx_tasks_created_at ON background_tasks(created_at DESC);

COMMENT ON TABLE background_tasks IS 'Background task tracking for async operations';
COMMENT ON COLUMN background_tasks.target_id IS 'ID of the entity being processed (source_id, chat_id, etc.)';
COMMENT ON COLUMN background_tasks.target_type IS 'Type of target: source, studio_signal, chat';
COMMENT ON COLUMN background_tasks.progress IS 'Progress percentage (0-100)';

-- ============================================================================
-- UPDATED_AT TRIGGERS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to all tables with updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chats_updated_at BEFORE UPDATE ON chats
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_studio_signals_updated_at BEFORE UPDATE ON studio_signals
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_background_tasks_updated_at BEFORE UPDATE ON background_tasks
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to update project's last_accessed timestamp
CREATE OR REPLACE FUNCTION update_project_last_accessed(p_project_id UUID)
RETURNS VOID AS $$
BEGIN
  UPDATE projects
  SET last_accessed = NOW()
  WHERE id = p_project_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_project_last_accessed IS 'Update project last_accessed timestamp when project is opened';
