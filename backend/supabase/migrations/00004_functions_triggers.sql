-- Migration: Helper Functions and Triggers
-- Description: Utility functions and triggers for business logic
-- Created: 2026-01-01

-- ============================================================================
-- PROJECT STATISTICS FUNCTIONS
-- ============================================================================

-- Function to get project statistics
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
    ),
    'total_studio_signals', (
      SELECT COUNT(*) FROM studio_signals ss
      JOIN chats c ON c.id = ss.chat_id
      WHERE c.project_id = p_project_id
    ),
    'total_chunks', (
      SELECT COUNT(*) FROM chunks ch
      JOIN sources s ON s.id = ch.source_id
      WHERE s.project_id = p_project_id
    ),
    'total_file_size', (
      SELECT COALESCE(SUM(file_size), 0) FROM sources WHERE project_id = p_project_id
    ),
    'sources_by_type', (
      SELECT json_object_agg(type, count)
      FROM (
        SELECT type, COUNT(*) as count
        FROM sources
        WHERE project_id = p_project_id
        GROUP BY type
      ) type_counts
    ),
    'sources_by_status', (
      SELECT json_object_agg(status, count)
      FROM (
        SELECT status, COUNT(*) as count
        FROM sources
        WHERE project_id = p_project_id
        GROUP BY status
      ) status_counts
    )
  ) INTO v_stats;
  
  RETURN v_stats;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_project_stats IS 'Get comprehensive statistics for a project';

-- ============================================================================
-- CHAT STATISTICS FUNCTIONS
-- ============================================================================

-- Function to get chat statistics
CREATE OR REPLACE FUNCTION get_chat_stats(p_chat_id UUID)
RETURNS JSON AS $$
DECLARE
  v_stats JSON;
BEGIN
  SELECT json_build_object(
    'total_messages', (SELECT COUNT(*) FROM messages WHERE chat_id = p_chat_id),
    'user_messages', (SELECT COUNT(*) FROM messages WHERE chat_id = p_chat_id AND role = 'user'),
    'assistant_messages', (SELECT COUNT(*) FROM messages WHERE chat_id = p_chat_id AND role = 'assistant'),
    'total_tokens_input', (SELECT COALESCE(SUM(tokens_input), 0) FROM messages WHERE chat_id = p_chat_id),
    'total_tokens_output', (SELECT COALESCE(SUM(tokens_output), 0) FROM messages WHERE chat_id = p_chat_id),
    'total_cost_usd', (SELECT COALESCE(SUM(cost_usd), 0) FROM messages WHERE chat_id = p_chat_id),
    'total_studio_signals', (SELECT COUNT(*) FROM studio_signals WHERE chat_id = p_chat_id),
    'pending_signals', (SELECT COUNT(*) FROM studio_signals WHERE chat_id = p_chat_id AND status = 'pending'),
    'ready_signals', (SELECT COUNT(*) FROM studio_signals WHERE chat_id = p_chat_id AND status = 'ready')
  ) INTO v_stats;
  
  RETURN v_stats;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chat_stats IS 'Get comprehensive statistics for a chat';

-- ============================================================================
-- COST AGGREGATION FUNCTIONS
-- ============================================================================

-- Function to update project costs from messages
CREATE OR REPLACE FUNCTION update_project_costs(p_project_id UUID)
RETURNS VOID AS $$
DECLARE
  v_total_input_tokens BIGINT;
  v_total_output_tokens BIGINT;
  v_total_cost_usd NUMERIC;
  v_costs_by_model JSON;
BEGIN
  -- Calculate total tokens and costs
  SELECT 
    COALESCE(SUM(m.tokens_input), 0),
    COALESCE(SUM(m.tokens_output), 0),
    COALESCE(SUM(m.cost_usd), 0)
  INTO 
    v_total_input_tokens,
    v_total_output_tokens,
    v_total_cost_usd
  FROM messages m
  JOIN chats c ON c.id = m.chat_id
  WHERE c.project_id = p_project_id;
  
  -- Calculate costs by model
  SELECT json_object_agg(model, model_stats)
  INTO v_costs_by_model
  FROM (
    SELECT 
      m.model,
      json_build_object(
        'input_tokens', COALESCE(SUM(m.tokens_input), 0),
        'output_tokens', COALESCE(SUM(m.tokens_output), 0),
        'cost_usd', COALESCE(SUM(m.cost_usd), 0),
        'message_count', COUNT(*)
      ) as model_stats
    FROM messages m
    JOIN chats c ON c.id = m.chat_id
    WHERE c.project_id = p_project_id
    AND m.model IS NOT NULL
    GROUP BY m.model
  ) model_costs;
  
  -- Update project costs
  UPDATE projects
  SET costs = json_build_object(
    'total_input_tokens', v_total_input_tokens,
    'total_output_tokens', v_total_output_tokens,
    'total_cost_usd', v_total_cost_usd,
    'by_model', COALESCE(v_costs_by_model, '{}'::json)
  )
  WHERE id = p_project_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_project_costs IS 'Recalculate and update project costs from all messages';

