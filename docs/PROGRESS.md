# CMPDI AI — Implementation Progress

**Last updated:** 2026-09-05 (IST)
**Project:** SIH26023 — AI-Powered Geological, Mining and Other Reporting Solution for CMPDI/CIL

---

## Current Phase

**PHASE 3 — DOCUMENT EXTRACTION, OCR, SCHEMA DETECTION & VALIDATION (COMPLETE)**
**Status: READY FOR REVIEW**
**All 97 tests passing. Local checkpoint commit created.**

---

## Completed Work

### Phase 1 — Foundation (previously completed)
- Django backend, health endpoint, stub API, git baseline

### Phase 2 — Real Document Upload & Storage (previously completed)
- Multipart upload with magic-byte validation, LocalStorageBackend
- `Document`, `ProcessingJob`, `AuditEvent` models with migrations
- IsAuthenticated on all document endpoints, owner-scoping
- TokenAuthentication login flow, seed_dev_user management command
- 71 Phase 2 tests passing (all preserved in Phase 3)

### Phase 3 — Document Processing Pipeline (this phase)

- [x] **New Django app: `apps.pipeline`**
  - Isolated from Phase 2; minimal integration only at upload trigger hook
  - Registered in `INSTALLED_APPS`, migrations applied

- [x] **Extractor Modules** (`apps/pipeline/extractor/`)
  - `pdf_extractor.py` — pdfplumber text extraction; pytesseract OCR fallback for scanned pages
  - `docx_extractor.py` — python-docx paragraphs + tables
  - `xlsx_extractor.py` — openpyxl multi-sheet extraction
  - `csv_extractor.py` — csv.Sniffer delimiter detection (comma/semicolon/tab/pipe)
  - `txt_extractor.py` — multi-encoding UTF-8/latin-1 detection
  - `image_extractor.py` — Pillow + pytesseract OCR; graceful degradation when Tesseract unavailable
  - `base.py` — `ExtractedDocument` and `ExtractedTable` dataclasses

- [x] **Dynamic Schema Detection** (`apps/pipeline/schema/detector.py`)
  - Rule-based regex matching for 25+ mining concepts (mine, coalfield, subsidiary, production,
    financial_year, dispatch, grade, seam, borehole, coordinates, reserve, resource, etc.)
  - Returns `{raw_header: {concept, confidence, raw}}`

- [x] **Value Normalization** (`apps/pipeline/schema/normalizer.py`)
  - Financial year normalization (e.g. `FY 2024-25` → `2024-25`)
  - Numeric + unit extraction (e.g. `4.5 MT` → `{value: 4.5, unit: 'MT'}`)
  - Date parsing to ISO 8601
  - Original values always preserved alongside normalized values

- [x] **Validation Engine** (`apps/pipeline/validation/engine.py`)
  - 10 issue types: `missing_required`, `duplicate`, `invalid_numeric`, `invalid_date`,
    `inconsistent_unit`, `suspicious_value`, `coordinate_error`, `schema_mismatch`,
    `extraction_failure`, `duplicate_record`
  - Severity levels: INFO / WARNING / ERROR
  - Per-row, per-table, and dataset-level checks

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

