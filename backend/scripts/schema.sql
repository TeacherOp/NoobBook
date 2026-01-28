-- NoobBook Database Schema for Self-Hosted Supabase
--
-- Educational Note: This schema migrates NoobBook from JSON file storage
-- to PostgreSQL via Supabase. Key design decisions:
--   - UUIDs for all primary keys (matches existing JSON structure)
--   - JSONB for flexible fields (settings, metadata, cost_tracking)
--   - Separate chunks table (enables SQL-based hybrid search)
--   - Single-user mode initially (no complex auth)
--
-- To apply this schema:
--   docker exec -it supabase-db psql -U postgres -d postgres -f /path/to/schema.sql
-- Or via Supabase Dashboard SQL Editor

-- =============================================================================
-- Enable Required Extensions
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- For UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- For text search/fuzzy matching

-- =============================================================================
-- Users Table (for future multi-user support)
-- =============================================================================

-- Educational Note: Even though NoobBook is single-user initially,
-- we create a users table to prepare for multi-user support.
-- The default user will be created by the migration script.

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE,
    display_name TEXT,
    user_memory TEXT,  -- Global user preferences/context
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create default user for single-user mode
INSERT INTO users (id, email, display_name, user_memory)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'default@noobbook.local',
    'Default User',
    NULL
) ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- Projects Table
-- =============================================================================

-- Educational Note: Projects are the top-level containers for all user data.
-- Settings and cost_tracking use JSONB for flexibility - we don't need to
-- query these fields directly, just store/retrieve them.

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',

    -- Project settings (ai_model, auto_save, custom_prompt)
    settings JSONB NOT NULL DEFAULT '{
        "ai_model": "claude-sonnet-4-5",
        "auto_save": true,
        "custom_prompt": null
    }',

    -- Cost tracking per model
    -- Structure: { "model_name": { "input_tokens": N, "output_tokens": N, "cost_usd": N } }
    cost_tracking JSONB NOT NULL DEFAULT '{}',

    -- Project-specific memory (separate from global user memory)
    project_memory TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Ensure unique names per user
    CONSTRAINT unique_project_name_per_user UNIQUE (user_id, name)
);

-- Index for listing projects by user, sorted by last_accessed
CREATE INDEX IF NOT EXISTS idx_projects_user_accessed
    ON projects(user_id, last_accessed DESC);

-- =============================================================================
-- Sources Table
-- =============================================================================

-- Educational Note: Sources are documents/files uploaded to a project.
-- Status tracks the processing pipeline: uploaded -> processing -> [embedding] -> ready
-- Embedding happens only if token_count > 2500.

CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- Basic metadata
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    source_type TEXT NOT NULL,  -- pdf, docx, pptx, image, audio, link, youtube, text
    original_filename TEXT,
    file_size INTEGER,  -- bytes
    mime_type TEXT,

    -- Processing status
    status TEXT NOT NULL DEFAULT 'uploaded',  -- uploaded, processing, embedding, ready, error, cancelled
    error_message TEXT,

    -- Token/page counts from processing
    token_count INTEGER,
    page_count INTEGER,

    -- Embedding info (populated after embedding step)
    -- Structure: { "status": "completed", "vector_count": N, "namespace": "project_id" }
    embedding_info JSONB,

    -- Summary info (populated after summarization)
    -- Structure: { "summary": "...", "generated_at": "..." }
    summary_info JSONB,

    -- Storage paths (relative to Supabase Storage bucket)
    raw_path TEXT,       -- sources/{project_id}/raw/{source_id}.{ext}
    processed_path TEXT, -- sources/{project_id}/processed/{source_id}.txt

    -- Source-specific metadata
    -- For URLs: { "url": "...", "scraped_title": "..." }
    -- For YouTube: { "video_id": "...", "channel": "..." }
    metadata JSONB DEFAULT '{}',

    -- Active flag for filtering sources in chat
    active BOOLEAN NOT NULL DEFAULT true,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ
);

-- Index for listing sources by project
CREATE INDEX IF NOT EXISTS idx_sources_project ON sources(project_id);
CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(project_id, status);

-- =============================================================================
-- Chunks Table (for RAG)
-- =============================================================================

-- Educational Note: Chunks are segments of processed source text used for
-- retrieval in RAG. Storing in PostgreSQL (instead of just as files) enables:
-- - SQL-based keyword search alongside Pinecone semantic search
-- - Easier chunk management and querying
-- - Direct loading without file system operations

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,  -- Format: {source_id}_page_{N}_chunk_{M}
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- Chunk content
    text TEXT NOT NULL,
    token_count INTEGER,

    -- Position information
    page_number INTEGER NOT NULL,
    chunk_number INTEGER NOT NULL,

    -- For hybrid search - we store raw text, can add tsvector for FTS

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for retrieving chunks by source
CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id);

-- Full-text search index (optional, for keyword search)
CREATE INDEX IF NOT EXISTS idx_chunks_text_search
    ON chunks USING gin(to_tsvector('english', text));

-- =============================================================================
-- Chats Table
-- =============================================================================