-- ============================================================================
-- AUTOMATIC COST TRACKING TRIGGER
-- ============================================================================

-- Function to automatically update project costs when messages are added
CREATE OR REPLACE FUNCTION trigger_update_project_costs()
RETURNS TRIGGER AS $$
DECLARE
  v_project_id UUID;
BEGIN
  -- Get project_id from the chat
  SELECT c.project_id INTO v_project_id
  FROM chats c
  WHERE c.id = COALESCE(NEW.chat_id, OLD.chat_id);
  
  -- Update project costs
  PERFORM update_project_costs(v_project_id);
  
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Trigger on message insert/update/delete
CREATE TRIGGER update_project_costs_on_message_change
AFTER INSERT OR UPDATE OR DELETE ON messages
FOR EACH ROW
EXECUTE FUNCTION trigger_update_project_costs();

COMMENT ON TRIGGER update_project_costs_on_message_change ON messages IS 'Automatically update project costs when messages change';

-- ============================================================================
-- CHAT AUTO-NAMING TRIGGER
-- ============================================================================

-- Function to update chat title based on first message
CREATE OR REPLACE FUNCTION trigger_auto_name_chat()
RETURNS TRIGGER AS $$
DECLARE
  v_message_count INTEGER;
  v_chat_title TEXT;
BEGIN
  -- Only process if this is a user message
  IF NEW.role != 'user' THEN
    RETURN NEW;
  END IF;
  
  -- Check if this is the first user message
  SELECT COUNT(*) INTO v_message_count
  FROM messages
  WHERE chat_id = NEW.chat_id
  AND role = 'user';
  
  -- If this is the first message and chat title is still "New Chat"
  IF v_message_count = 1 THEN
    SELECT title INTO v_chat_title
    FROM chats
    WHERE id = NEW.chat_id;
    
    IF v_chat_title = 'New Chat' THEN
      -- Extract first 50 chars of message content as title
      -- Content is JSONB: try 'text' field first, fall back to string representation
      UPDATE chats
      SET title = SUBSTRING(
        COALESCE(
          NEW.content->>'text',
          NEW.content::text
        ), 1, 50
      )
      WHERE id = NEW.chat_id;
    END IF;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on message insert
CREATE TRIGGER auto_name_chat_on_first_message
AFTER INSERT ON messages
FOR EACH ROW
EXECUTE FUNCTION trigger_auto_name_chat();

COMMENT ON TRIGGER auto_name_chat_on_first_message ON messages IS 'Automatically name chat based on first user message';

-- ============================================================================
-- CASCADE DELETE HELPERS
-- ============================================================================

-- Function to clean up orphaned chunks when source is deleted
-- (Already handled by ON DELETE CASCADE, but this is for manual cleanup)
CREATE OR REPLACE FUNCTION cleanup_orphaned_chunks()
RETURNS INTEGER AS $$
DECLARE
  v_deleted_count INTEGER;
BEGIN
  DELETE FROM chunks
  WHERE source_id NOT IN (SELECT id FROM sources);
  
  GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
  RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_orphaned_chunks IS 'Clean up chunks that reference deleted sources (should not happen with CASCADE)';

