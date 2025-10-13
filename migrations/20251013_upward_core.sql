-- prerequisites
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- Concepts
CREATE TABLE IF NOT EXISTS concepts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  domain TEXT,
  embedding VECTOR(1536),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Concept relations
CREATE TABLE IF NOT EXISTS concept_relations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  src_concept UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
  dst_concept UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
  rel_type TEXT NOT NULL,
  weight DOUBLE PRECISION DEFAULT 0.5,
  evidence_ids UUID[] DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_concept_rel_src ON concept_relations(src_concept);
CREATE INDEX IF NOT EXISTS idx_concept_rel_dst ON concept_relations(dst_concept);

-- Memory frames
CREATE TABLE IF NOT EXISTS memory_frames (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  description TEXT,
  tags TEXT[] DEFAULT '{}',
  entity_ids UUID[] DEFAULT '{}',
  time_interval TSRANGE,
  location TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Meaning flows
CREATE TABLE IF NOT EXISTS meaning_flows (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID,
  flow_type TEXT NOT NULL,
  steps JSONB NOT NULL,
  summary TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Rheomode runs
CREATE TABLE IF NOT EXISTS rheomode_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID,
  query_text TEXT NOT NULL,
  steps JSONB NOT NULL,
  result_summary TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Contradictions
CREATE TABLE IF NOT EXISTS contradictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  item1_type TEXT NOT NULL,
  item1_id UUID NOT NULL,
  item2_type TEXT NOT NULL,
  item2_id UUID NOT NULL,
  description TEXT NOT NULL,
  discovered_at TIMESTAMPTZ DEFAULT now(),
  resolved BOOLEAN DEFAULT FALSE,
  resolution_notes TEXT
);

-- Feedback
CREATE TABLE IF NOT EXISTS feedback_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  session_id UUID,
  event_type TEXT NOT NULL,
  target_type TEXT,
  target_id UUID,
  feedback_content TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Hypotheses & Experiments
CREATE TABLE IF NOT EXISTS hypotheses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'open',
  concept_ids UUID[] DEFAULT '{}',
  evidence_ids UUID[] DEFAULT '{}',
  created_by UUID,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS experiments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  hypothesis_id UUID REFERENCES hypotheses(id) ON DELETE SET NULL,
  description TEXT,
  status TEXT DEFAULT 'proposed',
  result_summary TEXT,
  created_by UUID,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- AURA mirrors
CREATE TABLE IF NOT EXISTS aura_projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  aura_project_id TEXT UNIQUE,
  name TEXT NOT NULL,
  description TEXT,
  status TEXT,
  frame_id UUID REFERENCES memory_frames(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS aura_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  aura_task_id TEXT UNIQUE,
  project_id UUID REFERENCES aura_projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  assignee TEXT,
  status TEXT,
  due_date DATE,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Memories extension (if table exists)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='memories') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='memories' AND column_name='frame_id') THEN
      ALTER TABLE memories ADD COLUMN frame_id UUID REFERENCES memory_frames(id) ON DELETE SET NULL;
    END IF;
  END IF;
END $$;

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_memories_frame ON memories(frame_id);
CREATE INDEX IF NOT EXISTS idx_hypotheses_status ON hypotheses(status);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