-- Educational Note: Chats are conversation containers within a project.
-- Messages are stored separately to allow efficient message queries.
-- studio_signals tracks in-flight studio generation triggered from chat.

CREATE TABLE IF NOT EXISTS chats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    title TEXT NOT NULL DEFAULT 'New Chat',

    -- Message count for quick display (denormalized for efficiency)
    message_count INTEGER NOT NULL DEFAULT 0,

    -- Chat metadata
    -- Structure: { "source_references": [], "sub_agents": [] }
    metadata JSONB DEFAULT '{"source_references": [], "sub_agents": []}',

    -- Studio signals for in-flight generation jobs
    -- Structure: [{ "job_id": "...", "job_type": "audio", "status": "pending" }]
    studio_signals JSONB DEFAULT '[]',

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for listing chats by project
CREATE INDEX IF NOT EXISTS idx_chats_project ON chats(project_id);
CREATE INDEX IF NOT EXISTS idx_chats_updated ON chats(project_id, updated_at DESC);

-- =============================================================================
-- Messages Table
-- =============================================================================

-- Educational Note: Messages are stored separately from chats for efficiency.
-- The content field is JSONB because it can be:
-- - Simple string for user/assistant text messages
-- - Array of content blocks for tool_use/tool_result messages
-- sequence_number ensures ordering within a chat.

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,

    -- Message role: user, assistant
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),

    -- Content can be string or array of content blocks (tool_use, tool_result, etc.)
    content JSONB NOT NULL,

    -- Sequence number for ordering
    sequence_number INTEGER NOT NULL,

    -- Optional metadata (model, tokens, error flag)
    model TEXT,
    tokens JSONB,  -- { "input": N, "output": N }
    is_error BOOLEAN DEFAULT false,

    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Ensure unique sequence within chat
    CONSTRAINT unique_message_sequence UNIQUE (chat_id, sequence_number)
);

-- Index for retrieving messages in order
CREATE INDEX IF NOT EXISTS idx_messages_chat_seq ON messages(chat_id, sequence_number);

-- =============================================================================
-- Tasks Table (Background Jobs)
-- =============================================================================

-- Educational Note: Tasks track background operations like source processing.
-- This replaces the JSON-based task tracking with better query capabilities.

CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Task type (e.g., "source_processing", "audio_generation")
    task_type TEXT NOT NULL,

    -- Target resource ID (e.g., source_id, job_id)
    target_id TEXT NOT NULL,

    -- Status: pending, running, completed, failed, cancelled
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Index for finding tasks by target
CREATE INDEX IF NOT EXISTS idx_tasks_target ON tasks(target_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status) WHERE status IN ('pending', 'running');

-- =============================================================================
-- Studio Jobs Table
-- =============================================================================

-- Educational Note: Studio jobs track content generation requests.
-- Different job types have different output structures, so we use JSONB
-- for flexible storage while keeping common fields in columns.

CREATE TABLE IF NOT EXISTS studio_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- Job type (18 types: audio, video, ad, flash_cards, mind_map, quiz, etc.)
    job_type TEXT NOT NULL,

    -- Status: pending, processing, ready, error
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,

    -- Input configuration (varies by job type)
    -- E.g., for audio: { "format": "podcast", "voice_settings": {...} }
    config JSONB DEFAULT '{}',

    -- Output data (varies by job type)
    -- E.g., for audio: { "script": "...", "audio_url": "...", "duration_seconds": N }
    output JSONB DEFAULT '{}',

    -- Storage paths for generated files
    output_paths JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- Index for listing jobs by project and type
CREATE INDEX IF NOT EXISTS idx_studio_jobs_project ON studio_jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_studio_jobs_type ON studio_jobs(project_id, job_type);

-- =============================================================================
-- Agent Executions Table (Debug Logs)
-- =============================================================================

-- Educational Note: Agent executions store the full message chain for
-- debugging agent behavior. This is optional logging data, not critical
-- for application function.

