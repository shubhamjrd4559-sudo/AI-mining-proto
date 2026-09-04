# SIH 2026 — CMPDI AI Mining Intelligence Command Center
# Implementation Roadmap

## Project Overview

**Problem Statement:** SIH26023 — AI-Powered Geological, Mining and Reporting Solution
**Client:** CMPDI / Coal India Limited subsidiaries
**Stack:** Django + DRF backend · SQLite→PostgreSQL · Static HTML frontend (→ React in Phase 4)

---

## Phase 1 — Full-Stack Foundation (CURRENT)

**Goal:** Establish a working, production-structure backend that the existing frontend can communicate with.

### Deliverables
- [x] Django project with split settings (base/dev/prod)
- [x] Database models: Document, ProcessingJob, StructuredDataset, StructuredRecord, AuditEvent
- [x] Django REST Framework configuration
- [x] `GET /api/health/` endpoint
- [x] Local storage abstraction (S3-compatible interface)
- [x] Stub API boundaries for all future services
- [x] Frontend `apiServices` object wired to backend
- [x] Environment configuration (.env.example, .gitignore)
- [x] docs/PROGRESS.md

### NOT in Phase 1
- OCR / PDF / DOCX extraction
- AI / RAG / embeddings
- Real data processing pipelines
- Production deployment

---

## Phase 2 — Real Document Upload + Storage

**Goal:** Users can upload real documents; files are stored; basic metadata is recorded.

### Deliverables
- File upload endpoint: `POST /api/documents/`
- Chunked upload support
- ProcessingJob creation on upload
- Document list/retrieve/delete: `GET/DELETE /api/documents/{id}/`
- Frontend Documents page wired to real upload
- Storage backend swapped to local (already abstracted)
- Celery task queue stub for async processing

---

## Phase 3 — Document Processing Pipeline

**Goal:** Uploaded documents are OCR-processed and structured data is extracted.

### Deliverables
- PDF text extraction (pdfplumber / PyMuPDF)
- Scanned PDF OCR (Tesseract / EasyOCR)
- DOCX extraction (python-docx)
- XLSX/CSV ingestion
- StructuredRecord population
- ProcessingJob lifecycle (Processing → Extracting → Validating → Indexed)
- Celery worker + Redis

---

## Phase 4 — AI / RAG / Analytics

**Goal:** AI-powered Q&A, analytics, and report generation over real data.

### Deliverables
- Vector embeddings (sentence-transformers or OpenAI)
- Vector store (Chroma or pgvector)
- RAG pipeline for AI Query
- Dynamic analytics API (`/api/analytics/`)
- Topic modeling (BERTopic)
- Report generation (ReportLab / WeasyPrint)
- Excel AI Maintainer

---

## Phase 5 — Production Hardening

**Goal:** Deploy to production with proper security, monitoring, and scalability.

### Deliverables
- PostgreSQL migration
- S3/object storage backend
- Authentication (JWT + role-based)
- Rate limiting
- HTTPS / nginx / gunicorn
- Docker Compose
- CI/CD pipeline
- Monitoring (Sentry, logging)

---

## Technology Decisions

| Concern | Phase 1-2 | Phase 3+ |
|---|---|---|
| Database | SQLite | PostgreSQL |
| Storage | Local filesystem | S3-compatible |
| Auth | Django session | JWT (djangorestframework-simplejwt) |
| Task queue | — | Celery + Redis |
| OCR | — | Tesseract / EasyOCR |
| AI | — | Gemini / OpenAI via LangChain |
| Frontend | Static HTML | React (progressive migration) |
| Deploy | Local dev | Docker + nginx |
