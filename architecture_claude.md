# NoobBook Architecture Document

> An open-source NotebookLM alternative — AI-powered document Q&A with multi-modal source ingestion, RAG-based chat, and studio content generation.

---

## Table of Contents

1. [High-Level Overview](#1-high-level-overview)
2. [System Architecture](#2-system-architecture)
3. [Backend Architecture](#3-backend-architecture)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Data Layer](#5-data-layer)
6. [AI & LLM Integration Patterns](#6-ai--llm-integration-patterns)
7. [RAG Pipeline](#7-rag-pipeline)
8. [Source Processing Pipeline](#8-source-processing-pipeline)
9. [Studio Content Generation](#9-studio-content-generation)
10. [Authentication & Multi-User](#10-authentication--multi-user)
11. [Infrastructure & Deployment](#11-infrastructure--deployment)
12. [Key Design Patterns](#12-key-design-patterns)

---

## 1. High-Level Overview

NoobBook is a full-stack web application with three core capabilities:

1. **Multi-modal source ingestion** — Upload PDFs, DOCX, PPTX, images, audio, YouTube videos, URLs, CSVs, and database connections. Each source type has a dedicated processor that extracts text content.

2. **RAG-based chat** — Conversational AI that searches ingested sources using hybrid search (keyword + semantic), cites specific chunks, and maintains per-user and per-project memory.

3. **Studio content generation** — AI agents that produce documents, presentations, emails, audio overviews, videos, mind maps, blogs, wireframes, and more from source material.

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, Radix UI |
| Backend | Python 3.11, Flask, Flask-SocketIO, Flask-CORS |
| Database | PostgreSQL 15 (self-hosted Supabase) with pgvector |
| File Storage | Supabase Storage (S3-compatible, MinIO on macOS) |
| Vector DB | Pinecone (cosine similarity, 1536-dim OpenAI embeddings) |
| LLM | Anthropic Claude (Sonnet for chat/extraction, Haiku for summaries/naming) |
| Embeddings | OpenAI text-embedding-3-small |
| Audio | ElevenLabs (transcription, text-to-speech) |
| Search | Tavily (web search fallback) |
| Containerization | Docker Compose (16 Supabase containers + 3 app containers) |

---

## 2. System Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                      │
│                    React 19 + Vite + Tailwind + shadcn                     │
│                                                                            │
│  ┌──────────────┐  ┌──────────────────────┐  ┌────────────────────────┐   │
│  │ Sources Panel │  │    Chat Panel         │  │    Studio Panel        │   │
│  │              │  │                        │  │                        │   │
│  │ Upload/Import│  │ RAG Q&A + Citations    │  │ Audio, Video, Docs,   │   │
│  │ Process/View │  │ Voice Input            │  │ Presentations, Email  │   │
│  │ Per-Chat Sel │  │ Memory + Signals       │  │ Mind Maps, Blogs...   │   │
│  └──────────────┘  └──────────────────────┘  └────────────────────────┘   │
│                              │ Axios + JWT                                 │
└──────────────────────────────┼─────────────────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │    Nginx / Vite      │
                    │  (Proxy /api → :5001)│
                    └──────────┬──────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────────────────┐
│                              BACKEND                                       │
│                    Flask + Flask-SocketIO                                   │
│                                                                            │
│  ┌─────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Routes  │→│   Services    │→│  Integrations  │→│  External APIs    │  │
│  │ (API)   │  │ (Business    │  │ (Claude,       │  │ (Anthropic,      │  │
│  │         │  │  Logic)      │  │  OpenAI,       │  │  OpenAI,         │  │
│  │ 7 blue- │  │              │  │  Pinecone,     │  │  Pinecone,       │  │
│  │ prints  │  │ Chat, Source,│  │  Supabase,     │  │  ElevenLabs,     │  │
│  │         │  │ AI, Studio,  │  │  ElevenLabs,   │  │  Google,         │  │
│  │         │  │ Background   │  │  Google, etc.) │  │  Tavily)         │  │
│  └─────────┘  └──────────────┘  └──────────────┘  └───────────────────┘  │
│                       │                                                    │
│              ┌────────▼────────┐                                          │
│              │  Data Services   │                                          │
│              │  (CRUD via       │                                          │
│              │   Supabase)      │                                          │
│              └────────┬────────┘                                          │
└───────────────────────┼────────────────────────────────────────────────────┘
                        │
          ┌─────────────▼──────────────┐
          │     SUPABASE (Self-Hosted)  │
          │                             │
          │  PostgreSQL + pgvector      │
          │  Storage (raw, processed,   │
          │    chunks, studio, brand)   │
          │  Auth (JWT, RLS)            │
          │  Kong API Gateway           │
          └─────────────────────────────┘
```

---

## 3. Backend Architecture

### 3.1 Directory Structure

```
backend/
├── run.py                          # Flask entry point (SocketIO server)
├── config.py                       # Environment-based configuration classes
├── app/
│   ├── __init__.py                 # Application factory (create_app)
│   ├── api/
│   │   └── __init__.py             # Main API blueprint (/api/v1)
│   ├── routes/                     # HTTP endpoint handlers
│   │   ├── project_routes.py       # /projects CRUD
│   │   ├── chat_routes.py          # /projects/{id}/chats + messages
│   │   ├── source_routes.py        # /projects/{id}/sources upload/process
│   │   ├── studio_routes.py        # /projects/{id}/studio generation
│   │   ├── settings_routes.py      # /settings (API keys, databases)
│   │   ├── google_routes.py        # /google (OAuth, Drive)
│   │   ├── auth_routes.py          # /auth (signin, signup, refresh)
│   │   ├── transcription_routes.py # /transcription (ElevenLabs config)
│   │   ├── brand_routes.py         # /brand (config, assets)
│   │   └── citation_routes.py      # /citations (chunk lookup)
│   ├── config/                     # Configuration loaders
│   │   ├── prompt_loader.py        # System prompt JSON loading
│   │   ├── tool_loader.py          # Tool definition JSON loading
│   │   ├── tier_loader.py          # Rate limit tier configuration
│   │   ├── context_loader.py       # Dynamic source/memory context builder
│   │   └── brand_context_loader.py # Brand guidelines for studio agents
│   ├── services/
│   │   ├── chat_services/          # RAG chat (main_chat_service.py)
│   │   ├── source_services/        # Source CRUD + processing pipeline
│   │   │   ├── source_service.py
│   │   │   ├── source_processing/  # Per-type processors (pdf, docx, etc.)
│   │   │   └── source_upload/      # Upload handlers (file, url, text)
│   │   ├── ai_services/            # Single-call AI utilities
│   │   │   ├── pdf_service.py      # Vision-based PDF extraction
│   │   │   ├── pptx_service.py     # Vision-based PPTX extraction
│   │   │   ├── image_service.py    # Image content extraction
│   │   │   ├── summary_service.py  # Source summary generation
│   │   │   ├── memory_service.py   # Memory merge via Haiku
│   │   │   ├── embedding_service.py# Chunk → embed → upsert pipeline
│   │   │   └── chat_naming_service.py
│   │   ├── ai_agents/              # Multi-turn agentic loops
│   │   │   ├── web_agent_service.py        # URL content extraction
│   │   │   ├── csv_analyzer_agent.py       # CSV data analysis
│   │   │   ├── database_analyzer_agent.py  # SQL query agent
│   │   │   ├── email_agent_service.py      # Email generation
│   │   │   ├── presentation_agent_service.py
│   │   │   ├── website_agent_service.py
│   │   │   ├── blog_agent_service.py
│   │   │   └── ...                 # 10+ more studio agents
│   │   ├── tool_executors/         # Execute Claude tool calls
│   │   │   ├── source_search_executor.py   # Hybrid search
│   │   │   ├── memory_executor.py
│   │   │   ├── studio_signal_executor.py
│   │   │   └── web_agent_executor.py
│   │   ├── background_services/    # ThreadPoolExecutor task queue
│   │   │   └── task_service.py
│   │   ├── data_services/          # CRUD (Supabase queries)
│   │   │   ├── chat_service.py
│   │   │   ├── project_service.py
│   │   │   ├── message_service.py
│   │   │   ├── brand_asset_service.py
│   │   │   ├── brand_config_service.py
│   │   │   └── user_service.py
│   │   ├── integrations/           # External API clients
│   │   │   ├── claude/claude_service.py    # Anthropic API wrapper
│   │   │   ├── openai/openai_service.py    # Embeddings (text-embedding-3-small)
│   │   │   ├── pinecone/pinecone_service.py# Vector search
│   │   │   ├── supabase/                   # DB client, auth, storage
│   │   │   ├── elevenlabs/                 # Audio, TTS, transcription
│   │   │   ├── google/                     # Drive, Imagen, Video
│   │   │   ├── youtube/                    # Transcript extraction
│   │   │   ├── tavily/                     # Web search
│   │   │   └── knowledge_bases/            # Jira, Notion connectors
│   │   └── tools/                  # Tool definition JSON schemas
│   │       ├── chat_tools/         # search_sources, memory, studio_signal
│   │       ├── pdf_tools/          # PDF extraction tools
│   │       ├── web_agent/          # web_fetch, web_search, tavily
│   │       └── ...                 # Per-agent tool categories
│   └── utils/
│       ├── claude_parsing_utils.py # Centralized Claude response parsing
│       ├── embedding_utils.py      # Token counting (tiktoken)
│       ├── cost_tracking.py        # Per-project API cost tracking
│       ├── path_utils.py           # Centralized path management
│       ├── rate_limit_utils.py     # RateLimiter class
│       ├── batching_utils.py       # Batch processing helper
│       ├── auth_middleware.py      # JWT validation
│       ├── text/
│       │   ├── chunking.py         # Token-based text chunking (~200 tokens)
│       │   ├── cleaning.py         # Text normalization for embeddings
│       │   ├── page_markers.py     # === TYPE PAGE N of M === format
│       │   └── processed_output.py # Standardized processed file format
│       └── ...                     # pdf_utils, docx_utils, pptx_utils
├── data/
│   └── prompts/                    # System prompt JSON configs
└── supabase/
    ├── init.sql                    # Combined schema (fresh DB)
    └── migrations/                 # 13 incremental migration files
```

### 3.2 Application Factory

The Flask app uses the application factory pattern (`create_app()` in `app/__init__.py`):

1. Load config from `config.py` based on `FLASK_ENV`
2. Initialize Flask-CORS with `ALLOWED_ORIGINS`
3. Register the main API blueprint at `/api/v1`
4. Apply auth middleware via `@api_bp.before_request` (skips public routes like `/auth/*`)
5. Initialize Flask-SocketIO for WebSocket support

### 3.3 Service Layer Pattern

The backend follows a strict layered architecture:

```
Routes (thin HTTP handlers)
    → validate request, extract params
    → call service method
    → return JSON response

Services (business logic)
    → orchestrate operations
    → call data services for persistence
    → call integrations for external APIs
    → call utils for parsing/formatting

Data Services (CRUD)
    → Supabase queries via supabase-py
    → No business logic

Integrations (external API wrappers)
    → Thin wrappers around SDK clients
    → Lazy initialization (not at import time)
    → Singleton instances
```

### 3.4 Configuration System

Three loader modules manage runtime configuration:

**Prompt Loader** (`config/prompt_loader.py`): Loads system prompt JSON files from `data/prompts/`. Each config specifies the model, temperature, max_tokens, and system prompt text. Supports project-level custom prompts with fallback to global defaults.

**Tool Loader** (`config/tool_loader.py`): Loads Claude tool definitions from JSON schemas in `services/tools/{category}/{tool}.json`. Supports lazy loading and category-based organization.

**Tier Loader** (`config/tier_loader.py`): Maps `ANTHROPIC_TIER` (1-4) to rate limit parameters:

| Tier | Workers | Pages/min | RPM | Use Case |
|------|---------|-----------|-----|----------|
| 1 | 4 | 10 | 50 | Free tier |
| 2 | 16 | 100 | 1000 | Standard |
| 3 | 24 | 200 | 2000 | Pro |
| 4 | 80 | 1500 | 4000 | Enterprise |

**Context Loader** (`config/context_loader.py`): Dynamically builds source and memory context for chat system prompts. Handles per-chat source selection (all sources, no sources, or specific source IDs).

---

## 4. Frontend Architecture

### 4.1 Directory Structure

```
frontend/src/
├── main.tsx                        # React 19 entry with StrictMode
├── App.tsx                         # Router + auth gate
├── index.css                       # Tailwind + design tokens + animations
├── lib/
│   ├── api/                        # Axios-based API clients
│   │   ├── client.ts               # Axios instance (auth interceptor, token refresh)
│   │   ├── auth.ts                 # signIn, signUp, signOut, me
│   │   ├── projects.ts             # Project CRUD + memory + costs
│   │   ├── chats.ts                # Chat CRUD + messages + prompts
│   │   ├── sources.ts              # Upload, URL, text, citations
│   │   ├── settings.ts             # API keys, databases, Google Drive
│   │   └── studio/                 # 18 feature-specific API modules
│   ├── auth/session.ts             # localStorage token management
│   ├── citations.ts                # [[cite:CHUNK_ID]] parsing
│   ├── logger.ts                   # Pino structured logging
│   └── utils.ts                    # Tailwind class merging (cn)
├── hooks/
│   ├── useAuth.tsx                 # Auth context (user, login, logout)
│   └── use-mobile.tsx              # Mobile breakpoint detection (768px)
└── components/
    ├── ui/                         # 50+ shadcn/ui primitives
    ├── auth/AuthPage.tsx           # Sign-in/sign-up (admin + user portals)
    ├── dashboard/                  # Dashboard + ProjectList + AppSettings
    ├── project/                    # ProjectWorkspace (3-panel orchestrator)
    ├── chat/                       # ChatPanel + ChatList + Messages + Input
    ├── sources/                    # SourcesPanel + AddSources + DriveImport
    ├── studio/                     # StudioPanel + 18 feature sections
    ├── settings/                   # Settings sections + team management
    └── brand/                      # Brand asset management
```

### 4.2 Routing

React Router v7 with two top-level routes:

```
/                       → Dashboard (project list, create project)
/projects/:projectId    → ProjectWorkspace (3-panel layout)
```

### 4.3 State Management

The frontend uses minimal, localized state — no global store library:

- **Auth Context** (`useAuth`): The only React Context. Provides user, login, signup, logout across the app.
- **Component-level `useState`**: All other state lives in component trees with intentional props drilling.
- **Version counter pattern**: Parent components expose `sourcesVersion` / `costsVersion` counters that child components watch via `useEffect` to trigger refetches.
- **Optimistic UI**: User messages appear immediately in the chat before the API responds.

### 4.4 API Client Architecture

A central Axios instance (`lib/api/client.ts`) handles:
- Automatic `Authorization: Bearer {token}` header injection
- 401 response interception with automatic token refresh
- Shared refresh promise to deduplicate concurrent 401 retries
- Query parameter fallback (`?token=`) for media elements that can't send headers

### 4.5 Design System

- **Icons**: Phosphor Icons (`@phosphor-icons/react`)
- **Colors**: Amber-600 primary (`#D97706`), Stone-800 text, warm cream background
- **Components**: shadcn/ui built on Radix UI primitives
- **Layout**: Resizable panels via `react-resizable-panels`
- **Charts**: Recharts for data visualization
- **Diagrams**: Mermaid for mind maps, XYFlow for flow diagrams, Excalidraw for wireframes

### 4.6 Key Frontend Components

**ProjectWorkspace** — The main 3-panel orchestrator. Manages layout state (collapsible panels), version counters for data refresh, per-chat source selection, and studio signal routing between ChatPanel and StudioPanel.

**ChatPanel** — Chat orchestrator. Handles active chat state, message sending with optimistic updates, citation display via `CitationBadge`, voice recording via `useVoiceRecording` hook (ElevenLabs WebSocket + AudioWorklet), and studio signal propagation.

**SourcesPanel** — Source management. Multi-tab source addition (file upload, URL, paste text, Google Drive, database), processing status tracking with polling, per-chat source selection toggles, and processed content viewer.

**StudioPanel** — Content generation hub. Uses `StudioContext` for shared state. 18 feature sections render conditionally based on studio signals from chat. Each section owns its own generation state and API calls.

---

## 5. Data Layer

### 5.1 Database Schema (PostgreSQL + Supabase)

```
users
  ├── id (UUID, PK)
  ├── email (unique)
  ├── role (admin | user)
  ├── memory (JSONB)              ← Global user memory
  ├── settings (JSONB)            ← User preferences
  ├── google_tokens (JSONB)       ← Google OAuth tokens
  └── created_at, updated_at

projects
  ├── id (UUID, PK)
  ├── user_id (FK → users)
  ├── name, description
  ├── custom_prompt (TEXT)         ← Optional per-project system prompt
  ├── memory (JSONB)              ← Project-specific memory
  ├── costs (JSONB)               ← API usage tracking by model
  └── created_at, updated_at, last_accessed

sources
  ├── id (UUID, PK)
  ├── project_id (FK → projects)
  ├── name, description
  ├── type (PDF|DOCX|PPTX|IMAGE|AUDIO|LINK|YOUTUBE|TEXT|CSV|DATABASE|RESEARCH)
  ├── status (uploaded → processing → embedding → ready | error | cancelled)
  ├── raw_file_path, processed_file_path  ← Supabase Storage paths
  ├── token_count, page_count, file_size
  ├── embedding_info (JSONB)      ← Pinecone metadata, chunk counts
  ├── summary_info (JSONB)        ← AI-generated summary
  ├── url                         ← For LINK/YOUTUBE types
  ├── is_active (BOOLEAN)         ← Included in RAG searches
  └── created_at, updated_at

chats
  ├── id (UUID, PK)
  ├── project_id (FK → projects)
  ├── title
  ├── selected_source_ids (UUID[]) ← Per-chat source selection
  └── created_at, updated_at

messages
  ├── id (UUID, PK)
  ├── chat_id (FK → chats)
  ├── role (user | assistant | tool_use | tool_result)
  ├── content (JSONB)             ← Text or structured content blocks
  ├── citations (TEXT[])          ← Referenced chunk IDs
  ├── model, tokens_input, tokens_output, cost_usd
  └── created_at

chunks
  ├── id (TEXT, PK)               ← Format: {source_id}_page_{N}_chunk_{M}
  ├── source_id (FK → sources)
  ├── content (TEXT)
  ├── page_number, chunk_number, token_count
  ├── embedding (vector(1536))    ← pgvector column (optional)
  └── created_at

studio_signals
  ├── id (UUID, PK)
  ├── chat_id, message_id (FK)
  ├── studio_item (ENUM)          ← audio_overview, video, mind_map, etc.
  ├── direction (TEXT)            ← AI instructions for generation
  ├── source_ids (UUID[])
  ├── status (pending | generating | ready | error | cancelled)
  └── output_path, error_message

background_tasks
  ├── id (UUID, PK)
  ├── target_id, target_type, task_type
  ├── status (pending | running | completed | failed | cancelled)
  ├── progress, message, error_message
  └── created_at, started_at, updated_at, completed_at

brand_config                      ← Workspace-level (per-user, not per-project)
  ├── id (UUID, PK)
  ├── user_id (FK → users, UNIQUE)
  ├── colors, typography, spacing, guidelines, voice (JSONB)
  └── created_at, updated_at

brand_assets                      ← Workspace-level (per-user)
  ├── id (UUID, PK)
  ├── user_id (FK → users)
  ├── name, asset_type, file_path
  └── created_at, updated_at

database_connections
  ├── id (UUID, PK)
  ├── owner_user_id (FK → users)
  ├── db_type (postgres | mysql)
  ├── connection_uri (encrypted)
  └── visible_to_all (BOOLEAN)

project_members                   ← Multi-user collaboration
  ├── project_id, user_id (composite PK)
  ├── role (owner | admin | member)
  └── can_edit, can_delete, can_invite
```

### 5.2 Row-Level Security (RLS)

All tables have RLS policies enforcing `user_id = auth.uid()`. Nested tables (messages, chunks) enforce access through joins to their parent chain (message → chat → project → user). A default user (`00000000-0000-0000-0000-000000000001`) is bootstrapped for single-user mode.

### 5.3 Storage Buckets (Supabase Storage / MinIO)

| Bucket | Purpose | Path Pattern |
|--------|---------|-------------|
| `raw-files` | Original uploaded files | `{user_id}/{project_id}/{source_id}/{filename}` |
| `processed-files` | Extracted text content | `{user_id}/{project_id}/{source_id}/{filename}.txt` |
| `chunks` | Text chunks for RAG | `{user_id}/{project_id}/{source_id}/chunks/` |
| `studio-outputs` | Generated content | `{user_id}/{project_id}/studio/{item_type}/{filename}` |
| `brand-assets` | Brand logos, icons, fonts | `{user_id}/brand/{asset_id}/{filename}` |

### 5.4 Vector Storage (Pinecone)

- **Index**: Named index with cosine similarity metric
- **Dimensions**: 1536 (OpenAI text-embedding-3-small)
- **Namespace**: One per project (isolates vectors)
- **Vector format**: `{id: chunk_id, values: [float...], metadata: {text, page, source_id}}`
- **Operations**: Upsert in batches of 100, top-k search (default k=5), delete by source_id

---

## 6. AI & LLM Integration Patterns

### 6.1 Claude API Wrapper

`claude_service.py` provides a thin singleton wrapper around the Anthropic SDK:

```python
send_message(
    messages,           # Conversation history
    system_prompt,      # Dynamic prompt with source context
    model,              # claude-sonnet-4-5-20250929 (default)
    max_tokens,         # From prompt config
    temperature,        # From prompt config
    tools,              # Tool definitions (JSON schemas)
    tool_choice,        # Optional: force specific tool
    extra_headers,      # Beta features (web_fetch)
    project_id          # Required for cost tracking
) → {content_blocks, model, usage, stop_reason}
```

All AI services go through this single entry point. Cost tracking is automatic — every call records input/output tokens against the project.

### 6.2 Two AI Patterns

**Pattern 1: Single-Call AI Services** (`ai_services/`)

Used for focused extraction or generation tasks. One Claude API call with forced tool use to get structured output.

Examples:
- **PDF extraction**: Send page images in batches of 5, force `submit_page_extraction` tool
- **Image extraction**: Single vision call with `submit_image_extraction` tool
- **Summary generation**: Send sampled chunks, get 150-200 token summary via Haiku
- **Chat naming**: Send first message, get 1-5 word title via Haiku
- **Memory merging**: Send existing + new memory, get merged memory via Haiku

**Pattern 2: Agentic Loops** (`ai_agents/`)

Used for complex, multi-step tasks. The agent loops until it calls a termination tool or hits max iterations.

```
Initialize messages + system prompt + tools
    │
    ▼
Call Claude API ────────────────────────┐
    │                                    │
    ▼                                    │
stop_reason == "tool_use"?               │
    │ Yes                                │
    ▼                                    │
Execute tool calls                       │
    │                                    │
    ▼                                    │
Is termination tool?                     │
    │ No                                 │
    ▼                                    │
Append tool_use + tool_result to messages│
    │                                    │
    └────────────────────────────────────┘
    │ Yes (or end_turn / max iterations)
    ▼
Return final result
```

Agent examples with their max iterations:
- **Web Agent** (8 iters): URL fetch with web_search/tavily fallback
- **Email Agent** (15 iters): Plan → generate images → write HTML
- **Blog Agent** (20 iters): Plan → generate images → write markdown
- **Website Agent** (30 iters): Plan → generate images → create/update files
- **Presentation Agent** (40 iters): Plan → create styles → add slides → finalize

### 6.3 Tool Types

Claude tools fall into three categories:

1. **Server Tools**: Claude itself executes the action (e.g., `web_fetch`, `web_search` via Anthropic's server-side tool execution with `extra_headers`)
2. **Client Tools**: The backend executes the tool and returns results (e.g., `search_sources`, `store_memory`, `tavily_search`)
3. **Termination Tools**: Signal that the agent loop should stop (e.g., `return_search_result` in web agent)

### 6.4 Cost Tracking

Every `claude_service.send_message()` call requires a `project_id`. Costs are calculated using model-specific pricing:

| Model | Input | Output |
|-------|-------|--------|
| Sonnet | $3/1M tokens | $15/1M tokens |
| Haiku | $1/1M tokens | $5/1M tokens |

Costs aggregate in the project's `costs` JSONB column and are displayed in the ProjectHeader.

---

## 7. RAG Pipeline

### 7.1 Ingestion Flow

```
Upload file / Add URL / Paste text
    │
    ▼
Store raw file in Supabase Storage
    │
    ▼
Status: "processing"
    │
    ▼
Type-specific processor extracts text
    │
    ▼
Add page markers: === TYPE PAGE N of M ===
    │
    ▼
Count tokens (tiktoken, cl100k_base)
    │
    ▼
Store processed text in Supabase Storage
    │
    ▼
token_count > 2500?
    │ Yes                     │ No
    ▼                         ▼
Status: "embedding"       Status: "ready"
    │                     (small enough for
    ▼                      full context)
Token-based chunking
(~200 tokens per chunk)
    │
    ▼
OpenAI embeddings
(text-embedding-3-small, 1536 dim)
    │
    ▼
Upsert to Pinecone
(batch of 100, project namespace)
    │
    ▼
Store chunks in Supabase Storage
    │
    ▼
Generate summary (Haiku, 150-200 tokens)
    │
    ▼
Status: "ready"
```

### 7.2 Chunk Format

All processed text uses standardized page markers:

```
=== PDF PAGE 1 of 10 ===
Content of page 1...

=== PDF PAGE 2 of 10 ===
Content of page 2...
```

Chunking splits on ~200 token boundaries (±20%), producing chunk IDs like `{source_id}_page_5_chunk_2`.

### 7.3 Search (Hybrid)

The `search_sources` tool uses a size-aware hybrid search strategy:

```
source.token_count < 1000?
    │ Yes                          │ No
    ▼                              ▼
Return ALL chunks              Parallel search:
(small enough to               ├─ Keyword search (difflib fuzzy matching)
read in full)                  └─ Semantic search (OpenAI embed → Pinecone top-k)
                                   │
                                   ▼
                               Combine & deduplicate by chunk_id
```

Claude receives chunk content + chunk_id in search results and uses chunk_ids for citations.

### 7.4 Chat Flow (Main RAG Loop)

```
User sends message
    │
    ▼
Store user message in DB
    │
    ▼
Build dynamic system prompt:
├─ Base prompt (from prompt config)
├─ Source context (names, types, summaries of active sources)
├─ User memory (global preferences)
├─ Project memory (project-specific context)
└─ Brand context (if configured)
    │
    ▼
Assemble available tools:
├─ search_sources (if non-CSV sources exist)
├─ store_memory (always)
├─ studio_signal (always)
├─ analyze_csv_agent (if CSV sources exist)
├─ analyze_database_agent (if DB sources exist)
└─ knowledge_base_tools (Jira, Notion if configured)
    │
    ▼
Tool use loop (max 10 iterations):
├─ Call Claude API
├─ If tool_use → execute tools → append results → loop
├─ If end_turn → extract text + citations → store → return
└─ If max_tokens → return partial response
    │
    ▼
Response with inline citations: [[cite:chunk_id]]
Frontend parses → CitationBadge → hover to fetch chunk content
```

### 7.5 Citation System

- **Format**: `[[cite:CHUNK_ID]]` where CHUNK_ID = `{source_id}_page_{N}_chunk_{M}`
- **API**: `GET /projects/{id}/citations/{chunk_id}` returns chunk content + metadata
- **Frontend**: Parses citations from response text, renders as numbered badges `[1]`, `[2]`, fetches content on hover for tooltip display
- **Export**: Converts to Markdown footnotes `[^1]` with citation content section

---

## 8. Source Processing Pipeline

### 8.1 Supported Source Types

| Type | Processor | AI Method | Pages |
|------|-----------|-----------|-------|
| PDF | `pdf_processor.py` → `pdf_service.py` | Batched vision (5 pages/batch, parallel ThreadPool) | Real pages |
| PPTX | `pptx_processor.py` → `pptx_service.py` | Same as PDF — slides rendered as images | Real slides |
| Image | `image_processor.py` → `image_service.py` | Single Claude vision call | 1 per image |
| URL | `link_processor.py` → `web_agent_service.py` | Agentic loop (web_fetch + tavily_search) | Single page |
| DOCX | `docx_processor.py` → `docx_utils.py` | No AI — python-docx extraction | Single page |
| Audio | `audio_processor.py` → ElevenLabs | No AI — Scribe v1 transcription | Single page |
| Text | `text_processor.py` | No AI — direct read | Single page |
| YouTube | `youtube_processor.py` → youtube-transcript-api | No AI — transcript API | Single page |
| CSV | `csv_processor.py` | No AI — pandas parsing | Single page |
| Database | `database_processor.py` | No AI — schema introspection | Single page |

### 8.2 Processing Design Decisions

- **Raw files preserved**: On error, the raw file remains in storage so users can retry without re-uploading.
- **Background processing**: All processing runs in background threads via `task_service` (ThreadPoolExecutor).
- **Cooperative cancellation**: Processors check `task_service.is_target_cancelled(source_id)` between batches.
- **Standardized output**: All processors use `build_processed_output()` for consistent file headers with metadata.

---

## 9. Studio Content Generation

Studio features are triggered by **studio signals** — structured messages emitted by Claude during chat that suggest content generation.

### 9.1 Signal Flow

```
User asks question in chat
    │
    ▼
Claude responds with text + calls studio_signal tool:
{studio_item: "presentation", direction: "Create a 10-slide deck on...", source_ids: [...]}
    │
    ▼
Signal stored in studio_signals table (status: "pending")
    │
    ▼
Frontend receives signal in chat response
    │
    ▼
StudioPanel renders corresponding section with generation button
    │
    ▼
User clicks "Generate" → triggers studio agent
    │
    ▼
Agent runs in background (agentic loop with specialized tools)
    │
    ▼
Output stored in studio-outputs bucket
    │
    ▼
Status: "ready" → frontend shows result with viewer/download
```

### 9.2 Available Studio Features

| Category | Features |
|----------|----------|
| Learning | Quiz, Flash Cards, Audio Overview, Mind Map |
| Business | Business Report, Marketing Strategy, PRD, Infographics, Flow Diagram, Wireframes, Presentation |
| Content | Blog, Social Posts, Website, Email Templates, Components, Ads Creative, Video |

Each feature has a dedicated backend agent, frontend section component, and API module.

---

## 10. Authentication & Multi-User

### 10.1 Auth Flow

1. User signs in/up via AuthPage (email + password)
2. Backend validates via Supabase Auth → returns JWT tokens
3. Frontend stores `access_token` and `refresh_token` in localStorage
4. Every API request includes `Authorization: Bearer {token}`
5. Backend middleware validates JWT on every request (skips `/auth/*`)
6. On 401, frontend auto-refreshes token and retries the request

### 10.2 Single-User vs Multi-User

**Single-user mode**: Uses Supabase `SERVICE_KEY` (bypasses RLS). A default admin user is bootstrapped from environment variables. Simpler setup for local development.

**Multi-user mode**: Uses `ANON_KEY` + RLS policies. Each user's data is isolated by `user_id = auth.uid()` policies. Supports team collaboration via `project_members` table with granular permissions (can_edit, can_delete, can_invite).

### 10.3 Voice Input

Real-time speech-to-text via ElevenLabs WebSocket:
1. Backend generates a single-use token (15-min expiry) — API key never leaves server
2. Frontend connects directly to ElevenLabs WebSocket
3. Audio captured via AudioWorklet (separate thread, no main thread blocking)
4. PCM audio converted to base64, sent as JSON messages
5. Partial transcripts displayed in real-time, committed text appended to chat input

---

## 11. Infrastructure & Deployment

### 11.1 Development Mode

```
bin/setup       → Create venv, install Python + Node deps, create .env
bin/dev         → Start Flask (5001) + Vite (5173) in parallel
```

Flask serves the API; Vite proxies `/api` requests to Flask and serves React with HMR.

### 11.2 Docker Production Mode

**19 containers** total, organized in two Docker Compose files:

**Supabase Stack** (`docker/supabase/docker-compose.yml`) — 16 containers:

| Container | Service | Port |
|-----------|---------|------|
| supabase-db | PostgreSQL 15 + pgvector | 5432 |
| supabase-kong | Kong API Gateway | 8000/8443 |
| supabase-auth | GoTrue (JWT auth) | 9999 |
| supabase-rest | PostgREST (auto API) | 3000 |
| supabase-realtime | WebSocket subscriptions | 4000 |
| supabase-storage | File storage API | 5000 |
| supabase-imgproxy | Image transformation | 5001 |
| supabase-meta | Schema introspection | 8080 |
| supabase-studio | Admin UI | 3001 |
| supabase-analytics | Logflare logging | 4000 |
| supabase-edge-functions | Serverless functions | — |
| supabase-vector | Log collection | — |
| supabase-pooler | Connection pooler (Supavisor) | 5432/6543 |
| supabase-minio | S3-compatible storage (macOS) | 9000/9001 |
| + 2 more | Support services | — |

**Application Stack** (`docker-compose.yml`) — 3 containers:

| Container | Service | Port |
|-----------|---------|------|
| noobbook-backend | Flask + SocketIO | 5001 |
| noobbook-frontend | Nginx + React build | 80 |
| noobbook-migrate | PostgreSQL migration runner | — |

All containers share the `noobbook-network` Docker network.

### 11.3 Nginx Configuration

- Serves React build from `/usr/share/nginx/html`
- Proxies `/api/` → `http://noobbook-backend:5001` (300s read timeout)
- Proxies `/socket.io/` → backend with WebSocket upgrade (24h timeout)
- SPA fallback: all non-file routes serve `index.html`
- 100MB client max body size for file uploads
- Gzip compression enabled

### 11.4 Migration System

The `noobbook-migrate` container runs on startup:
1. Checks for `schema_migrations` tracking table
2. If fresh DB: runs `init.sql` (combined schema)
3. If existing DB: runs only unapplied `migrations/*.sql` files
4. Records applied migrations to prevent re-runs
5. Exits with code 0 on success (backend `depends_on` this)

### 11.5 Backend Dockerfile

Multi-step build on Python 3.11 Slim:
1. Install system deps (LibreOffice, FFmpeg, Playwright Chromium)
2. Install Python packages
3. Stage prompt files to `/_prompts_staging`
4. Entrypoint seeds prompts non-destructively (doesn't overwrite user customizations)

### 11.6 Setup Script (`docker/setup.sh`)

Automated 11-step setup:
1. Verify Docker + Compose + Python3 prerequisites
2. Check port availability (80, 5001, 8000, 5432)
3. Generate all Supabase secrets (JWT, passwords, encryption keys)
4. Create `.env` files with generated values
5. Create Docker network
6. Start Supabase stack + wait for health
7. Create MinIO storage bucket (macOS xattr workaround)
8. Build and start NoobBook stack
9. Wait for migration completion

---

## 12. Key Design Patterns

### 12.1 Application Factory
Flask `create_app()` enables multiple app instances with different configs (dev, test, prod).

### 12.2 Singleton Services
External API clients (`claude_service`, `pinecone_service`, `openai_service`) are instantiated as module-level singletons with lazy initialization — clients aren't created until first use, preventing errors when optional API keys aren't set.

### 12.3 Forced Tool Use
PDF and PPTX extraction forces Claude to call a specific tool (`tool_choice: {type: "tool", name: "submit_page_extraction"}`), guaranteeing structured output rather than free-form text.

### 12.4 Token-Based Chunking
All source types produce text that's chunked into ~200 token segments using tiktoken (local, fast). This consistent chunk size enables effective embedding search regardless of source type.

### 12.5 Page Marker Format
A standardized `=== TYPE PAGE N of M ===` format is used across all processors, enabling consistent parsing and chunk ID generation.

### 12.6 Context Injection
System prompts are dynamically assembled per message: base prompt + source context (names, types, summaries) + user memory + project memory + brand context. This gives Claude awareness of available sources without including full content.

### 12.7 Non-Blocking Background Tasks
Memory merging, chat naming, source processing, and studio generation all run as background tasks via ThreadPoolExecutor. The main request returns immediately with a confirmation.

### 12.8 Cooperative Cancellation
Long-running processors check `task_service.is_target_cancelled()` between batches, allowing users to cancel source processing without killing threads.

### 12.9 Version Counter Pattern (Frontend)
Parent components maintain `sourcesVersion` / `costsVersion` counters. Children watch via `useEffect` and refetch data when the counter increments. Simple alternative to global state management.

### 12.10 Hybrid Search
Source search combines keyword matching (difflib fuzzy) with semantic search (OpenAI embedding → Pinecone) and deduplicates results by chunk_id. Small sources (< 1000 tokens) skip search entirely and return all chunks.
