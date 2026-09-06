# CMPDI AI — Implementation Progress

**Last updated:** 2026-09-06 (IST)  
**Project:** SIH26023 — AI-Powered Geological, Mining and Other Reporting Solution for CMPDI/CIL  

---

## Current Phase

**PHASE 5 — REAL RAG-BASED MINING INTELLIGENCE / AI QUERY & RESPONSE (COMPLETE)**  
**Status: READY FOR REVIEW**  
**All 123 tests passing (22 Phase 5 tests + 101 regression tests). Local checkpoint commit created.**

---

## Completed Work

### Phase 1 — Foundation
- Django backend, health endpoint, stub API, git baseline

### Phase 2 — Real Document Upload & Storage
- Multipart upload with magic-byte validation, LocalStorageBackend
- `Document`, `ProcessingJob`, `AuditEvent` models with migrations
- `IsAuthenticated` on all document endpoints, owner-scoping
- TokenAuthentication login flow, `seed_dev_user` management command
- 71 Phase 2 tests passing

### Phase 3 — Document Processing Pipeline
- Extractor modules (PDF with pdfplumber + OCR fallback, DOCX, XLSX, CSV, TXT, Image OCR)
- Dynamic schema detection (25+ mining concepts)
- Normalization engine (FY, units, dates)
- Quality validation engine with 10 issue types
- Pipeline orchestrator with retry and SQLite concurrency resilience
- `ExtractionResult`, `ExtractionProvenance`, `ValidationResult`, `StructuredDataset`, `StructuredRecord`

---

### Phase 5 — RAG Mining Intelligence (This Phase)

- [x] **New Django App: `apps.intelligence`**
  - Registered in `INSTALLED_APPS` and URL configuration
  - Models:
    - `DocumentChunk`: Text chunks with `document`, `chunk_index`, `content`, `content_hash`, `page_number`, `section_heading`, `metadata`, `token_count`
    - `AIQueryLog`: Query history tracking `user`, `question`, `query_type`, `answer`, `confidence`, `sources`, `evidence_count`, `source_count`, `created_at`

- [x] **Deterministic Chunking & Fingerprinting** (`apps/intelligence/indexing/chunker.py`)
  - Sentence and paragraph boundary preservation
  - Page number and section context retention
  - Structured table chunking with row indices and column headers
  - Idempotent SHA-256 fingerprinting for duplicate detection

- [x] **Indexing Lifecycle & Safe Re-Indexing** (`apps/intelligence/indexing/indexer.py`)
  - Only successfully processed documents (`INDEXED`, `NEEDS_REVIEW`, `COMPLETED`) are indexable
  - Unchanged content skipped automatically
  - Atomic deletion and recreation during re-indexing
  - Pipeline hook in `orchestrator.py` automatically indexes documents upon extraction completion
  - Management command `reindex_documents` for batch and individual document indexing

- [x] **Intelligent Query Routing** (`apps/intelligence/router/query_router.py`)
  - Classifies queries into:
    1. `STRUCTURED`: Numerical queries, subsidiary comparisons, aggregations (max, min, sum, avg)
    2. `DOCUMENT`: Narrative, qualitative exploration methods, and geological overviews
    3. `HYBRID`: Combines numerical facts with document context
  - Rule-based regex entity extraction (subsidiaries MCL, ECL, BCCL, CCL, WCL, SECL, NCL, CMPDI, metrics, FYs)

- [x] **User-Scoped Multi-Tenant Retrieval** (`apps/intelligence/retrieval/retriever.py`)
  - Strict owner filtering during retrieval (`uploaded_by=request.user`) — cross-user leakage blocked
  - BM25 ranked document chunk retrieval with heading and phrase boosts
  - Deterministic structured database querying and calculations (no hallucinated numbers)
  - Full provenance extraction via `ExtractionProvenance`

- [x] **Prompt Injection Defense & LLM Client** (`apps/intelligence/generator/`)
  - `llm_client.py`: Configurable Gemini client (`GEMINI_API_KEY`, model `gemini-2.5-flash`), safe timeouts, and error handling
  - `answer_engine.py`: Encapsulates retrieved content in passive `<document_evidence>` blocks with explicit refusal rules
  - Insufficient evidence refusal: *"I could not find sufficient evidence in the available project data."*
  - Confidence assessment (`HIGH`, `MEDIUM`, `LOW`) based on retrieval score and evidence counts
  - Offline grounded synthesis fallback when LLM provider is unavailable

- [x] **Authenticated APIs** (`apps/intelligence/views.py`)
  - `POST /api/chat/` and `POST /api/intelligence/query/` (`IsAuthenticated` enforced, no `AllowAny`)
  - `GET /api/intelligence/history/` for user's past queries
  - `POST /api/intelligence/reindex/` for user-triggered re-indexing
  - Automatic `AuditEvent` logging (`ai.query`)

- [x] **Frontend Integration** (`index.html`)
  - `runAIQuery(question)` calls authenticated backend API
  - Displays grounded answers, `STRUCTURED`/`DOCUMENT`/`HYBRID` query badges, and confidence indicators
  - Displays traceable source cards with document title, page numbers, sections, tables, rows, and provenance references
  - Clear no-evidence and error states

---

## Test Suite Results (Phase 5 Complete)

**123/123 tests PASSED (exit code 0)**

| App | Tests | Result |
|---|---|---|
| `apps.core` | 6 | ✅ PASS |
| `apps.documents` | 47 | ✅ PASS |
| `apps.datasets` | 3 | ✅ PASS |
| `apps.audit` | 4 | ✅ PASS |
| `apps.storage` | 11 | ✅ PASS |
| `apps.pipeline` | 30 | ✅ PASS |
| `apps.intelligence` | 22 | ✅ PASS |
| **TOTAL** | **123** | **✅ ALL PASS** |

---

## Security & Architecture Verification

1. **Authentication**: All query and management endpoints require `IsAuthenticated`.
2. **Access Control**: Retrieval queries enforce `document__uploaded_by=user` preventing cross-user data leakage.
3. **Immutability**: Source files and audit records remain immutable.
4. **Prompt Injection Defense**: Untrusted chunk text is wrapped in data blocks with strict instructions.
5. **No Hallucinated Calculations**: Structured queries execute deterministic database aggregations.
6. **Zero External Test Dependencies**: Tests mock the external LLM boundary while keeping retrieval, business logic, and access control real.

---

## Known Limitations

- **OCR requires Tesseract binary**: System Tesseract must be installed on the host for image OCR.
- **LLM API Key**: Requires `GEMINI_API_KEY` in `.env` for LLM generation; otherwise uses offline grounded synthesis fallback.
- **SQLite Concurrency in Dev**: SQLite transactions lock the table briefly during heavy multi-threading.
