# Scheduler-Agent

Agentic RAG–powered assistant built with LangGraph that answers user queries from a knowledge base and guides users to create, update, or cancel Google Meet calls, managing availability and sending meeting links via email.

---

## Setup Instructions

# Scheduler-Agent — Agentic RAG + Scheduler (LangGraph learning project)

This repository is my learning project for LangGraph subgraph integration and building agentic systems. It contains two main capabilities:

- An agentic RAG (Retrieval-Augmented Generation) agent that answers questions from ingested documents.
- A scheduler agent that can create Google Calendar events and generate Google Meet links.

I'm experimenting with integrating my scheduler into the agentic RAG using LangGraph subgraph integration options. This README explains how the project is organized and how to run and use the APIs.

## Highlights

- Backend: FastAPI application exposing REST endpoints to interact with conversations and agents.
- Agents: Agentic workflow code that powers both RAG-based question answering and a scheduler agent.
- Persistence: SQL database (SQLAlchemy + Alembic) for conversations, messages and other data.
- Vector DB: pluggable vector DB adapters live under `app/vector_db` (Chroma, PG vector, Milvus etc.).

## What's different in this branch / learning notes

- This repo is a learning playground for LangGraph subgraphs. The aim is to integrate the scheduler agent as a LangGraph subgraph and wire it into the agentic RAG flow.
- I added instructions to run the server with Uvicorn and updated the Python target to 3.12.

## Quick setup (local development)

Prerequisites:

- Python 3.12 (use uv, pyenv, conda, or your preferred environment manager)
- git

1. Clone

```bash
git clone https://github.com/BennisonDevadoss/langgraph-scheduler-agent
cd langgraph-scheduler-agent
mkdir assets creds
```

2. Create and activate an environment (example using pyenv + virtualenv or conda):

Using UV (recommended):

```bash
uv sync
```

Using pyenv/venv (python=3.12):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Using conda:

```bash
conda create -n scheduler-agent python=3.12
conda activate scheduler-agent
pip install -r requirements.txt
```

3. Environment variables

Copy and edit environment files as needed:

```bash
cp .env.example .env.development
cp .env.example .env.staging
cp .env.example .env.production
# Then edit the .env.* files with your keys (DB, GOOGLE API, OAUTH, etc.)
```

4. Database migrations and seeding

```bash
alembic upgrade head
python app/seeders/seed.py
```

5. Run the app

The application exposes a FastAPI `app` in `app/main.py`. Start it with uvicorn so you get ASGI performance and proper reload behavior:

```bash
cd app # if you are not in app directory.
# from repository root
# Option 1: Inline environment variable
ENVIRONMENT=development python main.py

# Option 2: Export and run
export ENVIRONMENT=development
python main.py
```

## Notes about crawling and Celery

- The repository contains `crawl4ai` and Celery integration pieces. Right now those features are not required for local experimentation with the agents, so you can ignore them for the moment. Do not remove the code — the project keeps the hooks for future work.
- If you want to enable crawling or background workers later, the code paths and Celery tasks are present under `app/queues` and `app/datasource`. You can follow the existing task signatures to wire a broker (Redis/RabbitMQ) and start workers.
  These are learning notes — the repo contains agent code under `app/agents/*` to help with this work.

## API overview

Base path: /v1 (see `app/routers/v1/router.py`)

Important endpoints:

- Conversations

  - POST /v1/conversations/
    - Create a new conversation. Accepts a `session_id` and returns conversation metadata.
  - GET /v1/conversations/session/{session_id}
    - List conversations for a session.
  - GET /v1/conversations/{conversation_uuid}
    - Get a conversation and its messages.
  - DELETE /v1/conversations/{conversation_uuid}
    - Delete a conversation (requires session_id for auth in the request query/body).
  - POST /v1/conversations/{conversation_uuid}/chat
    - Send a message to a conversation. The server will persist the user message, call the RAG agent to generate a response, save the bot response, and return the bot's reply.