-- Function to clean up orphaned background tasks
CREATE OR REPLACE FUNCTION cleanup_completed_tasks(p_days_old INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
  v_deleted_count INTEGER;
BEGIN
  DELETE FROM background_tasks
  WHERE status IN ('completed', 'failed', 'cancelled')
  AND completed_at < NOW() - (p_days_old || ' days')::INTERVAL;
  
  GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
  RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_completed_tasks IS 'Clean up old completed/failed/cancelled background tasks';

-- ============================================================================
-- SEARCH FUNCTIONS
-- ============================================================================

-- Function to search sources by name or description
CREATE OR REPLACE FUNCTION search_sources(
  p_project_id UUID,
  p_query TEXT
)
RETURNS TABLE (
  id UUID,
  name TEXT,
  description TEXT,
  type TEXT,
  status TEXT,
  created_at TIMESTAMPTZ
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    s.id,
    s.name,
    s.description,
    s.type,
    s.status,
    s.created_at
  FROM sources s
  WHERE s.project_id = p_project_id
  AND (
    s.name ILIKE '%' || p_query || '%'
    OR s.description ILIKE '%' || p_query || '%'
  )
  ORDER BY s.created_at DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_sources IS 'Search sources by name or description within a project';

-- Function to search chats by title
CREATE OR REPLACE FUNCTION search_chats(
  p_project_id UUID,
  p_query TEXT
)
RETURNS TABLE (
  id UUID,
  title TEXT,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    c.id,
    c.title,
    c.created_at,
    c.updated_at
  FROM chats c
  WHERE c.project_id = p_project_id
  AND c.title ILIKE '%' || p_query || '%'
  ORDER BY c.updated_at DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_chats IS 'Search chats by title within a project';

-- ============================================================================
-- BULK OPERATIONS
-- ============================================================================

-- Function to toggle multiple sources active/inactive
CREATE OR REPLACE FUNCTION toggle_sources_active(
  p_source_ids UUID[],
  p_is_active BOOLEAN
)
RETURNS INTEGER AS $$
DECLARE
  v_updated_count INTEGER;
BEGIN
  UPDATE sources
  SET is_active = p_is_active
  WHERE id = ANY(p_source_ids);
  
  GET DIAGNOSTICS v_updated_count = ROW_COUNT;
  RETURN v_updated_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION toggle_sources_active IS 'Bulk toggle sources active/inactive status';

-- Function to delete multiple chats
CREATE OR REPLACE FUNCTION delete_chats(p_chat_ids UUID[])
RETURNS INTEGER AS $$
DECLARE
  v_deleted_count INTEGER;
BEGIN
  DELETE FROM chats
  WHERE id = ANY(p_chat_ids);
  
  GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
  RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION delete_chats IS 'Bulk delete chats (cascades to messages and studio signals)';

-- ============================================================================
-- ANALYTICS VIEWS
-- ============================================================================

-- View for project analytics
CREATE OR REPLACE VIEW project_analytics AS
SELECT 
  p.id as project_id,
  p.name as project_name,
  p.user_id,
  COUNT(DISTINCT s.id) as total_sources,
  COUNT(DISTINCT c.id) as total_chats,
  COUNT(DISTINCT m.id) as total_messages,
  COUNT(DISTINCT ss.id) as total_studio_signals,
  COALESCE(SUM(s.file_size), 0) as total_file_size,
  COALESCE(SUM(s.token_count), 0) as total_tokens,
  p.costs->>'total_cost_usd' as total_cost_usd,
  p.created_at,
  p.last_accessed
FROM projects p
LEFT JOIN sources s ON s.project_id = p.id
LEFT JOIN chats c ON c.project_id = p.id
LEFT JOIN messages m ON m.chat_id = c.id
LEFT JOIN studio_signals ss ON ss.chat_id = c.id
GROUP BY p.id;

COMMENT ON VIEW project_analytics IS 'Analytics view for project-level statistics';

-- View for user analytics
CREATE OR REPLACE VIEW user_analytics AS
SELECT 
  u.id as user_id,
  u.email,
  COUNT(DISTINCT p.id) as total_projects,
  COUNT(DISTINCT s.id) as total_sources,
  COUNT(DISTINCT c.id) as total_chats,
  COUNT(DISTINCT m.id) as total_messages,
  COALESCE(SUM((p.costs->>'total_cost_usd')::numeric), 0) as total_cost_usd,
  u.created_at as user_created_at,
  MAX(p.last_accessed) as last_active
FROM users u
LEFT JOIN projects p ON p.user_id = u.id
LEFT JOIN sources s ON s.project_id = p.id
LEFT JOIN chats c ON c.project_id = p.id
LEFT JOIN messages m ON m.chat_id = c.id
GROUP BY u.id;

COMMENT ON VIEW user_analytics IS 'Analytics view for user-level statistics';