CREATE TABLE IF NOT EXISTS agent_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- Agent name (e.g., "web_agent", "csv_analyzer")
    agent_name TEXT NOT NULL,

    -- Task description given to the agent
    task TEXT NOT NULL,

    -- Full message chain (for debugging)
    messages JSONB NOT NULL DEFAULT '[]',

    -- Final result from agent
    result JSONB NOT NULL DEFAULT '{}',

    -- Additional metadata (source_id, url, etc.)
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- Index for listing executions by project
CREATE INDEX IF NOT EXISTS idx_agent_executions_project ON agent_executions(project_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_agent ON agent_executions(project_id, agent_name);

-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Atomic cost tracking function
-- Educational Note: Using a database function ensures atomic updates to
-- cost tracking, even with concurrent requests.

CREATE OR REPLACE FUNCTION add_project_cost(
    p_project_id UUID,
    p_model TEXT,
    p_input_tokens INTEGER,
    p_output_tokens INTEGER,
    p_cost_usd NUMERIC(10, 6)
) RETURNS JSONB AS $$
DECLARE
    current_costs JSONB;
    model_costs JSONB;
    new_input INTEGER;
    new_output INTEGER;
    new_cost NUMERIC(10, 6);
BEGIN
    -- Get current cost tracking
    SELECT cost_tracking INTO current_costs
    FROM projects
    WHERE id = p_project_id
    FOR UPDATE;  -- Lock row for atomic update

    IF current_costs IS NULL THEN
        current_costs := '{}'::JSONB;
    END IF;

    -- Get current model costs or initialize
    model_costs := COALESCE(current_costs -> p_model, '{
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0
    }'::JSONB);

    -- Calculate new totals
    new_input := COALESCE((model_costs ->> 'input_tokens')::INTEGER, 0) + p_input_tokens;
    new_output := COALESCE((model_costs ->> 'output_tokens')::INTEGER, 0) + p_output_tokens;
    new_cost := COALESCE((model_costs ->> 'cost_usd')::NUMERIC, 0) + p_cost_usd;

    -- Build updated model costs
    model_costs := jsonb_build_object(
        'input_tokens', new_input,
        'output_tokens', new_output,
        'cost_usd', new_cost
    );

    -- Update project
    UPDATE projects
    SET
        cost_tracking = current_costs || jsonb_build_object(p_model, model_costs),
        updated_at = now()
    WHERE id = p_project_id;

    RETURN model_costs;
END;
$$ LANGUAGE plpgsql;

-- Function to update chat message count
CREATE OR REPLACE FUNCTION update_chat_message_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE chats SET message_count = message_count + 1, updated_at = now()
        WHERE id = NEW.chat_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE chats SET message_count = GREATEST(0, message_count - 1), updated_at = now()
        WHERE id = OLD.chat_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update message count
DROP TRIGGER IF EXISTS trigger_update_chat_message_count ON messages;
CREATE TRIGGER trigger_update_chat_message_count
    AFTER INSERT OR DELETE ON messages
    FOR EACH ROW
    EXECUTE FUNCTION update_chat_message_count();

-- Function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers to relevant tables
DROP TRIGGER IF EXISTS trigger_projects_updated_at ON projects;
CREATE TRIGGER trigger_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trigger_sources_updated_at ON sources;
CREATE TRIGGER trigger_sources_updated_at
    BEFORE UPDATE ON sources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trigger_chats_updated_at ON chats;
CREATE TRIGGER trigger_chats_updated_at
    BEFORE UPDATE ON chats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trigger_studio_jobs_updated_at ON studio_jobs;
CREATE TRIGGER trigger_studio_jobs_updated_at
    BEFORE UPDATE ON studio_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- Chunk Search Functions
-- =============================================================================

-- Full-text search function for chunks (hybrid search component)
-- Educational Note: This function performs PostgreSQL full-text search
-- on chunk text for the local keyword search portion of hybrid search.

CREATE OR REPLACE FUNCTION search_chunks_by_keywords(
    p_source_id UUID,
    p_query TEXT,
    p_limit INTEGER DEFAULT 10
) RETURNS TABLE (
    id TEXT,
    source_id UUID,
    project_id UUID,
    text TEXT,
    page_number INTEGER,
    chunk_number INTEGER,
    token_count INTEGER,
    relevance_score REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.source_id,
        c.project_id,
        c.text,
        c.page_number,
        c.chunk_number,
        c.token_count,
        ts_rank(to_tsvector('english', c.text), plainto_tsquery('english', p_query)) AS relevance_score
    FROM chunks c
    WHERE c.source_id = p_source_id
      AND to_tsvector('english', c.text) @@ plainto_tsquery('english', p_query)
    ORDER BY relevance_score DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Row Level Security (RLS) - Placeholder
-- =============================================================================

-- Educational Note: RLS is disabled for single-user mode.
-- When multi-user is implemented, uncomment and configure these policies.

-- Enable RLS on tables (uncomment for multi-user)
-- ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE chats ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE studio_jobs ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE agent_executions ENABLE ROW LEVEL SECURITY;

-- Example RLS policies (uncomment for multi-user)
-- CREATE POLICY "Users can view own projects" ON projects
--     FOR SELECT USING (user_id = auth.uid());
--
-- CREATE POLICY "Users can insert own projects" ON projects
--     FOR INSERT WITH CHECK (user_id = auth.uid());
--
-- CREATE POLICY "Users can update own projects" ON projects
--     FOR UPDATE USING (user_id = auth.uid());
--
-- CREATE POLICY "Users can delete own projects" ON projects
--     FOR DELETE USING (user_id = auth.uid());

-- =============================================================================
-- Storage Buckets (run via Supabase Dashboard or API)
-- =============================================================================

-- Note: Storage buckets cannot be created via SQL.
-- Create these via Supabase Dashboard (http://localhost:54323):
--   1. sources - For raw uploads and processed text
--   2. studio - For generated audio, video, images
--   3. ai-outputs - For AI-generated content (plots, etc.)

-- Example bucket policies (set via Dashboard):
-- {
--   "name": "sources",
--   "public": false,
--   "file_size_limit": 104857600,  -- 100MB
--   "allowed_mime_types": ["application/pdf", "image/*", "audio/*", ...]
-- }