- Chat (agent endpoints)

  - POST /v1/chat/rag/web (deprecated)
    - Generate a RAG-based chat response using an indexed collection.
  - POST /v1/chat/scheduler/web (deprecated)
    - Generate a scheduler-specific chat response.
  - POST /v1/chat/secure/web (experimental, deprecated)
    - A secured endpoint demonstrating captcha and fingerprint dependencies.

- Datasource (ingestion)

  - POST /v1/datasource/upload/temp
    - Upload a temporary file for ingestion into a collection.
  - POST /v1/datasource/upload
    - Upload a file; this starts a background processing task and returns a task id.
  - POST /v1/datasource/crawl
    - Start a crawl job to ingest content (uses crawl4ai helpers — optional for now).
  - GET /v1/datasource/task/{task_id}
    - Check task status for ingestion/processing jobs.

- Calendar / Scheduler
  - GET /v1/calendar/auth
    - Trigger a Google OAuth flow to authorize the app to access a Google Calendar.
  - POST /v1/calendar/create_event
    - Create a calendar event and return the event id and Meet link. The endpoint accepts an `EventRequest` payload (see `app/schemas/calendar_schema.py`).

## How the RAG and Scheduler agents work together

- RAG Agent

  - The RAG agent answers questions using ingested documents stored in the vector DB collections.
  - Ingestion APIs exist under `/v1/datasource` (upload, crawl). After ingestion the RAG agent will answer queries from the ingested documents.
  - To add temporary files for quick ingestion use POST `/v1/datasource/upload/temp`.

- Scheduler Agent
  - The scheduler agent is responsible for interacting with Google Calendar (authenticate, create events, generate Meet links).
  - The calendar endpoints are under `/v1/calendar`. The scheduler agent can be called directly via the API or invoked from within the RAG agent if you wire it with LangGraph subgraphs.
  - Typical workflow: RAG decides an action needs scheduling -> call scheduler subgraph / API -> scheduler authenticates (if needed) and creates event -> returns Meet link and event id.

## Integration with your chatbot

You can use the conversation/chat endpoints to integrate this application with a chatbot frontend. A typical flow:

1. Create or select a conversation for a user (POST /v1/conversations/)
2. Send chat messages to POST /v1/conversations/{conversation_uuid}/chat to get agent responses.
3. If the bot needs to create meetings, it can either:
   - Call POST /v1/calendar/create_event directly, or
   - Use LangGraph subgraph wiring to let the RAG agent call the scheduler subgraph automatically.

## Developer notes / file locations

- FastAPI app: `app/main.py`
- Routers: `app/routers/v1/`
- Agentic RAG code: `app/agents/agentic_rag/`
- Scheduler agent / workflow: `app/agents/scheduler/`
- Conversations & messages: `app/routers/v1/conversation_router.py`, `app/services/conversation_service.py`, `app/schemas/conversation_schema.py`
- Datasource ingestion: `app/routers/v1/datasource_router.py`, `app/services/datasource_service.py`
- Calendar service: `app/routers/v1/calendar_router.py`, `app/services/calendar_service.py`

## Running tests / linting

This project doesn't yet include an automated test suite in the repo root. Before adding tests, run linters and type-checkers as you prefer. Consider adding a lightweight pytest suite covering at least the router happy paths and any core service logic you change.

## Future work / TODO

- Build a LangGraph scheduler subgraph and show end-to-end integration with the agentic RAG subgraph.
- Add first-class tests for conversation flows and calendar interactions (unit + integration).
- Optionally wire up crawl4ai and Celery with an explicit broker and worker setup for ingestion pipelines.

## Short summary of changes in this README

- Target Python version changed to 3.12.
- Recommend running with Uvicorn (example `uvicorn app.main:app`).
- Clarified that `crawl4ai` and Celery exist but are optional/not required for current experimentation.
- Documented API endpoints and how RAG and Scheduler agents interact.

If you'd like, I can also:

- Add a minimal `Makefile` with dev commands (start, migrate, seed, lint).
- Add a small example script that creates a conversation and sends a chat message to demonstrate the end-to-end flow.
