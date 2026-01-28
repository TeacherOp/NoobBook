# NoobBook

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
Backend API (Flask)
    |
    ├── Source Processing (upload, extract, chunk, embed)
    ├── Chat Service (RAG search, Claude API, citations)
    ├── Studio Services (content generation agents)
    └── Integrations (Claude, OpenAI, Pinecone, ElevenLabs, Gemini)
    |
    v
Data Storage (JSON files)
```

**AI Services:**
- **Claude** - Main LLM for chat, agents, content generation
- **OpenAI** - Embeddings for vector search
- **Pinecone** - Vector database for RAG
- **ElevenLabs** - Text-to-speech and transcription
- **Gemini** - Image generation
- **Google Veo** - Video generation

---

## Running Locally

### Prerequisites

```bash
# macOS
brew install libreoffice ffmpeg
npx playwright install

# Ubuntu/Debian
sudo apt install libreoffice ffmpeg
npx playwright install
```

### macOS / Linux

```bash
# First time setup (creates venv, installs dependencies)
bin/setup

# Run both backend and frontend
bin/dev

# Options
bin/dev --backend-only    # Only Flask server
bin/dev --frontend-only   # Only Vite server
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

### API Keys

Create `backend/.env` or configure in **Dashboard -> Settings**:

**Required:**
- `ANTHROPIC_API_KEY` - Claude API
- `OPENAI_API_KEY` - Embeddings
- `PINECONE_API_KEY` + `PINECONE_INDEX_NAME` - Vector database

**Optional:**
- `ELEVENLABS_API_KEY` - Audio features
- `TAVILY_API_KEY` - Web search
- `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` - Google Drive import

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + Vite + TypeScript |
| UI | shadcn/ui + Tailwind CSS |
| Icons | Phosphor Icons |
| Backend | Python Flask |
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
