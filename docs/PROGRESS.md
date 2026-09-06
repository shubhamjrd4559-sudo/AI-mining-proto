# CMPDI AI — Implementation Progress

**Last updated:** 2026-09-06 (IST)
**Project:** SIH26023 — AI-Powered Geological, Mining and Other Reporting Solution for CMPDI/CIL

---

## Current Phase

**PHASE 6 — DYNAMIC ANALYTICS + DATA EXPLORER (COMPLETE)**
**Status: READY FOR REVIEW**
**All Phase 1–6 tests passing (191 total tests: 22 Phase 5 intelligence + 19 Phase 6 analytics + 7 datasets + 143 existing). Verification complete.**

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

### Phase 4 — AI Excel/CSV Maintainer

- [x] **New Django App: `apps.maintainer`**
  - Registered in `LOCAL_APPS` and `INSTALLED_APPS`
  - Database migrations applied (`maintainer.0001_initial`)
  - Admin registration for `MaintainerSuggestion`

- [x] **Model & Lifecycle State Machine**
  - `MaintainerSuggestion` model: `PENDING → APPROVED → APPLIED`, `PENDING → REJECTED`, `APPROVED → FAILED`
  - Fields: `dataset`, `record`, `document`, `field_name`, `original_value`, `suggested_value`, `applied_value`, `issue_type`, `reason`, `confidence`, `suggestion_source` (`deterministic` / `ai`), `provenance`, `status`, `error_message`, `created_by`, `reviewed_by`, timestamps
  - Full indexing and relational links to `StructuredDataset` and `StructuredRecord`

- [x] **Deterministic Cleaning Engine (`apps/maintainer/suggester.py`)**
  - Rules for whitespace cleanup, comma-number formatting, redundant plus / missing zero numeric formatting, percentage standardization, financial year normalization, date ISO 8601 normalization, safe unit casing (`MT`, `KT`, `km`), and mine/subsidiary title casing.
  - Safe generation: Never auto-applies; generates persisted `MaintainerSuggestion` records.

- [x] **Optional AI Fallback (`apps/maintainer/ai_maintainer.py`)**
  - Environment-configured (`OPENAI_API_KEY` / `GEMINI_API_KEY`).
  - Bounded context-level calls (never one call per cell).
  - Graceful degradation when AI credentials are not provided.

- [x] **Owner-Scoped & Authenticated APIs (`apps/maintainer/views.py`)**
  - `GET /api/maintainer/datasets/` — Owner-scoped dataset library
  - `GET /api/maintainer/datasets/<id>/overview/` — Dataset overview & summary metrics
  - `GET /api/maintainer/datasets/<id>/records/` — Paginated records with suggestion flags
  - `GET /api/maintainer/datasets/<id>/suggestions/` — Filterable suggestions list
  - `GET /api/maintainer/datasets/<id>/validation-issues/` — Document validation findings
  - `POST /api/maintainer/datasets/<id>/generate-suggestions/` — Trigger suggestion engine
  - `POST /api/maintainer/suggestions/<id>/approve/` — Single approval (does NOT apply)
  - `POST /api/maintainer/suggestions/<id>/reject/` — Single rejection
  - `POST /api/maintainer/suggestions/batch-review/` — Batch approval / rejection
  - `POST /api/maintainer/datasets/<id>/apply/` — Atomic apply with conflict protection
  - `GET /api/maintainer/datasets/<id>/export/xlsx/` — Download maintained XLSX
  - `GET /api/maintainer/datasets/<id>/export/csv/` — Download maintained CSV

- [x] **Safety, Conflict Protection & Immutability**
  - Source file immutability: Original uploaded files are never overwritten.
  - Conflict protection: Verifies record's current value matches `original_value` before applying; marks `FAILED` with details if modified.
  - Transaction atomicity: Uses `transaction.atomic()` and row-level locking (`select_for_update`).
  - Non-destructive revision backup: Original values retained in `_original_before_apply` keys.
  - Audit logging: Every review (approve/reject/batch) and apply creates immutable `AuditEvent` records.
  - Strict ownership: Rejects orphan datasets without valid owners.

- [x] **Interactive Frontend UI (`index.html`)**
  - "Data Maintainer" navigation tab in sidebar.
  - Active dataset picker with real-time overview metrics.
  - Three-tab workspace: Suggested Fixes (Before → After), Dataset Records, Validation Issues.
  - Interactive single & batch approve/reject actions, explicit "Apply Changes" button, and XLSX/CSV export downloads.

- [x] **Phase 4 Test Suite**
  - 45 focused Phase 4 tests in `apps.maintainer.tests`.

---

### Phase 5 — RAG Mining Intelligence

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

### Phase 6 — Dynamic Analytics + Data Explorer (this phase)

- [x] **New Django App: `apps.analytics`**
  - Registered in `LOCAL_APPS` and mounted at `path('api/analytics/', ...)`
  - Reuses existing models (`StructuredDataset`, `StructuredRecord`, `ExtractionProvenance`, `ValidationResult`, `MaintainerSuggestion`) with **zero new database models and zero new migrations** (`makemigrations --check` detects no changes).

