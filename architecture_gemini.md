# NoobBook Architecture

This document provides a high-level overview of the NoobBook application architecture, including its backend, frontend, database, and AI services.

## 1. System Overview

NoobBook is a modern AI-powered application designed to assist users with various tasks (writing, research, planning) through specialized "AI Agents" and a chat interface. It utilizes a **Retrieval-Augmented Generation (RAG)** pipeline to ground AI responses in user-uploaded documents.

The system is built on a decoupled client-server architecture:
- **Frontend**: A React Single Page Application (SPA).
- **Backend**: A Python Flask REST/SocketIO API.
- **Infrastructure**: Dockerized services with Supabase as the backend-as-a-service (BaaS) provider.

---

## 2. Backend Architecture

**Framework**: Python (Flask)
**Key Libraries**: `Flask-SocketIO`, `Supabase`, `LangChain` (implied logic), `OpenAI`, `Anthropic`, `Google GenAI`.

### Core Components

1.  **Application Factory**:
    - Located in `backend/app/__init__.py`.
    - Initializes the Flask app, database connections, and extensions (CORS, SocketIO).
    - Registers **Blueprints** for modular routing.

2.  **API Blueprints** (`backend/app/api/`):
    - **Auth**: Handles user session and validation.
    - **Chats/Messages**: Manages conversation history and real-time AI interaction.
    - **Projects**: Manages workspaces, settings, and costs.
    - **Sources**: Handles file uploads, text extraction, and indexing.
    - **Studio**: Manages generative UI artifacts (graphs, documents).
    - **Brand**: Manages user/project brand assets.

3.  **Service Layer** (`backend/app/services/`):
    - **AI Agents**: Specialized classes for distinct tasks (e.g., `BlogAgent`, `PRDAgent`, `DeepResearchAgent`).
    - **Chat Services**: Orchestrates the conversation flow, including RAG retrieval and tool execution.
    - **Data Services**: Abstractions for database interactions.
    - **Source Services**: Pipeline for document ingestion (PDF/Docx/PPTX extraction -> Chunking -> Embedding).

4.  **Authentication**:
    - **Supabase Auth**: JWT-based authentication.
    - **Middleware**: A `before_request` hook in `backend/app/api/__init__.py` validates tokens for all protected routes, injecting `g.user_id` into the context.

---

## 3. Frontend Architecture

**Framework**: React 19 + TypeScript
**Build Tool**: Vite
**Styling**: Tailwind CSS

### Key Libraries & Components

-   **UI Primitives**: Radix UI (accessible, headless components) styled with Tailwind (likely `shadcn/ui` pattern).
-   **Routing**: React Router (`react-router-dom`).
-   **State & Networking**: `axios` for REST requests, `socket.io-client` (implied) for real-time chat.
-   **Visualizations**:
    -   `recharts` for data charting.
    -   `mermaid` for diagrams.
    -   `@xyflow/react` (React Flow) for node-based graphs.
    -   `@excalidraw/excalidraw` for whiteboard sketches.

---

## 4. Data Model (Supabase/PostgreSQL)

The database schema is defined in `backend/supabase/migrations/`.

### Core Entities

-   **`users`**: User profiles and global settings/memory.
-   **`projects`**: The main container for user work. Tracks API costs (`input/output tokens`) and project-specific memory.
-   **`sources`**: Uploaded files/links. Tracks processing status (`uploaded`, `embedding`, `ready`) and file metadata.
-   **`chunks`**: Text segments extracted from sources for RAG.
-   **`chats`** & **`messages`**: Standard chat history model. Messages support structured content and citation tracking.
-   **`studio_signals`**: A unique table for **Generative UI**. The AI inserts records here to trigger client-side UI generation (e.g., "Create a Mind Map").
-   **`background_tasks`**: Tracks async operations like file processing or deep research.

### Vector Search
-   The application appears to use **Pinecone** for vector storage (based on `requirements.txt` and source metadata), but the schema also includes provisions for `pgvector` (`enable_pgvector` migration and commented-out embedding columns).

---

## 5. AI & RAG Pipeline

1.  **Ingestion**:
    -   User uploads a file (PDF, DOCX, etc.) or link.
    -   Backend extracts text using `pypdf`, `python-docx`, `youtube-transcript-api`, or `playwright` (web scraping).
    -   Text is chunked and embedded (likely via OpenAI text-embedding-3).
    -   Vectors are stored in Pinecone/pgvector.

2.  **Retrieval**:
    -   User asks a question.
    -   System embeds the query and searches the vector store.
    -   Relevant chunks are retrieved and appended to the LLM context.

3.  **Generation**:
    -   The backend selects the appropriate model (Claude, GPT-4, Gemini) based on user tier or task complexity.
    -   Specialized **Prompts** (stored in `backend/app/data/prompts/`) guide the AI behavior.

---

## 6. Deployment & Infrastructure

-   **Docker**: The entire stack (Backend, Frontend, Supabase) is containerized via `docker-compose.yml` for consistent development and deployment.
-   **Supabase**: Provides the database, authentication, and file storage (S3-compatible).
