-- ============================================================
-- MoodMix Database Schema
-- PostgreSQL 16+ with pgvector extension
-- Hosted on Supabase
-- ============================================================

create extension if not exists vector;

-- ============================================================
-- GENRES
-- Pre-seeded lookup table. LLM classifier picks from this
-- controlled list to avoid duplicates (lo-fi vs lofi vs Lo-Fi).
-- ============================================================

create table genres (
  id uuid primary key default gen_random_uuid(),
  name text unique not null,    -- Display name: "Lo-Fi", "Jazz", "Classical"
  slug text unique not null,    -- URL/query friendly: "lo-fi", "jazz", "classical"
  created_at timestamptz not null default now()
);

-- Seed data — focused on genres well-suited for background music
insert into genres (name, slug) values
  ('Lo-Fi', 'lo-fi'),
  ('Hip-Hop', 'hip-hop'),
  ('Synthwave', 'synthwave'),
  ('Chill Electronic', 'chill-electronic'),
  ('Deep House', 'deep-house'),
  ('Drum & Bass', 'drum-and-bass'),
  ('Neo-Soul / R&B', 'neo-soul-r-and-b'),
  ('Jazz', 'jazz'),
  ('Ambient', 'ambient'),
  ('Acoustic & Piano', 'acoustic-and-piano');

-- ============================================================
-- MIXES
-- Core table. Each row = one YouTube mix (typically 30min-3h).
-- mood_vector is a 3D vector for pgvector cosine similarity.
-- Individual float columns exist for slider filtering + display.
-- ============================================================

create table mixes (
  id uuid primary key default gen_random_uuid(),

  -- YouTube metadata (from crawler)
  youtube_id text unique not null,
  title text not null,
  channel_name text,
  channel_id text,
  description text,
  tags text[],                          -- YouTube tags array
  duration_seconds integer not null,
  thumbnail_url text,
  published_at timestamptz,
  view_count integer,

  -- Mood vector (3D, for pgvector similarity search)
  -- [mood, energy, instrumentation]
  mood_vector vector(3),

  -- Individual mood scores (for slider filtering + card display)
  mood float,                            -- -1.0 (dark) to +1.0 (bright)
  energy float,                         -- -1.0 (chill) to +1.0 (dynamic)
  instrumentation float,                -- -1.0 (organic) to +1.0 (electronic)

  -- Vocal classification
  has_vocals boolean,

  -- Classification metadata
  classification_confidence float,      -- 0.0 to 1.0 (average across dimensions)

  -- Timestamps
  created_at timestamptz not null default now(),
  unavailable_at timestamptz             -- When it was marked unavailable (null if active)
);

-- pgvector HNSW index for fast cosine similarity search
create index idx_mixes_mood_vector on mixes using hnsw (mood_vector vector_cosine_ops);

-- Frequently filtered columns
create index idx_mixes_youtube_id on mixes (youtube_id);
create index idx_mixes_channel_id on mixes (channel_id);

-- ============================================================
-- MIX_GENRES
-- Many-to-many: each mix can have 1-3 genres.
-- ============================================================

create table mix_genres (
  mix_id uuid not null references mixes(id) on delete cascade,
  genre_id uuid not null references genres(id) on delete cascade,
  primary key (mix_id, genre_id)
);

-- Fast lookup: "all mixes in genre X"
create index idx_mix_genres_genre_id on mix_genres (genre_id);

-- ============================================================
-- SEED_CHANNELS
-- YouTube channels the crawler monitors for new mixes.
-- ============================================================

create table seed_channels (
  id uuid primary key default gen_random_uuid(),
  channel_id text unique not null,       -- YouTube channel ID (UC...)
  channel_name text not null,
  uploads_playlist_id text,              -- YouTube "uploads" playlist ID (UU...), cached to avoid extra API call
  active boolean not null default true,  -- Set false to stop crawling without deleting
  last_crawled_at timestamptz,
  total_mixes_found integer not null default 0,
  created_at timestamptz not null default now()
);

-- ============================================================
-- PIPELINE_RUNS
-- Log of each pipeline execution (crawl, classify, availability check).
-- Powers the /api/admin/pipeline/status endpoint.
-- ============================================================

create type pipeline_type as enum ('channel_crawl', 'keyword_search', 'classification', 'availability_check', 'analytics');
create type pipeline_run_status as enum ('running', 'completed', 'failed');

create table pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  pipeline_type pipeline_type not null,
  status pipeline_run_status not null default 'running',
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  mixes_processed integer not null default 0,  -- How many mixes were crawled/classified/checked
  mixes_added integer not null default 0,      -- New mixes added to catalog (crawl) or classified (classification)
  error_message text,                          -- If failed, why
  metadata jsonb                               -- Flexible: quota used, channels crawled, queries run, etc.
);

create index idx_pipeline_runs_type on pipeline_runs (pipeline_type, started_at desc);
