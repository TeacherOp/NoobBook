# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

### macOS / Linux (Recommended)
```bash
# First time setup (creates venv, installs all dependencies)
bin/setup

# Run both backend and frontend
bin/dev

# Options
bin/dev --backend-only    # Only Flask server (http://localhost:5001)
bin/dev --frontend-only   # Only Vite server (http://localhost:5173)
bin/dev --install         # Update deps before starting
```

### Windows
```bash
# First time setup
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

cd ../frontend
npm install

# Run both servers
python start.py

# Stop servers
python stop.py
```

### Other Commands
```bash
npm run build                  # Production build (frontend)
npm run lint                   # ESLint (frontend)
```

### System Dependencies (Required)
```bash
# macOS
brew install libreoffice ffmpeg
npx playwright install

# Ubuntu/Debian
sudo apt install libreoffice ffmpeg
npx playwright install
```

### Testing
```bash
# Backend tests
cd backend && pytest

# Single test file
pytest tests/test_sources.py

# Single test
pytest tests/test_sources.py::test_upload_pdf -v
```

### Environment Variables
Create `backend/.env` with:
```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...

# Optional
ELEVENLABS_API_KEY=...          # Audio features
TAVILY_API_KEY=...              # Web search fallback
GOOGLE_CLIENT_ID=...            # Google Drive import
GOOGLE_CLIENT_SECRET=...
ANTHROPIC_TIER=1                # 1-4, controls rate limits
```

### Claude Model
Always use `claude-sonnet-4-5-20250929` as the default model for Claude API calls.

## PROJECT PURPOSE

**NoobBook is an open-source NotebookLM alternative. NotebookLM, but smarter.**

