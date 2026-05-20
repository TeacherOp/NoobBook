-- Migration: list_chats_with_message_count — count image-attachment messages
-- Description: 00029 introduced this RPC with a filter that excluded ALL
--              jsonb_typeof(content) = 'array' rows on the assumption that
--              array content always meant tool_use / tool_result wrappers.
--
--              That assumption broke when inline image attachments shipped:
--              user messages with a screenshot persist as
--                  [{"type":"image","storage_path":...}, {"type":"text","text":"..."}]
--              i.e. array-typed content that IS user-visible. The previous
--              SQL undercounted those messages in the chat sidebar, and the
--              mirror Python filter (`_is_displayable_message`) dropped them
--              from the chat transcript entirely.
--
--              This migration recreates the RPC with a more precise array
--              filter that mirrors the corrected Python logic:
--                - skip arrays containing any tool_use / tool_result block
--                - count arrays that contain an image block (with or without
--                  text) — those are the inline-attachment user messages
--                - count arrays whose text blocks have non-empty trimmed text

CREATE OR REPLACE FUNCTION list_chats_with_message_count(p_project_id UUID)
RETURNS TABLE (
    id UUID,
    title TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    costs JSONB,
    message_count BIGINT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        c.id,
        c.title,
        c.created_at,
        c.updated_at,
        c.costs,
        COALESCE((
            SELECT COUNT(*)
            FROM messages m
            WHERE m.chat_id = c.id
              AND m.role IN ('user', 'assistant')
              AND (
                  -- string-typed JSONB: "hello" → trimmed text length > 0
                  (jsonb_typeof(m.content) = 'string'
                      AND length(btrim(m.content #>> '{}')) > 0)
                  -- object-typed JSONB: {"text":"hello"} → text field non-empty
                  OR (jsonb_typeof(m.content) = 'object'
                      AND length(btrim(COALESCE(m.content->>'text', ''))) > 0)
                  -- array-typed JSONB: user message with inline image
                  -- attachments. Allowed if it contains NO tool_use/
                  -- tool_result block, AND has either an image block or a
                  -- text block with non-empty content.
                  OR (jsonb_typeof(m.content) = 'array'
                      AND NOT EXISTS (
                          SELECT 1 FROM jsonb_array_elements(m.content) elem
                          WHERE elem->>'type' IN ('tool_use', 'tool_result')
                      )
                      AND EXISTS (
                          SELECT 1 FROM jsonb_array_elements(m.content) elem
                          WHERE elem->>'type' = 'image'
                             OR (elem->>'type' = 'text'
                                 AND length(btrim(COALESCE(elem->>'text', ''))) > 0)
                      ))
              )
        ), 0)::BIGINT AS message_count
    FROM chats c
    WHERE c.project_id = p_project_id
    ORDER BY c.updated_at DESC;
$$;

GRANT EXECUTE ON FUNCTION list_chats_with_message_count(UUID) TO anon, authenticated, service_role;
