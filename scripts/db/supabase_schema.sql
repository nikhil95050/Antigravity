-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.admin_audit (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  timestamp timestamp with time zone NOT NULL DEFAULT now(),
  admin_chat_id text NOT NULL,
  command text NOT NULL,
  details text NOT NULL DEFAULT ''::text,
  CONSTRAINT admin_audit_pkey PRIMARY KEY (id)
);
CREATE TABLE public.admins (
  chat_id text NOT NULL,
  username text NOT NULL DEFAULT ''::text,
  permission_level text NOT NULL DEFAULT 'admin'::text,
  added_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT admins_pkey PRIMARY KEY (chat_id)
);
CREATE TABLE public.api_usage (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  chat_id text NOT NULL,
  provider text NOT NULL,
  action text NOT NULL,
  timestamp timestamp with time zone NOT NULL DEFAULT now(),
  prompt_tokens integer DEFAULT 0,
  completion_tokens integer DEFAULT 0,
  total_tokens integer DEFAULT 0,
  CONSTRAINT api_usage_pkey PRIMARY KEY (id)
);
CREATE TABLE public.bot_stats (
  metric_name text NOT NULL,
  metric_value bigint NOT NULL DEFAULT 0,
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT bot_stats_pkey PRIMARY KEY (metric_name)
);
CREATE TABLE public.error_logs (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  timestamp timestamp with time zone NOT NULL DEFAULT now(),
  chat_id text NOT NULL DEFAULT ''::text,
  workflow_step text NOT NULL DEFAULT ''::text,
  intent text NOT NULL DEFAULT ''::text,
  error_type text NOT NULL DEFAULT ''::text,
  error_message text NOT NULL DEFAULT ''::text,
  raw_payload text NOT NULL DEFAULT ''::text,
  retry_status text NOT NULL DEFAULT ''::text,
  resolution_status text NOT NULL DEFAULT ''::text,
  CONSTRAINT error_logs_pkey PRIMARY KEY (id)
);
CREATE TABLE public.feedback (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  chat_id text NOT NULL,
  movie_id text NOT NULL,
  reaction_type text NOT NULL,
  timestamp timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT feedback_pkey PRIMARY KEY (id)
);
CREATE TABLE public.history (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  chat_id text NOT NULL,
  movie_id text NOT NULL,
  title text NOT NULL DEFAULT ''::text,
  year text NOT NULL DEFAULT ''::text,
  genres text NOT NULL DEFAULT ''::text,
  language text NOT NULL DEFAULT ''::text,
  rating text NOT NULL DEFAULT ''::text,
  recommended_at timestamp with time zone NOT NULL DEFAULT now(),
  watched boolean NOT NULL DEFAULT false,
  watched_at timestamp with time zone,
  CONSTRAINT history_pkey PRIMARY KEY (id)
);
CREATE TABLE public.movie_metadata (
  movie_id text NOT NULL,
  data_json jsonb NOT NULL,
  last_updated timestamp with time zone DEFAULT now(),
  chat_id text NOT NULL,
  CONSTRAINT movie_metadata_pkey PRIMARY KEY (movie_id)
);
CREATE TABLE public.provider_health (
  provider_name text NOT NULL,
  is_enabled boolean NOT NULL DEFAULT true,
  failure_count integer NOT NULL DEFAULT 0,
  last_failure_at timestamp with time zone,
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT provider_health_pkey PRIMARY KEY (provider_name)
);
CREATE TABLE public.sessions (
  chat_id text NOT NULL,
  session_state text NOT NULL DEFAULT 'idle'::text,
  question_index integer NOT NULL DEFAULT 0,
  pending_question text NOT NULL DEFAULT ''::text,
  answers_mood text NOT NULL DEFAULT ''::text,
  answers_genre text NOT NULL DEFAULT ''::text,
  answers_language text NOT NULL DEFAULT ''::text,
  answers_era text NOT NULL DEFAULT ''::text,
  answers_context text NOT NULL DEFAULT ''::text,
  answers_avoid text NOT NULL DEFAULT ''::text,
  last_recs_json text NOT NULL DEFAULT '[]'::text,
  sim_depth integer NOT NULL DEFAULT 0,
  last_active timestamp with time zone,
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  answers_time text DEFAULT ''::text,
  answers_favorites text DEFAULT ''::text,
  last_question_msg_id bigint,
  overflow_buffer_json text NOT NULL DEFAULT '[]'::text,
  answers_rating text,
  CONSTRAINT sessions_pkey PRIMARY KEY (chat_id)
);
CREATE TABLE public.trailer_cache (
  movie_id text NOT NULL,
  trailer_url text NOT NULL,
  cached_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT trailer_cache_pkey PRIMARY KEY (movie_id)
);
CREATE TABLE public.user_interactions (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  chat_id text NOT NULL,
  username text NOT NULL DEFAULT ''::text,
  input_text text NOT NULL DEFAULT ''::text,
  intent text NOT NULL DEFAULT ''::text,
  timestamp timestamp with time zone NOT NULL DEFAULT now(),
  request_id text,
  response_status text NOT NULL DEFAULT 'pending'::text,
  latency_ms integer,
  error_message text,
  CONSTRAINT user_interactions_pkey PRIMARY KEY (id)
);
CREATE TABLE public.users (
  chat_id text NOT NULL,
  username text NOT NULL DEFAULT ''::text,
  preferred_genres text NOT NULL DEFAULT ''::text,
  disliked_genres text NOT NULL DEFAULT ''::text,
  preferred_language text NOT NULL DEFAULT ''::text,
  preferred_era text NOT NULL DEFAULT ''::text,
  watch_context text NOT NULL DEFAULT ''::text,
  avg_rating_preference numeric,
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  subscriptions text,
  CONSTRAINT users_pkey PRIMARY KEY (chat_id)
);
CREATE TABLE public.watchlist (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  chat_id text NOT NULL,
  movie_id text NOT NULL,
  title text NOT NULL DEFAULT ''::text,
  year text NOT NULL DEFAULT ''::text,
  language text NOT NULL DEFAULT ''::text,
  rating text NOT NULL DEFAULT ''::text,
  genres text NOT NULL DEFAULT ''::text,
  added_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT watchlist_pkey PRIMARY KEY (id)
);
