# NoobBook Architecture (Codex)

This document summarizes the current architecture of the NoobBook codebase in this repository, based on the implementation in `backend/`, `frontend/`, and `docker/`.

## 1. System Topology

NoobBook is a 3-tier web application with external AI/data integrations.

- Frontend: React + TypeScript SPA built by Vite, served by Nginx in Docker.
- Backend: Flask REST API (with Flask-SocketIO initialized) that orchestrates auth, source processing, chat, and studio generation.
- Data plane: Supabase (Postgres + Storage + Auth) plus Pinecone for vector search.
- AI providers: Anthropic (primary LLM), OpenAI (embeddings/LLM utilities), Google (Imagen/Veo), ElevenLabs (TTS/STT), Tavily (web search).

At runtime (Docker setup):

- `frontend` container on port `80`.
- `backend` container on port `5001`.
- `migrate` one-shot container applies `backend/supabase/init.sql` and `backend/supabase/migrations/*.sql`.
- Supabase stack is started separately from `docker/supabase/docker-compose.yml`.

## 2. Frontend Architecture

### 2.1 Application Shell

Key files:

- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/project/ProjectWorkspace.tsx`

Flow:

- `App` performs auth bootstrap (`/auth/me`), then routes:
- `*` -> Dashboard and project list.
- `/projects/:projectId` -> Notebook-style 3-panel workspace.

Workspace layout (`ProjectWorkspace`):

- Left: Sources panel.
- Center: Chat panel.
- Right: Studio panel.

State orchestration in workspace:

- `sourcesVersion` and `costsVersion` counters trigger refresh in chat/header.
- Active chat and per-chat selected source IDs are shared between `ChatPanel` and `SourcesPanel`.
- Studio signals emitted by chat are passed to `StudioPanel`.

### 2.2 API Client and Auth Session

Key file:

- `frontend/src/lib/api/client.ts`

Pattern:

- Axios base URL from `VITE_API_URL` or `VITE_API_HOST` fallback.
- JWT access token attached via interceptors.
- Automatic refresh on 401 using `/auth/refresh` and stored refresh token.
- `getAuthUrl()` appends `?token=` for browser-managed requests (`img`, `video`, `iframe`) that cannot set headers.

Important implementation detail:

- Many service files use global `axios` instead of a single `api` instance; both are patched with shared 401 refresh handling.

### 2.3 Feature Modules

- `frontend/src/components/sources/*`: ingestion UI + polling + per-chat source selection.
- `frontend/src/components/chat/*`: chat lifecycle, optimistic message UX, studio signal sync.
- `frontend/src/components/studio/*`: generation tools and output sections (jobs per content type).
- `frontend/src/lib/api/studio/*`: API wrappers for each studio feature.
- Shared UI primitives are in `frontend/src/components/ui/*` (shadcn/Radix style).

## 3. Backend Architecture

### 3.1 App Bootstrap and Request Pipeline

Key files:

- `backend/run.py`
- `backend/app/__init__.py`
- `backend/config.py`
- `backend/app/api/__init__.py`

Bootstrap sequence:

1. Load env, create Flask app via factory.
2. Configure CORS and initialize SocketIO (`async_mode='threading'`).
3. Register main API blueprint under `/api/v1`.
4. Optionally bootstrap admin account from env.
5. Apply auth and project-access guards via request hooks.

Auth enforcement layers:

- Global API `before_request` in `app/api/__init__.py` validates JWT (except `/auth/*`) and sets `g.user_id`.
- App-level hook in `app/__init__.py` enforces optional RBAC and per-project authorization using `project_service.has_project_access`.

### 3.2 API Blueprints

Modular route groups in `backend/app/api/*`:

- `auth`: signup/signin/signout/refresh/me.
- `projects`: project CRUD, costs, memory.
- `chats`: chat CRUD and selected source IDs.
- `messages`: message send endpoint (chat orchestration entry point).
- `sources`: file/url/text/research/database sources + processing controls.
- `studio`: async generation endpoints for many content types.
- `settings`: API keys, users, databases, processing settings.
- `brand`: brand assets/config.
- `google`, `transcription`, `prompts` and others.

### 3.3 Service Layer (Core Domain Organization)

Main backend boundary is service-oriented under `backend/app/services/`:

- `chat_services/`: chat orchestration.
- `source_services/`: source metadata + upload + processing dispatch.
- `studio_services/`: studio job metadata and content-specific generation services.
- `data_services/`: persistence-facing CRUD for projects/chats/messages/users/databases.
- `integrations/`: provider SDK wrappers (supabase, claude, openai, pinecone, google, elevenlabs, tavily, youtube).
- `tool_executors/`: tool-call dispatch for agent/tool-use flows.
- `ai_agents/` and `ai_services/`: specialized generation/reasoning utilities.
- `background_services/task_service.py`: lightweight task queue over `ThreadPoolExecutor`.

This gives a practical layering:

- API routes: transport + validation.
- Service layer: orchestration/business logic.
- Integration/data services: external systems and persistence access.

## 4. Data Architecture

### 4.1 Primary Persistence: Supabase Postgres

Schema defined in:

- `backend/supabase/init.sql`
- `backend/supabase/migrations/*.sql`

Core entities:

- `users`: identity, role, settings, memory, optional Google tokens.
- `projects`: top-level workspace container, costs, memory.
- `sources`: source metadata/status/paths/processing info.
- `chunks`: extracted chunk content metadata.
- `chats`, `messages`: conversation data and citations.
- `background_tasks`: async task tracking.
- `studio_signals`: chat->studio trigger records.
- `studio_jobs`: async generation jobs (newer pattern).
- `database_connections`, `database_connection_users`: external DB integration.
- `brand_assets`, `brand_config`: user-level brand kit (migrated from project-level).

Operational notes:

- Migration runner seeds and tracks applied SQL files via `schema_migrations` table.
- Updated-at triggers and helper SQL functions are used for consistency/stats.

### 4.2 File/Object Storage: Supabase Storage

Buckets (from migrations):

- `raw-files`
- `processed-files`
- `chunks`
- `studio-outputs`
- `brand-assets`

`storage_service` centralizes upload/download/delete and signed URL creation.

### 4.3 Vector Search: Pinecone

`pinecone_service.py` handles:

- Vector upsert/query/delete.
- Namespace isolation by `project_id`.
- Search with optional metadata filters.

Embeddings are produced by embedding services and linked to source/chunk metadata.

## 5. Key Runtime Flows

### 5.1 Source Ingestion and Processing

Entry points:

- `POST /projects/:id/sources` (file)
- `POST /projects/:id/sources/url`
- `POST /projects/:id/sources/text`
- `POST /projects/:id/sources/research`
- `POST /projects/:id/sources/database`

Flow:

1. Source metadata row created in `sources`.
2. Raw file or synthetic source artifact stored in Supabase Storage.
3. Background task submitted via `task_service`.
4. `source_processing_service` dispatches by file extension/type to processor modules.
5. Processors extract content, create chunks/embeddings, update source status.
6. Source reaches `ready` (or `error`).

Design characteristics:

- Cooperative cancellation (`cancel` endpoints + task cancellation flags).
- Retry support without re-upload.
- Processor-specific modules for PDF, DOCX, PPTX, CSV, image, audio, link, database, research.

### 5.2 Chat + RAG + Tool Use

Entry point:

- `POST /projects/:project_id/chats/:chat_id/messages`

Orchestration (`MainChatService`):

1. Persist user message.
2. Build system prompt from base prompt + memory/context + brand context.
3. Determine available tools (source search, memory, csv/database analyzers, studio signals, knowledge-base tools).
4. Call Claude and iterate tool-use loop up to `MAX_TOOL_ITERATIONS`.
5. Persist assistant message and citations.
6. Trigger auxiliary background tasks (e.g., chat naming/studio signal updates).

RAG characteristics:

- Per-chat selected source IDs are supported (`chats.selected_source_ids`).
- Semantic retrieval through Pinecone and tool executors.
- Citation-aware response formatting on stored messages.

### 5.3 Studio Generation Jobs

Pattern across studio endpoints:

1. Create job record (`pending`).
2. Submit background task.
3. Return `202` with `job_id`.
4. Frontend polls `.../studio/*-jobs/:job_id`.
5. On completion, generated files are stored in `studio-outputs` and served through route handlers.

Implemented for many content types including audio, blog, business report, components, email, flow diagrams, infographics, marketing strategy, mind maps, PRDs, presentations, quizzes, social posts, video, website, and wireframes.

## 6. Authentication, Authorization, and Roles

Identity model:

- Supabase Auth provides JWT tokens.
- Backend validates bearer/query token and resolves user identity.
- Token validation cache (~60s) reduces repeated auth calls for media-heavy pages.

RBAC model:

- Roles: `admin`, `user`.
- Controlled by `NOOBBOOK_AUTH_REQUIRED` and role checks in `rbac.py`.
- Route-level and project-level ownership checks enforce tenant boundaries.

Modes:

- Single-user fallback supported via default user ID.
- Multi-user auth/RBAC path is present and increasingly integrated.

## 7. Deployment and Environment

### 7.1 Containers and Build

- Backend image installs Python deps + system libs (LibreOffice, FFmpeg, Playwright Chromium).
- Frontend image builds static bundle with Node, then serves via Nginx.
- Backend entrypoint seeds prompt files into mounted `data/` volume non-destructively.

### 7.2 Local/Dev Scripts

- `start.py` runs backend + frontend local dev servers.
- Docker scripts in `docker/` manage setup/stop/reset.

### 7.3 Configuration Surface

Critical env groups:

- Supabase: `SUPABASE_URL`, keys.
- AI providers: Anthropic/OpenAI/Pinecone (+ optional ElevenLabs/Tavily/Google).
- Auth/RBAC toggles and bootstrap admin envs.
- CORS / API host settings.

## 8. Architectural Characteristics

Strengths:

- Clear feature-based backend modularity with service boundaries.
- Unified async pattern for long-running source/studio tasks.
- Practical decoupling of metadata (Postgres), files (Storage), vectors (Pinecone).
- Frontend workspace state maps well to product concepts (sources/chat/studio).

Current tradeoffs / technical notes:

- Flask-SocketIO is initialized but current flows are largely polling-based, not event-push.
- Some docs/comments still mention older local-JSON flows while implementation is Supabase-centric.
- API client usage is split between global `axios` and shared `api` instance; interceptors currently cover both.
- ThreadPoolExecutor-based background processing is simple and effective for moderate load, but not a distributed queue.

## 9. Recommended C4-ish View (Condensed)

- System: NoobBook AI workspace platform.
- Containers:
- Web SPA (React/Nginx)
- API service (Flask)
- Supabase (Auth + Postgres + Storage)
- Pinecone (vector DB)
- External AI APIs (Anthropic/OpenAI/Google/ElevenLabs/Tavily)
- Components (inside API): route blueprints, orchestration services, integration adapters, async task service.
- Code: organized by domain under `app/api` and `app/services` with integration/provider segregation.

