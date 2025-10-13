## FastAPI routes (in app.py)

- GET /debug/routers — Shows which routers mounted successfully and which failed at import time. (app.py:57-66)
- GET /healthz — Cheap liveness probe with vendor init sanity. (app.py:68-104)

## Database usage summary

- No ORM/migrations detected.
- Raw SQL schema present:
  - public.users — id, email, name, role, created_at (supabase_schema.sql:21-27)
  - public.sessions — id, user_id, title, created_at (supabase_schema.sql:32-37)
  - public.messages — id, session_id, role, content, tokens, latency_ms, model, created_at (supabase_schema.sql:42-51)
  - public.files — id, filename, mime_type, bytes, storage_url, text_extracted, created_at (supabase_schema.sql:58-66)
  - public.memories — id, type, title, text, tags, source, file_id, session_id, author_user_id, role_view, created_at, updated_at, dedupe_hash, embedding_id (supabase_schema.sql:72-87)
  - public.entities — id, name, type, created_at (supabase_schema.sql:100-106)
  - public.entity_mentions — entity_id, memory_id, weight (supabase_schema.sql:110-115)
  - public.entity_edges — src, dst, rel, weight (supabase_schema.sql:119-124)
  - public.tool_runs — id, name, input_json, output_json, success, latency_ms, created_at (supabase_schema.sql:129-137)
  - view public.debug_recent_memories (supabase_schema.sql:143-147)

## Background jobs/workers

- None detected.

## Vector index usage mentions

- app.py — health check uses Pinecone index via vendors client (app.py:95-99)
- vendors/pinecone_client.py — Index factory and safe_query wrapper (vendors/pinecone_client.py:13-16,18-44)
- router/chat.py — semantic retrieval via Pinecone safe_query (router/chat.py:75-83)
- router/search.py — semantic search via Pinecone safe_query (router/search.py:71-79)
- router/ingest.py — obtains Pinecone index for upserts (router/ingest.py:43,72-88)
- router/memories.py — upserts using Pinecone index (router/memories.py:41-58)
- router/debug_selftest.py — index init and query roundtrip (router/debug_selftest.py:54-58,66-69)
- agent/pipeline.py — direct Pinecone query helper (agent/pipeline.py:38-53)
- agent/retrieval.py — Pinecone init/index usage (agent/retrieval.py:51-53)
- scripts/create_pinecone_index.py — index creation script (scripts/create_pinecone_index.py:4-13)

## Environment variables referenced

- OPENAI_API_KEY — vendors/openai_client.py:5; app.py:102
- CHAT_MODEL — vendors/openai_client.py:9; router/chat.py:176,313,320; ingest/pipeline.py:91; guardrails/redteam.py:18
- EMBED_MODEL — config.py:15; vendors/openai_client.py:10; router/chat.py:67; router/search.py:54; router/debug_selftest.py:46; ingest/pipeline.py:204
- EMBED_DIM — config.py:17,34-38; router/chat.py:68-71; router/search.py:57-59; router/debug_selftest.py:93-95; ingest/pipeline.py:205-206
- X_API_KEY — config.py:19; router/chat.py:61; router/upload.py:31; router/search.py:47; router/debug_selftest.py:21; router/ingest.py:34; router/entities.py:12; router/memories.py:29; router/debug.py:12
- ACTIONS_API_KEY — router/debug.py:12
- DISABLE_AUTH — router/debug.py:13
- MEMORIES_TEXT_COLUMN — config.py:16; router/chat.py:127; router/search.py:87; router/upload.py:87,104,159; router/ingest.py:83; router/memories.py:56
- TOPK_PER_TYPE — config.py:45; router/chat.py:222; agent/pipeline.py:115
- MAX_CONTEXT_TOKENS — config.py:44; memory/selection.py:6
- RECENCY_HALFLIFE_DAYS — config.py:46; memory/selection.py:8; agent/pipeline.py:31
- RECENCY_FLOOR — config.py:47
- SUPABASE_URL — config.py:8; vendors/supabase_client.py:13
- SUPABASE_SERVICE_ROLE_KEY — vendors/supabase_client.py:14
- SUPABASE_DEFAULT_USER_ID — agent/store.py:50
- PINECONE_API_KEY — config.py:9; vendors/pinecone_client.py:13; scripts/create_pinecone_index.py:4; agent/retrieval.py:38
- PINECONE_INDEX — config.py:10; vendors/pinecone_client.py:14; scripts/create_pinecone_index.py:5; app.py:83
- PINECONE_ENV — agent/retrieval.py:51
- PINECONE_CLOUD — scripts/create_pinecone_index.py:11
- PINECONE_REGION — scripts/create_pinecone_index.py:12
- BASE_URL — tests/evals/replay.py:4
- CHUNK_SIZE — router/upload.py:69
- CHUNK_OVERLAP — router/upload.py:70
- UPLOAD_ALSO_STORE_FULLTEXT_SEMANTIC — router/upload.py:91
- ENABLE_UPLOAD_SIGNAL_EXTRACTION — router/upload.py:114
- INGEST_MAX_ITEMS — router/ingest.py:46
- MAX_CHUNKS_PER_FILE — ingest/pipeline.py:50
- EXTRACTOR_MODEL — ingest/pipeline.py:119; memory/autosave_classifier.py:38
- UPSERT_MODE — ingest/pipeline.py:193
- SIMHASH_DISTANCE — ingest/pipeline.py:194
- OPENAI_CHAT_MODEL — vendors/openai_client.py:9
- OPENAI_EMBED_MODEL — vendors/openai_client.py:10
- INGEST_USER_ID — scripts/ingest_from_files.py:16
- DEFAULT_INGEST_TAGS — scripts/ingest_from_files.py:17