- [x] **High-Performance Query Engine (`apps/analytics/query_engine.py`)**
  - Dynamic column and concept discovery (`production`, `dispatch`, `target`, `financial_year`, `subsidiary`, `mine`, `grade`, etc.).
  - Chronological Financial Year parsing & sorting (e.g. `2021-22`, `FY22-23`, `2023-2024`).
  - Dynamic KPI calculations: Total production, target, dispatch, achievement %, period-over-period growth %, active mines, active subsidiaries.
  - Data Quality metrics: total records, valid records, warnings, errors, valid percentage.
  - Data Quality safety: automatically excludes records flagged with errors (`is_valid=False` or error-level validations).
  - Time-series trends calculation with growth % and provenance record tracking.
  - Categorical breakdown calculations (subsidiary, mine, grade) with share percentages and drill-down record IDs.
  - Dynamic arbitrary query execution: supports `SUM`, `AVG`, `MIN`, `MAX`, `COUNT` over any numeric column, grouped by any categorical dimension.

- [x] **Analytics REST API Endpoints (`apps/analytics/views.py`)**
  - `GET /api/analytics/datasets/` — Owner-scoped dataset selector with concept detection
  - `GET /api/analytics/kpi/` — Real-time dynamic KPIs and available filter options
  - `GET /api/analytics/trends/` — Chronological time-series trends with target/dispatch overlay
  - `GET /api/analytics/breakdown/` — Grouped comparisons (subsidiary, grade, mine)
  - `GET /api/analytics/query/` — Flexible dynamic aggregation endpoint
  - `GET /api/analytics/drilldown/` — Deep-dive record details with extraction provenance

- [x] **Data Explorer REST API Endpoints (`apps/datasets/views.py`)**
  - `GET /api/datasets/list/` — Owner-scoped dataset library
  - `GET /api/datasets/<id>/schema/` — Dynamic schema discovery and distinct filter options
  - `GET /api/datasets/<id>/records/` — Server-side pagination, global text search, safe sorting, multi-concept filtering
  - `GET /api/datasets/<id>/records/<record_id>/` — Full record detail with complete extraction provenance, validation findings, and maintainer suggestions
  - `GET /api/datasets/<id>/export/csv/` — Export filtered dataset rows to RFC-4180 CSV
  - Preserved `GET /api/datasets/` for Phase 1 backwards compatibility

- [x] **Interactive Frontend Integration (`index.html`)**
  - **Dynamic Analytics Dashboard**:
    - Real-time KPI summary cards (Production, Achievement %, Growth %, Active Mines/Subsidiaries, Valid Data %).
    - Dynamic filter bar: Subsidiary, Financial Year, Sheet, and Metric selectors.
    - Chart.js time-series trend line/bar chart with chronological FY axis.
    - Subsidiary production breakdown chart + Coal Grade distribution chart.
    - Top producing mines leaderboard.
    - Interactive chart drill-down modal showing exact records and document provenance.
  - **Live Data Explorer**:
    - Dataset dropdown with record counts.
    - Dynamic schema-driven table headers with sort indicators (asc/desc).
    - Global keyword search input and dynamic concept filter dropdowns (Subsidiary, FY, Sheet, Quality).
    - Server-side pagination controls (Previous, Next, Page X of Y, Record range display).
    - Filtered CSV export button.
    - Inspect Record modal showing full JSON fields, extraction provenance (document, sheet, row, extractor method, confidence), validation findings, and maintainer history.

- [x] **Database Seeding (`seed_sample_mining_data`)**
  - Command `python manage.py seed_sample_mining_data` created.
  - Seeds 26 multi-year CIL coal production & dispatch records across 7 subsidiaries (SECL, MCL, NCL, CCL, WCL, ECL, BCCL) covering FY21 through FY25.
  - Includes full provenance, validation issues (warnings/errors), and maintainer suggestions for testing.

---

## Test Suite Results (Phase 1–6 Complete)

**191/191 tests PASSED (exit code 0)**

| App | Tests | Result |
|---|---|---|
| `apps.core` | 6 | ✅ PASS |
| `apps.documents` | 47 | ✅ PASS |
| `apps.datasets` | 7 | ✅ PASS |
| `apps.audit` | 4 | ✅ PASS |
| `apps.storage` | 11 | ✅ PASS |
| `apps.pipeline` | 30 | ✅ PASS |
| `apps.maintainer` | 45 | ✅ PASS |
| `apps.intelligence` | 22 | ✅ PASS |
| `apps.analytics` | 19 | ✅ PASS |
| **TOTAL** | **191** | **✅ ALL PASS** |

---

## Security & Architecture Verification

1. **Authentication**: All query, maintainer, datasets, analytics, and management endpoints require `IsAuthenticated`.
2. **Access Control**: Retrieval, maintainer queries, datasets explorer, and analytics enforce `document__uploaded_by=user` preventing cross-user data leakage.
3. **Immutability**: Source files and audit records remain immutable.
4. **Conflict Protection**: Maintainer applies changes atomically with row locking and value verification.
5. **Prompt Injection Defense**: Untrusted chunk text is wrapped in data blocks with strict instructions.
6. **No Hallucinated Calculations**: Structured queries execute deterministic database aggregations.
7. **Zero External Test Dependencies**: Tests mock external AI/LLM boundaries while keeping retrieval, business logic, and access control real.
8. **Data Quality Safety**: `AnalyticsQueryEngine` excludes `ERROR`-level validation results and invalid records from analytics.

---

## Known Limitations

- **OCR requires Tesseract binary**: System Tesseract must be installed on the host for image OCR.
- **LLM API Key**: Requires `GEMINI_API_KEY` or `OPENAI_API_KEY` in `.env` for AI generation; otherwise uses deterministic / offline grounded synthesis fallback.
- **SQLite Concurrency in Dev**: SQLite transactions lock the table briefly during heavy multi-threading.