Website: [noobbooklm.com](https://noobbooklm.com)

### What We Focus On
- LLM API integration patterns (Claude, OpenAI, etc.)
- Prompt engineering and system prompt design
- Tool use and agentic loops
- RAG (Retrieval Augmented Generation) with embeddings
- Multi-modal AI (vision, audio transcription, text-to-speech)
- Studio content generation (audio, video, documents, design)

### Current Scope
- JSON file storage (no database)
- Single-user local deployment
- API key management via UI

### Code Philosophy
- Keep it simple and readable
- Add comments explaining LLM concepts where helpful
- Each service should have a clear, single purpose
- Avoid over-engineering

## IMPORTANT RULES TO FOLLOW

### Code Quality & Structure
- Follow DRY — extract repeated logic into reusable functions/components - Think of this as the learning session will be attended by the Founder of Python! He should be amazed not disgusted
- Keep code modular — one component/function per file when it exceeds 100 lines
- Prefer composition over inheritance in React components

### Frontend Rules (React + Vite + shadcn + Tailwind)
- **Always check shadcn/ui first** — before creating custom components, search if shadcn already provides it
- Use shadcn components via: `npx shadcn@latest add [component-name]`
- Tailwind for all styling — no inline styles or separate CSS files unless absolutely necessary
- Toast notifications use the custom hook from `./ui/toast` (not `../hooks/use-toast`)

### Design System
- **Icons**: Use Phosphor Icons (`@phosphor-icons/react`) — NOT Lucide React
- **Colors**: Amber-600 primary (`#D97706`), Stone-800 text, warm cream background
- **Full spec**: See `frontend/DESIGN_SYSTEM.md` for complete reference

### Backend Rules (Python Flask)
- Follow PEP 8 style guidelines
- Use type hints for all function parameters and return values
- Organize routes in blueprints when they exceed 5 endpoints

### Documentation & Comments
- **Add explanatory comments** for LLM-related code — explain WHY, not just WHAT
- Document agent architectures and prompt engineering decisions
- Add docstrings to Python functions and classes

### When In Doubt — ASK
- If approach is unclear, ask before implementing

## Project Overview

NoobBook - An open-source NotebookLM alternative. Full-stack web application with React frontend and Flask backend.

## Application Views

The application has exactly **two core views**:

### View 1: Dashboard
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  NoobBook                                             [ App Settings ]      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────┐    ┌─────────────────────┐                       │
│   │         +           │    │  Project Name       │                       │
│   │                     │    │  Description...     │                       │
│   │  Create New Project │    │                     │                       │
│   │                     │    │  Last opened: date  │                       │
│   └─────────────────────┘    └─────────────────────┘                       │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  Session 3: The Complete AI Tool     │  Previous Sessions & Resources      │
│                                       │                                     │
│  Tags: AI Chat, RAG, Image Gen,      │  - Session 1: API Basics            │
│  Video Gen, Realtime Transcription,  │  - Session 2: Chat, Memory & Agents │
│  Memories, Subagents, Web Search     │  - Course Code Repository           │
└─────────────────────────────────────────────────────────────────────────────┘
```
**Purpose**: Project management (create, open, delete projects) + course learning resources

### View 2: Project Workspace (3-Panel Layout)
```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  ← Project Name                        [ Memory ] [ Project Settings ] [ + New ]     │
├───────────────────┬─────────────────────────────────────┬────────────────────────────┤
│  SOURCES          │  CHAT                               │  STUDIO                    │
│                   │                                     │                            │
│  [Search...]      │  Chat Name ▼               [8/8]   │  Generate content from     │
│  [+ Add sources]  │  Ask questions about sources...     │  your sources              │
│                   │                                     │                            │
│  ┌─────────────┐  │  ┌─────────────────────────────┐   │  DOCUMENTS                 │
│  │ 📄 PDF      │  │  │ User: "question here?"      │   │  • Generate Presentation   │
│  │ 🖼️ Image    │  │  └─────────────────────────────┘   │  • Generate PRD / Docs     │
│  │ 🎵 Audio    │  │                                     │  • Generate To-Do List     │
│  │ 🔗 Link     │  │  ┌─────────────────────────────┐   │                            │
│  │ 📺 YouTube  │  │  │ NoobBook:                   │   │  COMMUNICATION             │
│  └─────────────┘  │  │ Response with citations¹²³  │   │  • Draft Team Email        │
│                   │  └─────────────────────────────┘   │  • Draft Stakeholder Email │
│                   │                                     │                            │
│  8/100 sources    │  [🎤] Ask about your sources...    │  MEDIA                     │
│  5.2 MB total     │                                     │  • Audio Overview          │
│                   │  Click mic to speak, or type       │  • Video Overview          │
│                   │                                     │                            │
│                   │                                     │  ANALYSIS                  │
│                   │                                     │  • Generate Mind Map       │
└───────────────────┴─────────────────────────────────────┴────────────────────────────┘
```
**Purpose**: Where all AI features live
- **Sources Panel**: Multi-modal ingestion (PDF, DOCX, PPTX, images, audio, YouTube, URLs)
- **Chat Panel**: RAG-based Q&A with citations, voice input, conversation history
- **Studio Panel**: Content generation features (planned)

### Data Structure
```
data/
├── user_memory.json              # Global user memory (persists across all projects)
├── google_tokens.json            # Google OAuth tokens (auto-created on connect)
├── prompts/
│   ├── default_prompt.json           # Global default system prompt
│   ├── pdf_extraction_prompt.json    # PDF extraction prompt config
│   ├── pptx_extraction_prompt.json   # PowerPoint extraction prompt config
│   ├── image_extraction_prompt.json  # Image extraction prompt config
│   ├── web_agent_prompt.json         # Web agent system prompt
│   ├── summary_prompt.json           # Source summary generation prompt
│   ├── memory_prompt.json            # Memory merge prompt config
│   └── chat_naming_prompt.json       # Chat title generation prompt
├── tasks/
│   └── tasks_index.json              # Background task tracking
└── projects/
    ├── {project_id}.json
    └── {project_id}/
        ├── memory.json               # Project-specific memory (deleted with project)
        ├── sources/
        │   ├── sources_index.json    # Source metadata index (includes embedding_info, summary_info)
        │   ├── raw/                  # Original uploaded files
        │   │   ├── {file}.pdf
        │   │   ├── {file}.docx
        │   │   ├── {file}.pptx
        │   │   ├── {file}.mp3        # Audio files (mp3, wav, m4a, etc.)
        │   │   ├── {file}.png        # Image files (png, jpg, jpeg, webp)
        │   │   ├── {name}.link       # URL sources (JSON with url, type)
        │   │   └── {name}.txt        # Pasted text sources
        │   ├── processed/            # Extracted/processed content
        │   │   └── {source_id}.txt   # Extracted text with page markers
        │   └── chunks/               # Chunked text for RAG (one folder per source)
        │       └── {source_id}/
        │           ├── {source_id}_chunk_1.txt
        │           ├── {source_id}_chunk_2.txt
        │           └── ...           # Each chunk has metadata header + text
        ├── agents/                   # Agent execution logs
        │   └── web_agent/
        │       └── {execution_id}.json  # Full message chain + result for debudding purposes only
        └── chats/
            ├── chats_index.json
            ├── {chat_id}.json
            ├── api_1.json            # Debug log for 1st API call in chat for debudding purposes only
            ├── api_2.json            # Debug log for 2nd API call (tool follow-up) for debudding purposes only
            └── ...                   # Incrementing logs for each API call for debudding purposes only

app/services/tools/               # Tool definitions (JSON schemas)
├── chat_tools/
│   ├── source_search_tool.json   # search_sources tool for main chat RAG
│   └── memory_tool.json          # store_memory tool for user/project memory
├── pdf_tools/
│   └── pdf_extraction.json       # submit_page_extraction tool
├── pptx_tools/
│   └── pptx_extraction.json      # submit_slide_extraction tool
├── image_tools/
│   └── image_extraction.json     # submit_image_extraction tool
└── web_agent/
    ├── web_search.json           # Claude server tool (web_search_20250305)
    ├── web_fetch.json            # Claude server tool (web_fetch_20250910, beta)
    ├── tavily_search.json        # Custom tool for Tavily API fallback
    └── return_search_result.json # Termination tool for agent completion
```

### API Endpoints
Base URL: `http://localhost:5001/api/v1`

**Projects**: GET/POST `/projects`, GET/PUT/DELETE `/projects/{id}`, GET `/projects/{id}/costs`, GET `/projects/{id}/memory`

**Chats**:
- `GET/POST /projects/{id}/chats` - List/create chats
- `GET/PUT/DELETE /projects/{id}/chats/{chat_id}` - Chat operations
- `POST /projects/{id}/chats/{chat_id}/messages` - Send message (calls Claude API)
- `GET /projects/{id}/prompt` - Get project's system prompt
- `GET /prompts/default` - Get global default prompt

**Sources**:
- `GET /projects/{id}/sources` - List all sources
- `POST /projects/{id}/sources` - Upload file (multipart/form-data)
- `POST /projects/{id}/sources/url` - Add URL source
- `POST /projects/{id}/sources/text` - Add pasted text source
- `PUT /projects/{id}/sources/{source_id}` - Update source (name, description, active)
- `DELETE /projects/{id}/sources/{source_id}` - Delete source
- `POST /projects/{id}/sources/{source_id}/cancel` - Cancel processing
- `POST /projects/{id}/sources/{source_id}/retry` - Retry/start processing

**Settings**: `GET/POST /settings/api-keys`, `DELETE /settings/api-keys/{id}`, `POST /settings/api-keys/validate`

**Google Drive**:
- `GET /google/status` - Check if configured and connected
- `GET /google/auth` - Get OAuth authorization URL
- `GET /google/callback` - Handle OAuth callback (redirects to frontend)
- `POST /google/disconnect` - Remove stored tokens
- `GET /google/files` - List files (supports `folder_id`, `page_size`, `page_token`)
- `POST /projects/{id}/sources/google-import` - Import file to sources

**Transcription**:
- `GET /transcription/config` - Get ElevenLabs WebSocket URL with single-use token
- `GET /transcription/status` - Check if ElevenLabs is configured

## Google Drive Integration

Import files from Google Drive. OAuth 2.0 flow with `drive.readonly` scope. Tokens stored in `data/google_tokens.json`, auto-refresh on expiry. Google Workspace exports: Docs→DOCX, Sheets→CSV, Slides→PPTX.

**Setup**: Create OAuth credentials in Google Cloud Console, add redirect URI `http://localhost:5001/api/v1/google/callback`.

## Voice Input (ElevenLabs)

Real-time speech-to-text via ElevenLabs WebSocket. Backend generates single-use tokens (15 min expiry), frontend connects directly. Audio captured via AudioWorklet, converted to 16-bit PCM base64. API key stays server-side.

## Source Processing Pipeline

Status flow: `uploaded → processing → [embedding] → ready` (embedding only if token count > 2500).

### Processed Output Format

All processors use `build_processed_output()` from `app/utils/text/processed_output.py` for consistent output format:

```
# Extracted from {TYPE} document: {source_name}
# Type: {TYPE}
# Total pages: {N}
# Processed at: {timestamp}
# {metadata_key}: {value}
# ...
# token_count: {count or "200k+"}
# ---

=== {TYPE} PAGE 1 of N ===

{page content}

=== {TYPE} PAGE 2 of N ===

{page content}
```

**Key Design Decisions:**
- **Sources with logical pages** (PDF, PPTX, Image batch): Preserve real page/slide structure
- **Sources without logical pages** (TEXT, DOCX, AUDIO, LINK, YOUTUBE): Single page marker `=== TYPE PAGE 1 of 1 ===`
- **Token-based chunking** handles all splitting for embeddings (~200 tokens per chunk)
- Each page extraction is **self-contained** with context from surrounding pages included

### Page Markers
All extracted content uses page markers: `=== {TYPE} PAGE 1 of N ===`
Types: PDF, TEXT, DOCX, PPTX, AUDIO, IMAGE, LINK, YOUTUBE

### Source Types & AI Patterns

| Type | Service | AI Method | Pages |
|------|---------|-----------|-------|
| **PDF** | `ai_services/pdf_service.py` | Batched vision extraction (5 pages/batch, parallel ThreadPool). `submit_page_extraction` tool. | Real pages |
| **PPTX** | `ai_services/pptx_service.py` | Same pattern as PDF - slides as images in batches, `submit_slide_extraction` tool. | Real slides |
| **Image** | `ai_services/image_service.py` | Single Claude vision call with `submit_image_extraction` tool. | 1 per image |
| **URL** | `ai_agents/web_agent_service.py` | Agentic loop with `web_fetch`, `tavily_search` tools. | Single page |
| **DOCX** | `utils/docx_utils.py` | No AI - python-docx extraction | Single page |
| **Audio** | `integrations/elevenlabs/audio_service.py` | No AI - ElevenLabs Scribe v1 transcription | Single page |
| **Text** | `source_processing_service.py` | No AI - direct file read | Single page |
| **YouTube** | `integrations/youtube/youtube_service.py` | No AI - youtube-transcript-api | Single page |

**Design**: Raw files preserved on error (retry without re-upload). Processing runs in background threads. Tool-based extraction ensures structured output.

### Text Utilities (`app/utils/text/`)

Modular text processing for the RAG pipeline:

| Module | Purpose |
|--------|---------|
| `cleaning.py` | Text cleaning for embeddings (normalize whitespace, remove noise) |
| `page_markers.py` | Standardized page marker format and regex patterns |
| `processed_output.py` | `build_processed_output()` for consistent file headers |
| `chunking.py` | Token-based chunking (~200 tokens) for embeddings |

**Note**: `splitting.py` was removed - artificial page splitting is no longer used. Token-based chunking handles all splitting for embeddings.

### Token Counting (Hybrid Approach)

Token counting uses **tiktoken** (local) for speed, with Claude API available for exact counts when needed.

**Why tiktoken?** Chunking calls `count_tokens()` thousands of times (per page, per sentence, per word for long sentences). API calls would take minutes due to network latency. tiktoken is local and instant.

```python
# embedding_utils.py
count_tokens(text)      # Uses tiktoken (fast, local) - for chunking operations
count_tokens_api(text)  # Uses Claude API (accurate, slower) - for billing/quota
```

tiktoken uses `cl100k_base` encoding which closely matches Claude's tokenizer (within ~5% accuracy - good enough for chunking).

## Web Agent Architecture

**Agentic loop pattern** for URL content extraction. Loop: Claude calls tools → execute → return result → repeat until termination.

**Tool Types**:
- **Server Tools**: Claude handles execution (web_fetch, web_search) - results come in response
- **Client Tools**: We execute via `web_agent_executor.py` (tavily_search)
- **Termination Tool**: `return_search_result` signals completion

Execution logs saved to `data/projects/{id}/agents/web_agent/{execution_id}.json` for debugging.

## Source Summaries

AI-generated summaries (150-200 tokens via Haiku) help chat AI understand documents at a glance. Summaries included in system prompt via `context_loader.py`. For large sources, samples 8 evenly distributed chunks.

## Chat Auto-Naming

Background task generates 1-5 word title via Haiku after first message. Non-blocking - chat response returns immediately. Manual rename available via ChatList UI.

## Main Chat Architecture

**RAG agentic loop** for source-aware conversations. System prompt includes dynamic source context + memory via `context_loader.py`.

### Tool Use Loop
```
User message → Claude API (with search_sources, store_memory tools)
    ↓
tool_use? → Yes: Execute tool → Store tool_use + tool_result → Loop back
          → No:  Store final text → Return to user
```

### Source Search (Hybrid Search)

The `search_sources` tool uses a smart hybrid search strategy based on source size:

**Tool Schema** (`source_search_tool.json`):
```json
{
  "source_id": "required - the source to search (from available sources)",
  "keywords": ["optional", "array"],  // 1-2 word terms for local text search
  "query": "optional string"           // semantic search phrase for Pinecone
}
```

**Search Strategy** (`source_search_executor.py`):
```
if source.token_count < 1000:
    → Return ALL chunks (no search needed)
else:
    → Local keyword search (fuzzy matching via difflib)
    → Semantic search (OpenAI embedding → Pinecone)
    → Combine & dedupe by chunk_id
```

**Key Point**: Claude passes `source_id` to search, but receives `chunk_id` in results. Citations must use `chunk_id`, NOT `source_id`.

### Chunk-Based Citations

Citations use chunk_ids for precise references to specific content sections.

**Citation Format**: `[[cite:CHUNK_ID]]`
**Chunk ID Format**: `{source_id}_page_{page}_chunk_{n}`
**Example**: `[[cite:abc123-def456_page_5_chunk_2]]`

**API Endpoint**: `GET /projects/{id}/citations/{chunk_id}`
Returns chunk content for tooltip/popover display.

**Flow**:
```
Claude response: "Information here [[cite:abc123_page_5_chunk_2]]"
       ↓
Frontend parses → extracts chunk_id
       ↓
Hover → GET /api/v1/projects/{id}/citations/{chunk_id}
       ↓
Backend loads chunk file → returns content + metadata
       ↓
Tooltip shows: "Source Name - Page 5, Section 2" + content
```

### Debug Logging
Each API call logged to `data/projects/{id}/chats/{chat_id}/api_N.json` with full request/response for debugging.

## Claude API Response Parsing

Centralized parsing via `utils/claude_parsing_utils.py`. Clean separation of concerns:

```
claude_service.py (API call) → returns raw {content_blocks, stop_reason, usage, model}
         ↓
claude_parsing_utils.py (parse response)
   - is_tool_use(response) / is_end_turn(response)
   - extract_text(response)
   - extract_tool_use_blocks(response)
   - build_tool_result_content(results)
   - serialize_content_blocks(blocks)
         ↓
message_service.py (store if needed - pure CRUD)
```

**Tool use flow**: `stop_reason: "tool_use"` → extract tool_use blocks → execute → build tool_result content → send back with matching IDs.

## Cost Tracking

Per-project API cost tracking. Pricing: Sonnet ($3/$15 per 1M in/out), Haiku ($1/$5). All services pass `project_id` to `claude_service.send_message()`. Costs stored in `project.json`, displayed in ProjectHeader with tooltip breakdown.

## Memory System

**Tool-based memory** for persistent context across conversations.

- **User Memory** (`data/user_memory.json`): Global preferences across all projects
- **Project Memory** (`data/projects/{id}/memory.json`): Project-specific context

**Flow**: Claude calls `store_memory` → returns immediately (non-blocking) → background task uses Haiku to merge new + existing memory (max 150 tokens) → saved to JSON → included in future system prompts via `context_loader.py`.

## Tier Configuration

Centralized rate limiting in `app/config/tier_loader.py`. Set via `ANTHROPIC_TIER` in .env (1-4).

| Tier | Workers | Pages/min | Use Case |
|------|---------|-----------|----------|
| 1 | 4 | 10 | Free tier |
| 2 | 16 | 100 | Standard |
| 3 | 24 | 200 | Pro |
| 4 | 80 | 1500 | Enterprise/Demos |

**Tier 4 Optimization**: Workers can be high (80) because PDF/PPTX processing is I/O-bound (waiting for API), not CPU-bound. The 4000 RPM limit with 5-page batches theoretically supports ~20,000 pages/min, but output token limits (~800K/min) cap practical throughput.

## AI Service Standard Pattern

All AI services (`ai_services/`), AI agents (`ai_agents/`), and tool executors (`tool_executors/`) must follow this standardized pattern for consistency and maintainability.

### Required Steps (Mandatory)

```
1. CONFIGURATION LOADING
   ├── prompt_loader.get_prompt_config("service_name")  # System prompt, model, temperature, max_tokens
   ├── tool_loader.load_tool("category", "tool_name")   # Tool definitions (if using tools)
   └── get_anthropic_config()                           # Tier config (workers, rate limits)

2. PATH MANAGEMENT
   └── path_utils.get_*_dir(project_id)                 # Use path_utils for ALL directory access
       ├── get_processed_dir()     # For output files
       ├── get_raw_dir()           # For input files
       ├── get_chunks_dir()        # For chunked text
       └── get_chats_dir()         # For chat files

3. API CALL
   └── claude_service.send_message(                     # Thin wrapper, returns raw response
           messages, system_prompt, model,
           max_tokens, temperature, tools,
           tool_choice, project_id                      # project_id required for cost tracking
       )

4. RESPONSE PARSING
   └── claude_parsing_utils.*                           # Centralized parsing utilities
       ├── is_tool_use(response)                        # Check if tool was called
       ├── is_end_turn(response)                        # Check if conversation ended
       ├── extract_text(response)                       # Get text content
       ├── extract_tool_use_blocks(response)            # Get tool call details
       ├── extract_tool_inputs(response, tool_name)     # Get inputs for specific tool
       └── build_tool_result_content(results)           # Build tool result message
```

### Optional Steps (As Needed)

```
FOR BATCHED PROCESSING (PDF, PPTX):
├── batching_utils.create_batches(items, DEFAULT_BATCH_SIZE)
├── batching_utils.get_batch_info(items, batch_size)
└── DEFAULT_BATCH_SIZE = 5                              # Standard batch size

FOR RATE-LIMITED APIs:
├── rate_limit_utils.RateLimiter(requests_per_minute)
└── rate_limiter.wait_if_needed()                       # Call before each API request

FOR PARALLEL PROCESSING:
├── ThreadPoolExecutor(max_workers=tier_config["max_workers"])
├── task_service.is_target_cancelled(source_id)         # Check for user cancellation
└── Cooperative cancellation pattern                    # Raise CancelledException

FOR BINARY DATA:
└── encoding_utils.encode_bytes_to_base64(data)         # Base64 encoding for API

FOR FILE-TYPE SPECIFIC:
├── pdf_utils.get_page_count(), get_all_page_bytes()    # PDF operations
├── docx_utils.extract_text()                           # DOCX extraction
└── pptx_utils.convert_to_pdf()                         # PPTX to PDF conversion
```

### Service Template

```python
"""
Service Name - Brief description of what this service does.
"""
from app.config import prompt_loader, tool_loader, get_anthropic_config
from app.services.integrations.claude import claude_service
from app.utils import claude_parsing_utils
from app.utils.path_utils import get_processed_dir
from app.utils.rate_limit_utils import RateLimiter  # If rate limiting needed
from app.utils.batching_utils import create_batches, DEFAULT_BATCH_SIZE  # If batching needed
from app.services.data_services import message_service # if message storage required


class ServiceName:
    def __init__(self):
        self._tool_definition = None  # Lazy load tools

    def _load_tool_definition(self):
        if self._tool_definition is None:
            self._tool_definition = tool_loader.load_tool("category", "tool_name")
        return self._tool_definition

    def process(self, project_id: str, ...) -> Dict[str, Any]:
        # 1. Load configurations
        prompt_config = prompt_loader.get_prompt_config("service_name")
        tool_def = self._load_tool_definition()
        tier_config = get_anthropic_config()

        # 2. Create rate limiter (if needed)
        rate_limiter = RateLimiter(tier_config["pages_per_minute"])

        # 3. Get paths
        output_dir = get_processed_dir(project_id)

        # 4. Process with rate limiting
        rate_limiter.wait_if_needed()
        response = claude_service.send_message(
            messages=messages,
            system_prompt=prompt_config["system_prompt"],
            model=prompt_config["model"],
            max_tokens=prompt_config["max_tokens"],
            temperature=prompt_config["temperature"],
            tools=[tool_def],
            project_id=project_id
        )

        # 5. Parse response
        tool_inputs = claude_parsing_utils.extract_tool_inputs(response, "tool_name")

        return {"success": True, "data": tool_inputs}


# Singleton instance
service_name = ServiceName()
```

### What NOT to Do

- **Never** duplicate configuration loading logic - use `prompt_loader`, `tool_loader`, `tier_loader`
- **Never** hardcode paths - use `path_utils` functions
- **Never** parse Claude responses manually - use `claude_parsing_utils`
- **Never** implement custom rate limiting - use `RateLimiter` class
- **Never** implement custom batching - use `create_batches()` utility
- **Never** skip `project_id` in API calls - needed for cost tracking
