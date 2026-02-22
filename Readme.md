# NoobBook

This is my cloned version of NoobBook.

<p align="center">
  <img src="assets/noob_book.png" alt="NoobBook Logo" width="120">
</p>

<p align="center">
  <strong>NotebookLM, but smarter.</strong>
</p>

<p align="center">
  An open-source NotebookLM alternative. Free to use, fork, and self-host.
</p>

<p align="center">
  <a href="https://noobbooklm.com">noobbooklm.com</a>
</p>

---

### First Believer & Primary Sponsor

<p align="center">
  <a href="https://www.delta.exchange">
    <img src="assets/delta_exchange.svg" alt="Delta Exchange" width="300">
  </a>
</p>

<p align="center">
  <em>Thank you Delta Exchange for believing in NoobBook from day one.</em>
</p>

<p align="center">
  <a href="SPONSORS.md">Want to sponsor? See how</a>
</p>

---

### Special Thanks

<p align="center">
  <a href="https://www.growthx.club">
    <img src="assets/growthxlogo.jpeg" alt="GrowthX" width="80">
  </a>
</p>

<p align="center">
  <em>GrowthX - The community that helped shape this journey.</em>
</p>

**Built with:**
[Claude](https://anthropic.com) & [Claude Code](https://claude.ai/code) |
[OpenAI](https://openai.com) |
[ElevenLabs](https://elevenlabs.io) |
[Pinecone](https://pinecone.io) |
[Tavily](https://tavily.com) |
[Google AI](https://ai.google)

**Powered by open-source:**
[React](https://react.dev) |
[Vite](https://vitejs.dev) |
[Flask](https://flask.palletsprojects.com) |
[shadcn/ui](https://ui.shadcn.com) |
[Tailwind CSS](https://tailwindcss.com) |
[Radix UI](https://radix-ui.com)

---

## Table of Contents

- [What is NoobBook?](#what-is-noobbook)
- [How It Works](#how-it-works)
  - [Projects](#1-projects)
  - [Sources](#2-sources-left-panel)
  - [Chat](#3-chat-center-panel)
  - [Studio](#4-studio-right-panel)
- [Architecture](#architecture)
- [Getting Started (Docker Setup)](#getting-started-docker-setup)
  - [Prerequisites](#prerequisites)
  - [API Keys](#api-keys)
  - [Step 1: Clone and Configure](#step-1-clone-and-configure)
  - [Step 2: Set Up Auth](#step-2-set-up-auth-required)
  - [Step 3: Run Setup](#step-3-run-setup)
  - [Step 4: Log In](#step-4-log-in)
  - [Auth & Roles (RBAC)](#auth--roles-rbac)
  - [Managing Your Setup](#managing-your-setup)
- [Local Development](#option-b-local-development)
- [Tech Stack](#tech-stack)
- [Contributing](#contributing)
- [License](#license)

---

## What is NoobBook?

NoobBook is a fully-featured NotebookLM alternative that you can run yourself. Upload documents, chat with your sources using RAG, and generate content with AI agents.

**Core Features:**
- Multi-modal source ingestion (PDF, DOCX, PPTX, images, audio, YouTube, URLs)
- RAG-powered chat with citations
- AI-generated content (audio overviews, mind maps, presentations, and more)
- Memory system for personalized responses
- Voice input and text-to-speech

---

## How It Works

NoobBook has 4 main concepts:

### 1. Projects

Everything is organized into projects. Each project has its own sources, chats, and studio outputs.

### 2. Sources (Left Panel)

Upload documents and the system processes them for AI understanding:

| Source Type | Processing |
|-------------|------------|
| PDF | AI vision extracts text page by page |
| DOCX | Python extraction |
| PPTX | Convert to PDF, then vision extraction |
| Images | AI vision describes content |
| Audio | ElevenLabs transcription |
| YouTube | Transcript API |
| URLs | Web agent fetches and extracts content |
| Text | Direct input |

**Processing Pipeline:**
```
Upload -> Raw file saved -> AI extracts text -> Chunked for RAG -> Embedded in Pinecone
```

### 3. Chat (Center Panel)

RAG-powered Q&A with your sources:

```
User question
    -> AI searches relevant sources (hybrid: keyword + semantic)
    -> AI generates response with citations
    -> Citations link to specific chunks
```

**Key features:**
- Chunk-based citations
- Memory system (user preferences + project context)
- Voice input via ElevenLabs
- Conversation history per chat

### 4. Studio (Right Panel)

Generate content from your sources using AI agents:

| Category | Studio Items |
|----------|--------------|
| **Audio/Video** | Audio Overview, Video Generation |
| **Learning** | Flash Cards, Mind Maps, Quizzes |
| **Documents** | PRD, Blog Posts, Business Reports, Presentations |
| **Marketing** | Ad Creatives, Social Posts, Email Templates |
| **Design** | Websites, Components, Wireframes, Flow Diagrams |

---

## Architecture

```
Frontend (React + Vite)
    |
    v
Backend API (Flask + SocketIO)
    |
    ├── Source Processing (upload, extract, chunk, embed)
    ├── Chat Service (RAG search, Claude API, citations)
    ├── Studio Services (content generation agents)
    └── Integrations (Claude, OpenAI, Pinecone, ElevenLabs, Gemini)
    |
    v
Supabase (PostgreSQL + S3 Storage + Auth)
```

**AI Services:**
- **Claude** - Main LLM for chat, agents, content generation
- **OpenAI** - Embeddings for vector search
- **Pinecone** - Vector database for RAG
- **ElevenLabs** - Text-to-speech and transcription
- **Gemini** - Image generation
- **Google Veo** - Video generation

---

## Getting Started (Docker Setup)

Docker is the recommended way to run NoobBook. One script starts everything — Supabase, PostgreSQL, database migrations, backend, and frontend (16 containers total).

### Prerequisites

Before you begin, make sure you have:

| Requirement | Install | Check |
|-------------|---------|-------|
| **Docker Desktop** | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) | `docker info` |
| **Docker Compose v2** | Included with Docker Desktop | `docker compose version` |
| **Python 3** | `brew install python3` (macOS) / `sudo apt install python3` (Ubuntu) | `python3 --version` |

> **Important:** Docker Desktop must be **running** (not just installed). Open it from your Applications before running setup.

**Ports required (must be free):**

| Port | Used by |
|------|---------|
| `80` | NoobBook frontend |
| `5001` | NoobBook backend API |
| `8000` | Supabase API gateway |
| `5432` | PostgreSQL |

The setup script checks these automatically and will tell you if something is already using a port.

### API Keys

Get these before running setup:

| Key | Where to get it | Required? |
|-----|-----------------|-----------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) | Yes |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/) | Yes |
| `PINECONE_API_KEY` + `PINECONE_INDEX_NAME` | [pinecone.io](https://www.pinecone.io/) | Yes |
| `ELEVENLABS_API_KEY` | [elevenlabs.io](https://elevenlabs.io/) | No — audio features |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com/) | No — web search fallback |
| `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` | [Google Cloud Console](https://console.cloud.google.com/) | No — Google Drive import |
| `JIRA_CLOUD_ID` (or `JIRA_DOMAIN`) + `JIRA_EMAIL` + `JIRA_API_KEY` | [Jira Settings → Security → API tokens](https://id.atlassian.com/manage-profile/security/api-tokens) | No — Jira integration |
| `NOTION_API_KEY` | [Notion Integrations](https://www.notion.so/my-integrations) | No — Notion integration |

---

### Step 1: Clone and Configure

```bash
# Clone the repo
git clone https://github.com/TeacherOp/NoobBook.git
cd NoobBook
git checkout develop

# Copy env template
cp docker/.env.example docker/.env
```

Edit `docker/.env` and add your API keys:
```bash
nano docker/.env
```

At minimum, fill in these four:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...
```

### Step 2: Set Up Auth (Required)

Auth is **enabled by default**. You need to configure an admin account before running setup.

In `docker/.env`, set your admin credentials:
```bash
# Admin email(s) — these users get admin role on signup
NOOBBOOK_ADMIN_EMAILS=you@company.com

# Bootstrap admin — auto-creates this admin account on startup
NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL=admin@example.com
NOOBBOOK_BOOTSTRAP_ADMIN_PASSWORD=YourSecurePassword123!
```

> **How it works:** The bootstrap admin is created automatically when the app starts. You'll use these credentials to log in at `http://localhost`. Any other user who signs up gets the `user` role (can chat, use studio, manage projects). Admins can additionally manage app settings and API keys.

### Step 3: Run Setup

```bash
bash docker/setup.sh
```

This will:
1. Check prerequisites (Docker running, ports free, python3 available)
2. Generate Supabase secrets (JWT tokens, database passwords)
3. Create the Docker network
4. Start Supabase services (PostgreSQL, Auth, Storage, API gateway)
5. Build and start NoobBook (backend, frontend, database migration)

First run takes **3-5 minutes** (downloading images + building). Subsequent runs are faster (cached).

> **Already ran setup before?** If you've previously set up NoobBook and something isn't working, do a full reset first so everything starts fresh:
> ```bash
> bash docker/reset.sh -v
> bash docker/setup.sh
> ```

When you see this, you're good:
```
============================================
  NoobBook is running!
============================================

  App:              http://localhost
  Backend API:      http://localhost:5001/api/v1
  Supabase API:     http://localhost:8000
```

### Step 4: Log In

Open `http://localhost` and sign in with the bootstrap admin credentials you set in Step 2.

---

### Auth & Roles (RBAC)

NoobBook has two roles:
- **admin** — can view/update API keys, manage app settings, plus everything a user can do
- **user** — can chat, use studio, upload sources, and manage projects

**Auth settings in `docker/.env`:**

| Variable | Description |
|----------|-------------|
| `NOOBBOOK_AUTH_REQUIRED=true` | Requires login for all API routes (default: `true`) |
| `NOOBBOOK_ADMIN_EMAILS=a@b.com,c@d.com` | These emails get admin role on signup |
| `NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL` | Auto-creates this admin on startup |
| `NOOBBOOK_BOOTSTRAP_ADMIN_PASSWORD` | Password for the bootstrap admin |
| `NOOBBOOK_BOOTSTRAP_ADMIN_FORCE_RESET=true` | Reset the bootstrap admin password if account already exists |

> **First signup rule:** If no admins exist yet, the first user to sign up automatically becomes admin (even without being in `NOOBBOOK_ADMIN_EMAILS`).

---

### Managing Your Setup

**Stopping and starting:**
```bash
bash docker/stop.sh           # Stop all services (your data is preserved)
bash docker/setup.sh          # Start again (safe to re-run, uses existing config)
```

**Full reset (destructive — deletes all data):**
```bash
bash docker/reset.sh -v       # Stops everything + deletes database, storage, and .env files
bash docker/setup.sh          # Fresh start with new secrets
```

> **Note on re-running `setup.sh`:** The script is idempotent — it detects existing `.env` files and reuses them. Your Supabase secrets, database passwords, and API keys are **not regenerated** on subsequent runs. If you need fresh secrets (e.g. something is broken), do a full reset first with `reset.sh -v`.

**If something goes wrong:**
```bash
# Check container status
docker ps --format "table {{.Names}}\t{{.Status}}"

# Check logs for a specific service
docker logs noobbook-backend
docker logs supabase-db
docker logs supabase-kong

# Nuclear option — wipe everything and start fresh
bash docker/reset.sh -v
bash docker/setup.sh
```

| Command | What it does |
|---------|-------------|
| `bash docker/setup.sh` | Start everything (idempotent, safe to re-run) |
| `bash docker/stop.sh` | Stop all services, keep data |
| `bash docker/reset.sh` | Stop all services, remove network |
| `bash docker/reset.sh -v` | Stop + delete ALL data (database, storage, .env files) |

| Service | URL |
|---------|-----|
| NoobBook App | `http://localhost` |
| Backend API | `http://localhost:5001/api/v1` |
| Supabase API | `http://localhost:8000` |
| MinIO Console | `http://localhost:9001` (supabase/supabase123) |

---

### Option B: Local Development

Run backend and frontend locally, but you still need Supabase running (via Docker or Supabase Cloud).

**Step 1: Start Supabase**

```bash
# Self-hosted via Docker
cp docker/supabase/.env.example docker/supabase/.env
# Edit docker/supabase/.env (see backend/supabase/SETUP.md for details)
docker network create noobbook-network
docker compose -f docker/supabase/docker-compose.yml --env-file docker/supabase/.env up -d

# Or use Supabase Cloud — get keys from https://app.supabase.com/project/_/settings/api
```

**Step 2: Run database migrations**

```bash
# Via psql
psql -h localhost -p 5432 -U postgres -d postgres -f backend/supabase/init.sql

# Or via Supabase Studio → SQL Editor → paste contents of init.sql → Run
```

**Step 3: Configure environment**

```bash
cp backend/.env.template backend/.env
nano backend/.env
```

Add your API keys AND Supabase keys:
```bash
# Required API keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...

# Required Supabase keys (app won't start without these)
SUPABASE_URL=http://localhost:8000
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
```

**Step 4: Install and run**

macOS / Linux:
```bash
bin/setup                     # First time — creates venv, installs all deps
bin/dev                       # Starts backend (:5001) + frontend (:5173)

# Options
bin/dev --backend-only        # Only Flask server
bin/dev --frontend-only       # Only Vite server
bin/dev --install             # Update deps before starting
```

Windows:
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

cd ../frontend
npm install

python start.py               # Starts both servers
python stop.py                 # Stops both servers
```

**Step 5: Install Playwright (for web scraping)**
```bash
npx playwright install
```

For the full Supabase setup guide, see [`backend/supabase/SETUP.md`](backend/supabase/SETUP.md).

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + Vite + TypeScript |
| UI | shadcn/ui + Tailwind CSS |
| Icons | Phosphor Icons |
| Backend | Python Flask + SocketIO |
| Database | Supabase (PostgreSQL + S3 Storage + Auth) |
| AI/LLM | Claude (Anthropic), OpenAI Embeddings |
| Vector DB | Pinecone |
| Audio | ElevenLabs |
| Image Gen | Google Gemini |
| Video Gen | Google Veo 2.0 |

---

## Contributing

Contributions welcome!

**Branch strategy:**
- `main` - Stable branch for testing and using NoobBook
- `develop` - Latest changes, all PRs go here

**Quick start:**
1. Fork the repo
2. Pull from `develop`
3. Create your branch
4. Open a PR to `develop` (not main)

See [CONTRIBUTING.md](CONTRIBUTING.md) for full details and `CLAUDE.md` for code guidelines.

---

## License 

**License YOLO.v1.01**
- New License type

**Free to use:**
- Fork it, self-host it, use it for yourself or your company

**Want to commercialize it?**
- Become an authorized seller: [noob@noobbooklm.com](mailto:noob@noobbooklm.com)
- Or provide a minimum sponsorship of $10,000 USD

If you commercialize without authorization... well, we're too busy building to chase you. But karma has a way of catching up.

---

**Built with a $10,000 USD sponsorship grant.**
