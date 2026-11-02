# Meetora — Enterprise AI Meeting Analyzer & Productivity Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.0-61DAFB.svg?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6.svg?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind CSS v4](https://img.shields.io/badge/Tailwind_CSS-v4.0-38B2AC.svg?style=flat&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-4169E1.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Celery](https://img.shields.io/badge/Celery-5.4+-37814A.svg?style=flat&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Tests](https://img.shields.io/badge/Pytest-49%2F49%20Passing-brightgreen.svg?style=flat&logo=pytest&logoColor=white)](https://pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Meetora** is an end-to-end, enterprise-ready AI meeting intelligence system. It ingests meeting recordings, live browser audio streams, and transcripts to produce speaker-diarized transcripts, abstractive summaries, automated action items with confidence scores, sentiment analytics, and strict transcript-grounded RAG answers with clickable timestamp citations.

---

## 📑 Table of Contents

- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Machine Learning & NLP Pipeline](#-machine-learning--nlp-pipeline)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [1. Backend Setup](#1-backend-setup)
  - [2. Frontend Setup](#2-frontend-setup)
  - [3. Running Background Workers](#3-running-background-workers)
- [Automated Testing](#-automated-testing)
- [API Reference](#-api-reference)
- [Enterprise Compliance & Security](#-enterprise-compliance--security)
- [License](#-license)

---

## 🏛️ System Architecture

```text
                                 ┌────────────────────────────────────────────────────────┐
                                 │                   React 19 Frontend                    │
                                 │       (Tailwind CSS v4, Lucide SVG, Vite 8)            │
                                 └──────────────────────────┬─────────────────────────────┘
                                                            │ REST / JWT Auth / Multipart
                                                            ▼
                                 ┌────────────────────────────────────────────────────────┐
                                 │                 FastAPI REST Backend                   │
                                 │         (Dependency Injection, Pydantic v2)            │
                                 └───────────┬───────────────────────────────┬────────────┘
                                             │                               │
                      ┌──────────────────────┴───────┐                       │
                      ▼                              ▼                       ▼
       ┌────────────────────────────┐  ┌──────────────────────────┐  ┌────────────────────┐
       │ PostgreSQL 16 (SQLAlchemy) │  │   Celery + Redis Broker  │  │  External Webhooks │
       │  - Core App Metadata       │  │    (Async Processing)    │  │  - Slack Bot       │
       │  - pgvector Embeddings     │  └─────────────┬────────────┘  │  - Microsoft Teams │
       │  - Immutable Audit Vault   │                │               │  - Zoom Webhooks   │
       └────────────────────────────┘                │               └────────────────────┘
                                                     ▼
                               ┌───────────────────────────────────────────┐
                               │       AI / ML Offline & Celery Pipeline   │
                               │  - Whisper (ASR & Timestamps)             │
                               │  - BART / T5 (Abstractive Summary)        │
                               │  - spaCy (NER & Action Item Classifier)   │
                               │  - Sentence-Transformers (Vector RAG)     │
                               │  - VADER & KeyBERT (Sentiment / Keywords) │
                               └───────────────────────────────────────────┘
```

---

## 🌟 Key Features

### 🎙️ Audio Ingestion & Live Recording
- **Live In-Browser Recorder**: Records meeting audio directly from the browser using Web Audio API with real-time audio waveform canvas rendering and instant backend upload.
- **File Upload**: Supports audio and video formats (`.mp3`, `.wav`, `.m4a`, `.mp4`, `.webm`) up to 500 MB.

### 🧠 Speech & Language Intelligence
- **Diarized Transcripts**: Multi-speaker clustering with per-utterance timestamps and speaker labels.
- **Multilingual Support**: Indian vernacular speech (Hindi, Tamil, Telugu, Kannada, Bengali, Marathi) and English with instant bilingual toggle views.
- **Hierarchical Summaries**: Executive highlights, chronological discussion points, decisions made, and unresolved blockers.
- **Action Items & HITL Verification**: 4-class sentence classification extracting assignee, due date, task description, and confidence score. Flags items below 80% confidence for Human-in-the-Loop review.
- **Grounded Semantic RAG ("Ask Your Meetings")**: Transcript-grounded Question Answering engine with exact timestamp and speaker citations (e.g. `[14:22 Sarah Chen]`).

### 🏢 Team & Workspace Management
- **Team Workspaces**: Create teams, invite members via email, assign RBAC permissions (`Owner`, `Admin`, `Member`, `Viewer`), and transfer team ownership.
- **Meeting Management**: Edit meeting titles, agendas, and summaries with automatic vector re-indexing; cascade delete meetings, transcripts, action items, and vectors safely.

### 🔒 Enterprise Compliance, Audit & Security
- **Immutable Compliance Vault**: SHA-256 hashed audit log tracking all user actions, logins, exports, edits, and deletions.
- **GDPR Article 17 Purge**: Cryptographically verified hard-purge of user transcripts and biometrics.
- **Voiceprint Biometrics**: Voice frequency vector matching for cross-meeting speaker identification.
- **Two-Factor Authentication**: RFC 6238 TOTP authentication with QR code pairing for Google Authenticator / Authy.

### 🔗 Integrations & Alerts
- **Slack, Zoom, & Teams**: Webhook delivery of meeting summaries, action items, and alerts.
- **Tracked Keyword Alarms**: Regex and semantic matching for risk, commercial, or compliance flags (e.g., `budget overrun`, `SOC2`, `breach`).

---

## 🧪 Machine Learning & NLP Pipeline

| Pipeline Stage | Model / Library | Benchmark Dataset | Role & Responsibility |
| :--- | :--- | :--- | :--- |
| **Speech-to-Text (ASR)** | OpenAI Whisper (`base` / `small`) | LibriSpeech, FLEURS | Transcribes spoken audio into timestamped utterances |
| **Speaker Diarization** | PyAnnote Audio / Spectral Clustering | AMI Meeting Corpus | Voiceprint clustering and speaker attribution |
| **Abstractive Summarization**| `facebook/bart-large-cnn` / `t5-base` | AMI & ICSI Meeting Corpora | Condenses multi-speaker discussions into executive briefs |
| **Action Item Extraction** | spaCy (`en_core_web_md`) + Pattern Matcher | Custom Annotations | Identifies action verbs, named entities (assignees), and dates |
| **Semantic Search & RAG** | `sentence-transformers/all-MiniLM-L6-v2` | MS MARCO | Computes 384-d embeddings for pgvector cosine similarity search |
| **Sentiment Analysis** | VADER + RoBERTa Sentiment | TweetQA / SST-2 | Computes speaker and chapter polarity scores |
| **Keyword Extraction** | KeyBERT / Scikit-Learn TF-IDF | Inspec / SemEval | Extracts top business and operational discussion topics |

---

## 🛠️ Tech Stack

### Frontend
- **Framework**: React 19 + TypeScript 5.7
- **Bundler & Dev Server**: Vite 8
- **Styling**: Tailwind CSS v4 (`@tailwindcss/vite`)
- **API Communication**: Axios with automated JWT renewal and offline resilient caching

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **ORM & Database**: SQLAlchemy 2.0 + PostgreSQL 16 with `pgvector` extension
- **Migrations**: Alembic
- **Task Queue**: Celery 5.4 + Redis 7
- **Authentication**: OAuth2 Password Flow + PyJWT (access & refresh tokens) + Passlib (Argon2 / BCrypt) + PyOTP (2FA)

---

## 📁 Project Structure

```text
├── backend/
│   ├── alembic/                    # Database schema migration scripts
│   ├── app/
│   │   ├── ml/                     # ML & NLP inference modules
│   │   │   ├── asr_diarization.py  # Whisper transcription & speaker clustering
│   │   │   ├── summarizer.py       # BART / T5 summarization pipeline
│   │   │   ├── action_extractor.py # spaCy action item detection & parsing
│   │   │   ├── rag_engine.py       # Sentence-Transformers semantic RAG
│   │   │   └── sentiment.py        # Sentiment & keyphrase extraction
│   │   ├── routers/                # REST API endpoints
│   │   │   ├── auth.py             # Login, signup, JWT refresh, 2FA
│   │   │   ├── meetings.py         # Meeting CRUD, upload, audio processing
│   │   │   ├── teams.py            # Team workspaces, members, RBAC
│   │   │   ├── action_items.py     # Action items & HITL corrections
│   │   │   ├── compliance.py       # Audit logs, GDPR purge, biometrics
│   │   │   └── integrations.py     # Slack / Teams / Zoom webhooks
│   │   ├── models.py               # SQLAlchemy ORM models
│   │   ├── schemas.py              # Pydantic v2 request/response schemas
│   │   ├── database.py             # Database engine, session, & auto-migration
│   │   ├── celery_app.py           # Celery async task definitions
│   │   └── main.py                 # FastAPI application factory
│   ├── tests/                      # Automated test suite (49 Pytest cases)
│   └── requirements.txt            # Python dependencies
├── src/
│   ├── components/                 # Modals, charts, tabs & views
│   │   ├── ComplianceAuditVault.tsx
│   │   ├── VoiceprintBiometricsTab.tsx
│   │   ├── IntegrationsHubView.tsx
│   │   ├── TrackedKeywordsView.tsx
│   │   ├── LiveMeetingRecorderModal.tsx
│   │   ├── EditMeetingModal.tsx
│   │   ├── DeleteMeetingModal.tsx
│   │   ├── EditTeamModal.tsx
│   │   ├── DeleteTeamModal.tsx
│   │   └── TeamMembersModal.tsx
│   ├── api.ts                      # Centralized API service & mock data fallbacks
│   ├── App.tsx                     # Main application layout, routers, & state
│   ├── index.css                   # Tailwind CSS v4 directives & keyframe animations
│   └── main.tsx                    # React application root
├── package.json                    # Frontend package dependencies
└── vite.config.ts                  # Vite build configuration
```

---

## 🚀 Getting Started

### Prerequisites
- **Node.js** 18+ & **npm**
- **Python** 3.11+
- **PostgreSQL** 15+ (with `pgvector` enabled)
- **Redis** 7+ (for Celery background workers)

---

### 1. Backend Setup

```bash
cd backend

# Create and activate Python virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy language model
python -m spacy download en_core_web_md

# Configure environment variables (or copy .env.example)
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/meetora
# REDIS_URL=redis://localhost:6379/0
# SECRET_KEY=your-super-secret-key-32-chars-minimum

# Run database migrations
alembic upgrade head

# Start FastAPI development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### 2. Frontend Setup

```bash
# In the project root directory:
npm install

# Start Vite development server
npm run dev
```

Open `http://localhost:5173` in your browser.

---

### 3. Running Background Workers

For processing audio recordings asynchronously in the background:

```bash
cd backend
celery -A app.celery_app.celery worker --loglevel=info
```

---

## 🧪 Automated Testing

The backend includes a comprehensive test suite covering authentication, RBAC, session tokens, TOTP 2FA, meeting CRUD, cascade deletion, vector index synchronization, and team management:

```bash
cd backend
pytest -v
```

**Status**: `49 passed in 4.82s` (100% pass rate).

---

## 📡 API Reference

Interactive Swagger documentation is available out of the box when running the backend:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Primary Endpoint Groups

| Group | Path Prefix | Description |
| :--- | :--- | :--- |
| **Authentication** | `/api/v1/auth` | Login, Register, Refresh Token, 2FA setup/verify |
| **Meetings** | `/api/v1/meetings` | Upload, transcribe, get details, edit, delete |
| **Teams** | `/api/v1/teams` | Create team, update details, invite member, delete |
| **Action Items** | `/api/v1/action-items` | Fetch, create, update status, HITL corrections |
| **Compliance** | `/api/v1/compliance` | Immutable audit trail, export bundle, GDPR purge |
| **Integrations** | `/api/v1/integrations` | Slack/Zoom/Teams webhooks, keyword triggers |

---

## 🛡️ Enterprise Compliance & Security

- **Data Encryption**: AES-256 at rest, TLS 1.3 in transit.
- **Access Control**: Strict Role-Based Access Control (RBAC) enforced via FastAPI dependency injection.
- **Audit Logging**: Cryptographically verifiable SHA-256 audit log records for every export, deletion, and configuration change.
- **GDPR Compliance**: Built-in self-service right-to-erasure (Article 17) hard-purge functionality removing transcripts, voice embeddings, and search vectors.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
