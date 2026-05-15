-- Migration: saved_insights — user-saved chat prompts that re-run on a schedule.
-- Created: 2026-05-15
--
-- Use case: a user asks "how many liquidation cases were rated 1 star and
-- blamed chart issues?" and wants that answer refreshed weekly. We save the
-- prompt text and re-send it as a fresh single-turn chat in the same project
-- on the configured cadence. The latest assistant response is stored on the
-- row so the Studio's Saved Insights section can show it without replaying
-- the whole chat.
--
-- `is_running` is the dual-purpose claim flag for the scheduler: an UPDATE
-- ... WHERE id = ? AND NOT is_running atomically claims an insight so two
-- workers (or two scheduler ticks racing) can't both kick off the same
-- refresh. The scheduler clears it on completion (success or error).

CREATE TABLE IF NOT EXISTS saved_insights (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  owner_user_id   UUID NOT NULL,
  title           TEXT NOT NULL,
  prompt          TEXT NOT NULL,
  cadence         TEXT NOT NULL CHECK (cadence IN ('daily', 'weekly')),
  last_run_at     TIMESTAMPTZ,
  last_result     TEXT,
  last_chat_id    UUID,
  last_error      TEXT,
  is_running      BOOLEAN NOT NULL DEFAULT false,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS saved_insights_project_id_idx ON saved_insights(project_id);
CREATE INDEX IF NOT EXISTS saved_insights_owner_idx     ON saved_insights(owner_user_id);
-- Partial index supports the scheduler's "find due" query cheaply.
CREATE INDEX IF NOT EXISTS saved_insights_due_idx
  ON saved_insights(last_run_at)
  WHERE NOT is_running;

CREATE OR REPLACE FUNCTION saved_insights_touch_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS saved_insights_touch ON saved_insights;
CREATE TRIGGER saved_insights_touch
  BEFORE UPDATE ON saved_insights
  FOR EACH ROW EXECUTE FUNCTION saved_insights_touch_updated_at();

ALTER TABLE saved_insights ENABLE ROW LEVEL SECURITY;

-- Owners read and mutate only their own insights. The backend uses the
-- service-role JWT for scheduler-driven writes (which bypasses RLS), so
-- these policies are about hardening direct authenticated access.
DROP POLICY IF EXISTS "saved_insights_owner_select" ON saved_insights;
CREATE POLICY "saved_insights_owner_select" ON saved_insights
  FOR SELECT TO authenticated
  USING (owner_user_id = auth.uid());

DROP POLICY IF EXISTS "saved_insights_owner_write" ON saved_insights;
CREATE POLICY "saved_insights_owner_write" ON saved_insights
  FOR ALL TO authenticated
  USING (owner_user_id = auth.uid())
  WITH CHECK (owner_user_id = auth.uid());

COMMENT ON TABLE saved_insights IS
  'User-saved prompts that auto-refresh on a daily or weekly schedule. The scheduler re-sends the prompt as a single-turn chat in the same project and stores the assistant response in last_result.';
