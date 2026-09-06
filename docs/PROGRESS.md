# CMPDI AI — Implementation Progress

**Last updated:** 2026-09-05 (IST)
**Project:** SIH26023 — AI-Powered Geological, Mining and Other Reporting Solution for CMPDI/CIL

---

## Current Phase

**PHASE 6 — DYNAMIC ANALYTICS + DATA EXPLORER (COMPLETE)**
**Status: READY FOR REVIEW**
**All 169 tests passing (19 analytics + 7 datasets + 143 existing). Verification complete.**

---

## Completed Work

### Phase 1 — Foundation (previously completed)
- Django backend, health endpoint, stub API, git baseline

### Phase 2 — Real Document Upload & Storage (previously completed)
- Multipart upload with magic-byte validation, LocalStorageBackend
- `Document`, `ProcessingJob`, `AuditEvent` models with migrations
- IsAuthenticated on all document endpoints, owner-scoping
- TokenAuthentication login flow, seed_dev_user management command
- 71 Phase 2 tests passing (all preserved)

### Phase 3 — Document Processing Pipeline (previously completed)
- Extractor modules (PDF, DOCX, XLSX, CSV, TXT, OCR)
- Dynamic Schema Detection (25+ mining concepts)
- Normalization (financial year, numeric units, dates)
- Validation Engine (10 issue types, severity levels)
- Orchestrator and thread safety
- 30 Phase 3 pipeline tests passing

### Phase 4 — AI Excel/CSV Maintainer (this phase)

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

- [x] **Test Suite Expansion**
  - 45 focused Phase 4 tests in `apps.maintainer.tests`.
  - Full project suite: 146/146 tests passing.

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

- [x] **Test Suite Expansion**
  - 19 comprehensive tests in `apps.analytics.tests` (100% pass).
  - 7 comprehensive tests in `apps.datasets.tests` (100% pass).
  - Full project suite: 169/169 tests passing with zero regressions.

---

## Test Suite Results (Phase 6 Complete)

**169/169 tests PASSED (exit code 0)**

| App | Tests | Result |
|---|---|---|
| `apps.core` | 6 | ✅ PASS |
| `apps.documents` | 47 | ✅ PASS |
| `apps.datasets` | 7 | ✅ PASS |
| `apps.audit` | 4 | ✅ PASS |
| `apps.storage` | 11 | ✅ PASS |
| `apps.pipeline` | 30 | ✅ PASS |
| `apps.maintainer` | 45 | ✅ PASS |
| `apps.analytics` | 19 | ✅ PASS |
| **TOTAL** | **169** | **✅ ALL PASS** |

---

## Known Limitations

- **OCR requires Tesseract binary**: Must install Tesseract OCR separately if OCR for scanned images is required. Graceful fallback is tested and supported.
- **SQLite Concurrency in Dev**: In multi-threaded development environments, SQLite file locks are mitigated by bounded exponential retries. Production deployments should use PostgreSQL.
- **AI Token Configuration**: AI contextual analysis requires `OPENAI_API_KEY` or `GEMINI_API_KEY` in `.env`. When absent, deterministic rules operate at 100% functionality without error.

- [x] **Pipeline Orchestrator** (`apps/pipeline/orchestrator.py`)
  - Daemon thread launched after each successful upload (non-blocking)
  - Correct status sequence: `UPLOADED → PROCESSING → EXTRACTING → VALIDATING → INDEXED/NEEDS_REVIEW/FAILED`
  - Storage accessed read-only (original file immutable)
  - `update_or_create` for retry safety; `close_old_connections()` for thread DB safety

- [x] **Persistence**
  - `ExtractionResult` — per-document extraction record (OneToOne with Document)
  - `ExtractionProvenance` — per-StructuredRecord source tracing
  - `ValidationResult` — per-finding validation issues
  - `StructuredDataset` + `StructuredRecord` — structured tables persisted in `apps.datasets`

- [x] **API Endpoint**
  - `GET /api/documents/<id>/extraction/` — authenticated, owner-only
  - Returns extractor type, OCR used, page count, tables count, validation summary, top 50 findings

- [x] **Document Detail Serializer Integration**
  - `DocumentDetailSerializer.extraction_summary` field returns real-time extraction state

- [x] **Minimal Frontend Integration** (`index.html`)
  - Document detail modal shows extraction status, OCR used, type, tables, validation summary
  - No frontend redesign; only extraction info appended in existing pipeline status section

- [x] **Dependencies Added** (`requirements.txt`)
  - `pdfplumber==0.11.4`
  - `python-docx==1.1.2`
  - `openpyxl==3.1.5`
  - `Pillow==10.4.0`
  - `pytesseract==0.3.13`

- [x] **SQLite Concurrency & Lock Resilience**
  - Added `is_transient_db_error` detection for SQLite table locks, busy states, and timeouts.
  - Added `db_retry` decorator with bounded exponential backoff and jitter for database operations.
  - Top-level exception safety ensuring documents reach `FAILED` state rather than hanging on error.
  - Configured SQLite connection busy `timeout: 20` in development settings.
  - Added dedicated regression tests (`ConcurrencyAndRetryTests`).

---

## Test Suite Results (Phase 3 Complete)

**101/101 tests PASSED (exit code 0)**

| App | Tests | Result |
|---|---|---|
| `apps.core` | 6 | ✅ PASS |
| `apps.documents` | 47 | ✅ PASS |
| `apps.datasets` | 3 | ✅ PASS |
| `apps.audit` | 4 | ✅ PASS |
| `apps.storage` | 11 | ✅ PASS |
| `apps.pipeline` | 30 | ✅ PASS |
| **TOTAL** | **101** | **✅ ALL PASS** |

**Notes:**
- Transient SQLite database locks in background threads are handled gracefully via bounded retry and backoff, preventing unhandled thread crashes and ensuring documents cleanly reach terminal status.
- OCR tests produce expected `"tesseract is not installed"` log messages when the Tesseract system binary is not on the host; graceful degradation confirmed working.

---

## Known Limitations

- **OCR requires Tesseract binary**: Must install Tesseract OCR (system package) separately.
  `pytesseract` is installed; if Tesseract binary is absent, OCR returns `OCR_UNAVAILABLE` gracefully.
  See installation notes below.
- **SQLite test isolation**: Background pipeline threads contend with SQLite test transactions.
  This is a SQLite limitation; harmless in development and irrelevant with PostgreSQL in production.
- **Scanned PDF rendering**: `page.to_image()` in pdfplumber requires `pypdfium2` (auto-installed).
  On constrained systems, PDF-to-image rendering may be slow for large documents.
- **Thread-based processing**: No Celery/Redis. Pipeline runs in daemon threads. Under high upload
  concurrency, threads accumulate. Acceptable for SIH demo; Celery migration planned for Phase N.

---

## Tesseract Installation (for OCR support)

**Windows**: Download installer from https://github.com/UB-Mannheim/tesseract/wiki
Add Tesseract to system PATH, or set in `.env`:
```
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
```

**Ubuntu/Debian**: `sudo apt-get install tesseract-ocr`
**macOS**: `brew install tesseract`

---

## Next Phase

**PHASE 4** (not yet started — awaiting approval)

