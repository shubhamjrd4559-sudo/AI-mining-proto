# SIH 2026 — CMPDI AI Mining Intelligence Command Center
# Final Implementation Roadmap (Phases 1 – 11)

**Project:** SIH26023 — AI-Powered Geological, Mining and other Reporting Solution for CMPDI/CIL Subsidiaries  
**Audited Repository:** `AI-mining-proto`  
**Audit Timestamp:** 2026-09-10  
**Operating System:** Windows  
**Framework:** Python 3.12/3.14 · Django 6.1 · Django REST Framework 3.18 · SQLite (PostgreSQL-Ready) · Vanilla HTML5/CSS3/JavaScript SPA  

---

## 1. Project Overview

The CMPDI AI Mining Intelligence Command Center is an end-to-end, multi-subsidiary enterprise platform developed for **Central Mine Planning & Design Institute (CMPDI)** and **Coal India Limited (CIL)** subsidiaries (ECL, BCCL, CCL, WCL, SECL, MCL, NCL, CMPDI HQ).

The platform ingests complex, heterogeneous mining documents (annual reports, production tables, borehole logs, GSI exploration dossiers, parliamentary replies, environmental filings, and operational spreadsheets), extracts structured tables and narrative text, detects and normalizes mining concepts, provides human-in-the-loop data maintenance, indexes chunks with strict user-scoping for grounded AI queries, computes dynamic analytics and KPIs, generates verifiable audit-governed reports, visualizes spatial mine distributions and 3D geological strata, and maintains an immutable audit trail.

---

## 2. Final Architecture

```
                                    ┌──────────────────────────────────────────────────────────┐
                                    │               SINGLE-FILE WEB FRONTEND                   │
                                    │    Vanilla HTML5 / CSS3 / ES6+ JavaScript SPA (index.html)│
                                    │  11 Modules: Dashboard, Docs, AI Query, Analytics,        │
                                    │  Explorer, Maintainer, Reports, Topics, Map, Geo3D, Audit │
                                    └────────────────────────────┬─────────────────────────────┘
                                                                 │ HTTP / JSON / Multipart
                                                                 │ TokenAuthentication (sessionStorage)
                                                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                  DJANGO 6.1 MODULAR MONOLITH                                                   │
├───────────────────┬───────────────────┬───────────────────┬───────────────────┬───────────────────┬────────────────────────────┤
│    apps.frontend  │   apps.documents  │   apps.pipeline   │  apps.maintainer  │ apps.intelligence │       apps.analytics       │
│  SPA Shell Server │ Upload, Storage,  │ Extraction, OCR,  │ Clean Suggestions,│ Chunker, BM25,    │ Dynamic KPIs, Trends,      │
│  Static Assets    │ Lifecycle, Delete │ Schema, Normalize │ Batch Review, CSV │ RAG Answer Engine │ Grouped Breakdowns, Filters│
├───────────────────┼───────────────────┼───────────────────┼───────────────────┼───────────────────┼────────────────────────────┤
│   apps.datasets   │   apps.reports    │    apps.phase8    │    apps.audit     │   apps.storage    │         apps.core          │
│ Data Explorer API │ 8 Report Types,   │ Topics, WordCloud,│ Immutable Events, │ StorageService    │ Health checks, Seeds,      │
│ Provenance Viewer │ Exporters, Review │ 107 Mines, Geo3D  │ Actor tracking    │ Local / S3 Abstr. │ Shared utilities           │
└───────────────────┴───────────────────┴───────────────────┴───────────────────┴───────────────────┴────────────────────────────┘
                                                                 │
                                                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                     DATA & STORAGE LAYER                                                       │
│  • SQLite Database (Development & Demo Prototype) — 100% PostgreSQL-Ready Django ORM Models                                    │
│  • Local File Storage (Media Directory) — S3-Compatible Abstraction Layer                                                      │
│  • Zero Mandatory External Infrastructure (Runs fully without Redis, Celery, Vector DBs, or Kubernetes)                        │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Frontend Architecture
* **Single-file static SPA** (`index.html`, rendered via Django `apps.frontend.views.index` at `/`).
* **Zero build step required** (no Node.js/Webpack/Vite pipeline needed during prototype).
* **Styling:** Custom CSS design system with CMPDI/CIL tokens (`--navy: #071A3D`, `--royal: #0B4DB8`, `--gold: #DFAE24`, `--green: #1E9E63`).
* **API Communication:** Unified `apiServices` object (`API_BASE = ''`, same-origin relative endpoints) with token injection, timeout handling, and automatic error toasts.
* **Preservation Policy:** Preserve existing polished vanilla UI. Gradual modularization only when required. No forced React rewrite.

### 2.2 Backend Architecture
* **Python 3.12 / 3.14 + Django 6.1 + Django REST Framework 3.18**.
* **Modular Monolith:** 12 cohesive Django apps residing in `backend/apps/`.
* **API Pattern:** RESTful JSON endpoints with explicit DRF serializers and permission classes (`IsAuthenticated` enforced, owner-scoped queries).
* **Storage Abstraction:** `apps.storage.service.get_storage_service()` providing pluggable `LocalStorageBackend` (dev) and `S3StorageBackend` (cloud).

### 2.3 Database Architecture
* **Prototype DB:** SQLite (`backend/db.sqlite3`).
* **Production DB:** PostgreSQL-ready via `DATABASE_URL` and `dj-database-url` in `production.py`.
* **MongoDB:** Not mandatory and not required.
* **Zero Data Loss Guarantee:** Existing database containing 9,965 structured records, 9,937 chunks, 107 mines, 1,075 GSI reports, and 2,226 OCBIS blocks is permanently preserved.

### 2.4 AI & RAG Architecture
* **Hybrid Retrieval:** BM25 chunk retrieval for qualitative narrative + deterministic database aggregations for numerical metrics.
* **Multi-Tenant Protection:** Retrieval querysets strictly filter `document__uploaded_by=request.user`.
* **Prompt Injection Defense:** Chunks are treated strictly as passive data inside `<document_evidence>` XML enclosures with closing tag sanitization.
* **Deterministic Fallback (DEMO MODE):** When external LLM API key (`GEMINI_API_KEY`) is unavailable or network is offline, the grounded synthesis fallback answers questions deterministically without crashing.

---

## 3. Core Data Flow

```
1. UPLOAD
   User uploads PDF, DOCX, XLSX, CSV, TXT, or scanned image
   → Magic byte validation & OpenXML structure integrity check
   → Stored via StorageService in local media storage
   → Document & ProcessingJob created (Status: UPLOADED → QUEUED)

2. EXTRACTION & OCR
   Pipeline Orchestrator triggers extraction based on file extension:
   • PDF: pdfplumber / pypdfium2 text + table extraction (OCR fallback for scans)
   • DOCX: python-docx paragraph and table parser
   • XLSX: openpyxl multi-sheet workbook reader
   • CSV / TXT: encoding-safe delimiter-aware parser
   • Scanned Images: pytesseract OCR engine

3. SCHEMA DETECTION & NORMALIZATION
   Extracted data fed to Mining Concept Detector:
   • Detects 25+ domain concepts (production, dispatch, target, seam, grade, overburden, FY)
   • Normalizes units (MT, KT, Tonnes), dates (ISO 8601), financial years (YYYY-YY)
   • Tracks ExtractionProvenance (document, sheet, table, row, column, confidence)

4. QUALITY VALIDATION & STRUCTURED STORAGE
   Validation Engine evaluates 10 rule classes:
   • Missing required fields, negative values, outlier production, invalid FY
   • Flags saved in ValidationResult (INFO, WARNING, ERROR)
   • Valid records stored in StructuredDataset and StructuredRecord

5. AI EXCEL/CSV MAINTAINER
   Human-in-the-loop data quality workbench:
   • Suggester engine generates MaintainerSuggestion (PENDING)
   • User reviews individual or batch suggestions (APPROVE / REJECT)
   • User clicks "Apply Changes" → atomic conflict-protected DB update
   • Source file remains immutable; exports available in cleaned XLSX and CSV

6. MINING INTELLIGENCE RAG & INDEXING
   Indexed documents chunked deterministically (paragraph & table boundary preserved):
   • SHA-256 fingerprinting prevents duplicate chunks
   • User asks natural language question in "AI Query"
   • Query Router categorizes into STRUCTURED, DOCUMENT, or HYBRID
   • Structured queries execute deterministic database calculations (SUM, AVG, etc.)
   • Document queries retrieve owner-scoped chunks via BM25 ranking
   • Grounded Answer Engine generates answer with traceable source cards

7. DYNAMIC ANALYTICS & DATA EXPLORER
   Single Source of Truth:
   • AnalyticsQueryEngine aggregates valid StructuredRecords
   • Dynamic KPI cards (National/CIL production, growth %, achievement %, active mines)
   • Chronological FY trend charts, subsidiary breakdowns, grade distributions
   • Data Explorer provides server-side search, filtering, pagination, and CSV export

8. REPORT GENERATION & EXPORT
   8 Official Report Types (Production, Geological, Mine Performance, Parliament reply, etc.):
   • Synthesizes live structured records and document chunks
   • Full lifecycle: DRAFT → GENERATED → UNDER_REVIEW → VERIFIED → APPROVED → EXPORTED
   • Real binary export generation: PDF (ReportLab), DOCX (python-docx), XLSX (openpyxl)

9. HUMAN REVIEW & IMMUTABLE AUDIT TRAIL
   Every action generates an AuditEvent:
   • Upload, retry, archive, suggestion review, data apply, report verify/approve, AI query
   • Dedicated Audit Trail UI displays chronological event stream with actor IP and metadata
```

---

## 4. Single-Source-of-Truth Principle

**Critical Architectural Law:** Disconnected mock or synthetic data must never compete with real processed data.
```
Uploaded Files
     │
     ▼
Extraction & Validation Engine
     │
     ▼
Structured Database Records (StructuredRecord + DocumentChunk)
     │
     ├──────────────────────────┼──────────────────────────┼──────────────────────────┤
     ▼                          ▼                          ▼                          ▼
Dashboard & Analytics       Data Explorer              Mining RAG AI              Report Generator
(Live DB Aggregations)     (Live Server Table)       (Live Chunks & Records)     (Live Records & Chunks)
```
* **Dashboard:** Must derive its KPI cards and trend charts from `AnalyticsQueryEngine` over live database records.
* **Analytics:** Visualizes live subsidiary, grade, and financial year distributions directly from `StructuredRecord`.
* **Data Explorer:** Browses, filters, searches, and inspects exact live records with full `ExtractionProvenance`.
* **AI / RAG:** Answers questions and computes statistics directly from live records and indexed chunks.
* **Reports:** Compiles official documents by pulling data directly from verified `StructuredRecord` rows.

---

## 5. Team Ownership Boundaries

| Module / Layer | Primary App | Key Models & Services | API Prefix |
|---|---|---|---|
| **Core Shell & Auth** | `apps.frontend`, `apps.core` | User, TokenAuthentication | `/`, `/api/health/`, `/api/auth/` |
| **Document Ingestion** | `apps.documents`, `apps.storage` | `Document`, `ProcessingJob`, `StorageBackend` | `/api/documents/` |
| **Extraction & Validation** | `apps.pipeline` | `ExtractionProvenance`, `ValidationResult` | `/api/pipeline/` |
| **Data Maintenance** | `apps.maintainer` | `MaintainerSuggestion`, `SuggesterEngine` | `/api/maintainer/` |
| **Mining Intelligence / RAG** | `apps.intelligence` | `DocumentChunk`, `AIQueryLog`, `AnswerEngine` | `/api/intelligence/`, `/api/chat/` |
| **Dynamic Analytics** | `apps.analytics`, `apps.datasets` | `AnalyticsQueryEngine`, `StructuredRecord` | `/api/analytics/`, `/api/datasets/` |
| **Report Generation** | `apps.reports` | `Report`, `ReportEngine`, Exporters | `/api/reports/` |
| **Spatial & Geological** | `apps.phase8` | `MineLocation`, `GSIReport`, `OcbisBlock` | `/api/phase8/` |
| **Governance & Audit** | `apps.audit` | `AuditEvent`, `AuditEventType` | `/api/audit/` |

---

## 6. 6-Day Recommended Execution Schedule

| Day | Assigned Phases | Focus Area | Key Deliverables |
|:---:|:---:|---|---|
| **Day 1** | **Phase 1** | Full-Stack Foundation + UI Integration | Reconcile frontend drift, fix `.env` settings evaluation, verify health & auth. |
| **Day 2** | **Phase 2 + Phase 3** | Ingestion, Storage, Extraction & OCR | Document upload verification, install parsing dependencies, end-to-end OCR extraction. |
| **Day 3** | **Phase 4 + Phase 5** | AI Maintainer + Mining RAG Intelligence | Excel/CSV cleaner verification, LLM key configuration, grounded Q&A with citations. |
| **Day 4** | **Phase 6 + Phase 7** | Analytics, Explorer & Report Generator | Wire Dashboard to live Analytics API, install ReportLab/openpyxl, export PDF/DOCX/XLSX. |
| **Day 5** | **Phase 8 + Phase 9** | Spatial Visuals + Human Review & Audit | 107 mines map, 3D strata, real Audit Trail API & UI, verification/approval sign-offs. |
| **Day 6** | **Phase 10 + Phase 11** | Polish, E2E Testing & SIH Demo Mode | 100% test pass rate, turnkey demo seed script, offline presentation demo mode. |

---

## 7. Comprehensive Dependency Matrix

| Dependency | Installed | Version | Required | Existing Usage | Missing Action | Relevant Phase |
|---|---|---|---|---|---|---|
| **Django** | Yes | 6.1.1 | Yes (>=6.0.4) | Web framework, ORM, settings | None | Phase 1 |
| **djangorestframework** | Yes | 3.18.0 | Yes (>=3.16.0) | REST API, serializers, auth | None | Phase 1 |
| **django-cors-headers** | Yes | 4.9.0 | Yes (>=4.7.0) | CORS middleware | None | Phase 1 |
| **python-decouple** | Yes | 3.8 | Yes (>=3.8) | Environment variable reader | None | Phase 1 |
| **python-dotenv** | Yes | 1.2.3 | Optional | .env loader | None | Phase 1 |
| **asgiref** | Yes | 3.12.1 | Yes | Django async runtime | None | Phase 1 |
| **sqlparse** | Yes | 0.6.0 | Yes | Django SQL formatting | None | Phase 1 |
| **tzdata** | Yes | 2026.3 | Yes | Timezone data | None | Phase 1 |
| **pdfplumber** | No | — | Yes (0.11.4) | `apps.pipeline.extractor.pdf_extractor` | Install in venv when Phase 3 approved | Phase 3 |
| **python-docx** | No | — | Yes (1.1.2) | `docx_extractor.py`, `docx_exporter.py` | Install in venv when Phase 3/7 approved | Phase 3, 7 |
| **openpyxl** | No | — | Yes (3.1.5) | `xlsx_extractor.py`, `maintainer`, `reports` | Install in venv when Phase 3/4/7 approved | Phase 3, 4, 7 |
| **Pillow** | No | — | Yes (10.4.0) | Image handling & OCR preprocessing | Install in venv when Phase 3 approved | Phase 3 |
| **pytesseract** | No | — | Yes (0.3.13) | Scanned PDF & image OCR fallback | Install in venv when Phase 3 approved | Phase 3 |
| **reportlab** | No | — | Yes (>=4.2.5) | `pdf_exporter.py` PDF generation | Install in venv when Phase 7 approved | Phase 7 |
| **pypdfium2** | No | — | Optional | Fast native PDF text extraction | Optional acceleration in Phase 3 | Phase 3 |
| **dj-database-url** | No | — | Optional (>=2.0.0)| PostgreSQL URL parsing in `production.py` | Install for production deployment | Phase 10 |
| **whitenoise** | No | — | Optional | Production static file serving | Install for production deployment | Phase 10 |
| **psycopg2-binary** | No | — | Optional | PostgreSQL adapter | Install if switching to PostgreSQL | Phase 10 |

---

## 8. Current Implementation Audit & Status Matrix

| Phase | Title | Current Status | Implemented Components | Broken / Missing / Disconnected Components |
|:---:|---|:---:|---|---|
| **P1** | Foundation & UI Integration | **90% Complete** | Django split settings, DRF config, health endpoint, token auth, static SPA serving. | `.env` has empty `MEDIA_ROOT` / `STATIC_ROOT` strings failing unit tests; root `index.html` has recent styles diverged from `templates/frontend/index.html`. |
| **P2** | Document Upload & Storage | **95% Complete** | Multipart upload, magic-byte checks, OpenXML checks, `Document`, `ProcessingJob`, LocalStorageBackend, retry, archive. | Unit tests fail due to `.env` empty `MEDIA_ROOT`; 6 documents already uploaded and stored safely. |
| **P3** | Extraction, OCR & Validation | **80% Complete** | Extractors coded for 6 formats, 25+ concept detector, normalizer, 10-rule validator, orchestrator with SQLite concurrency retry. | `pdfplumber`, `python-docx`, `openpyxl`, `Pillow`, `pytesseract` not installed in active venv causing test errors. |
| **P4** | AI Excel/CSV Maintainer | **90% Complete** | `MaintainerSuggestion` model, regex cleaner, approve/reject/batch review, atomic conflict-checked apply, audit logging, UI. | XLSX export endpoint fails because `openpyxl` is missing from venv; CSV export works. |
| **P5** | RAG Mining Intelligence | **95% Complete** | Chunking with SHA-256 fingerprints, query router, user-scoped BM25 retrieval, passive prompt injection defense, offline synthesis fallback, chat UI. | Gemini API key in `.env` needs network validation; deterministic offline fallback works completely. |
| **P6** | Dynamic Analytics & Explorer | **85% Complete** | `AnalyticsQueryEngine` (zero new models), dynamic KPIs, trends, breakdowns, Data Explorer server search/filter/pagination/CSV, UI modals. | **Disconnected Gap:** Main Dashboard (`pageDashboard()`) still uses static mock HTML/data instead of live `/api/analytics/kpi/` endpoint. |
| **P7** | Real Report Generator | **80% Complete** | `Report` model, full state machine, 8 pluggable generators, narrative editor, sign-off workflow, UI wizard. | PDF/DOCX/XLSX export endpoints fail with HTTP 500 because `reportlab`, `python-docx`, and `openpyxl` are not installed in venv. |
| **P8** | Topics, Map & 3D Geology | **100% Complete** | 107 verified mines, 1,075 GSI reports, 2,226 OCBIS blocks, dynamic TF-IDF topic modeler, interactive SVG map & 3D strata view, 26/26 tests passing. | Ready and verified. |
| **P9** | Human Review & Audit Trail | **40% Complete** | `AuditEvent` model, events recorded by Document, Maintainer, and Report apps. | `GET /api/audit/` is an unauthenticated Phase 1 stub returning `not_implemented`; frontend `afterAudit()` uses hardcoded `MOCK.auditTrail`. |
| **P10** | UI Polish & E2E Testing | **30% Complete** | 246 passing unit tests, responsive layouts, design tokens. | 11 tests failing due to missing packages & config; reconciles root vs template `index.html`. |
| **P11** | SIH Demo Mode & Preparation | **50% Complete** | Individual seed commands exist (`seed_dev_user`, `seed_sample_mining_data`, `seed_phase8_data`). | Unified turnkey demo script needed; offline fallback verification required. |

---

## 9. Phase Implementation Priorities

### P0 — MUST WORK (Core Enterprise Ingestion, Truth & Governance)
```
Document Upload ──▶ Extraction/OCR ──▶ Validation ──▶ Excel Maintainer ──▶ AI / RAG ──▶ Analytics ──▶ Report Generator ──▶ Audit Trail
```

### P1 — STRONG DEMO (Spatial & Visual Value-Adds)
* Topics & Dynamic Word Cloud
* Verified Mining Map (107 Indian coal mines)
* 3D Geological Strata & Borehole Viewer

### P2 — FUTURE (Post-Prototype Production Hardening)
* Cloud S3 Object Storage swap
* PostgreSQL production migration on Render/Docker
* Large-scale OCR distributed worker cluster

---

## 10. Detailed Phase-by-Phase Implementation Plans

---

### PHASE 1: Full-Stack Foundation + Existing UI Integration

#### 1. Goal
Ensure the core Django backend foundation is completely robust, resolves configuration gaps causing test failures, reconciles frontend template drift, and provides a stable communication channel between the static UI and API.

#### 2. Features to Implement / Reconcile
* Reconcile `backend/templates/frontend/index.html` with root `index.html` (porting over AI query background and hero styling without breaking Django template tags `{% load static %}`).
* Fix `.env` configuration parsing in `backend/config/settings/base.py` so that empty `MEDIA_ROOT=` or `STATIC_ROOT=` in `.env` fall back gracefully to default directory paths (`BASE_DIR / 'media'` and `BASE_DIR / 'staticfiles'`).
* Verify `GET /api/health/` returns database, storage, and auth subsystem status.
* Verify user authentication and token issuance via `POST /api/auth/token/`.

#### 3. Files / Modules Affected
* **Existing Files to Modify:**
  * `backend/config/settings/base.py` (safe fallback for empty string env vars)
  * `backend/templates/frontend/index.html` (synchronize styles from root `index.html`)
* **Existing Files Preserved:**
  * `backend/manage.py`, `backend/config/urls.py`, `backend/apps/core/`

#### 4. Dependencies on Previous Phases
* None (Foundation phase).

#### 5. Acceptance Criteria
* `python manage.py check` passes with 0 issues.
* `FrontendStaticAssetsTests.test_media_root_configured` and `test_static_root_configured` pass.
* Navigating to `http://127.0.0.1:8000/` loads the unified CMPDI AI Command Center with zero console errors.
* Root `index.html` and `backend/templates/frontend/index.html` design and styles are aligned.

#### 6. Testing Checklist
* [ ] `./venv/Scripts/python.exe backend/manage.py test apps.frontend apps.core`
* [ ] Verify `/api/health/` returns HTTP 200 with JSON payload `{"status": "ok"}`.
* [ ] Verify `/api/auth/token/` returns valid auth token for `admin`.

#### 7. What Must NOT Be Changed
* Do NOT rewrite frontend into React.
* Do NOT reset or delete `db.sqlite3`.
* Do NOT change existing database models.

#### 8. Expected Output / Demo Result
* Both frontend test cases pass. Clean console output on site load, displaying `[CMPDI AI] Backend connected`.

---

### PHASE 2: Real Document Upload + Storage

#### 1. Goal
Verify and stabilize the multi-format document upload pipeline, ensuring secure file storage, content-type verification, and multi-tenant isolation.

#### 2. Features to Implement / Reconcile
* Verify `LocalStorageBackend` storage directory creation and permissions under `backend/media/documents/`.
* Confirm multipart single and batch uploads (`POST /api/documents/`) enforce:
  * File size limits (`MAX_UPLOAD_SIZE = 50MB`, `MAX_BATCH_TOTAL_SIZE = 100MB`)
  * Magic byte verification (PDF `%PDF`, PNG, JPG, ZIP/OpenXML `PK\x03\x04`)
  * OpenXML ZIP integrity check (presence of `[Content_Types].xml` and `word/` or `xl/` components)
  * Filename sanitization against path traversal
* Confirm document listing (`GET /api/documents/`), status checks, authenticated download, retry, and archiving.

#### 3. Files / Modules Affected
* **Existing Modules:**
  * `backend/apps/documents/` (models, serializers, views, urls)
  * `backend/apps/storage/` (backends, service)
* **Existing Documents:**
  * Preserve all 6 existing uploaded PDF documents in `backend/documents/`.

#### 4. Dependencies on Previous Phases
* Depends on Phase 1 foundation and settings configuration.

#### 5. Acceptance Criteria
* All 47 tests in `apps.documents` pass.
* All 11 tests in `apps.storage` pass.
* Uploading an invalid or renamed `.exe` disguised as `.pdf` is rejected with HTTP 400.
* Uploading a valid mining PDF stores the file, creates a `Document` record, and returns HTTP 201.

#### 6. Testing Checklist
* [ ] `./venv/Scripts/python.exe backend/manage.py test apps.documents apps.storage`
* [ ] Test upload of valid PDF, XLSX, and CSV via API.
* [ ] Test download of stored document verifies ownership.

#### 7. What Must NOT Be Changed
* Do NOT delete any existing files in `backend/documents/` or `documents/`.
* Do NOT bypass `IsAuthenticated` on document endpoints.

#### 8. Expected Output / Demo Result
* Upload progress bar animates in UI, document appears in Documents table with status badge, and file is safely accessible in local storage.

---

### PHASE 3: Extraction + OCR + Schema Detection + Validation

#### 1. Goal
Install required extraction dependencies in the Python virtual environment and activate end-to-end parsing for PDF, DOCX, XLSX, CSV, and scanned image documents.

#### 2. Features to Implement / Reconcile
* Install missing parser packages in `./venv`:
  * `pdfplumber==0.11.4`
  * `python-docx==1.1.2`
  * `openpyxl==3.1.5`
  * `Pillow==10.4.0`
  * `pytesseract==0.3.13`
* Verify text and table extraction in `apps/pipeline/extractor/`:
  * `pdf_extractor.py` (extracts text and tables with OCR fallback)
  * `docx_extractor.py` (extracts paragraphs and tables)
  * `xlsx_extractor.py` (extracts multi-sheet tables)
  * `csv_extractor.py` and `txt_extractor.py`
* Verify dynamic concept detection (25+ mining concepts) in `apps/pipeline/schema/detector.py`.
* Verify normalization (financial years `YYYY-YY`, units `MT`) and quality validation (10 issue rules).
* Verify pipeline orchestrator lifecycle: `UPLOADED → QUEUED → PROCESSING → EXTRACTING → VALIDATING → INDEXED`.

#### 3. Files / Modules Affected
* **Environment:** `./venv/Scripts/pip.exe` (install dependencies from `backend/requirements.txt`).
* **Existing Modules:** `backend/apps/pipeline/` (extractors, schema, validation, orchestrator, models).

#### 4. Dependencies on Previous Phases
* Depends on Phase 2 document upload and file storage.

#### 5. Acceptance Criteria
* `pdfplumber`, `python-docx`, `openpyxl`, `Pillow`, and `pytesseract` import successfully.
* All 30 tests in `apps.pipeline` pass without any `ModuleNotFoundError`.
* Uploaded test CSV and PDF files parse into `StructuredDataset`, `StructuredRecord`, and `ExtractionProvenance` records.

#### 6. Testing Checklist
* [ ] `./venv/Scripts/python.exe backend/manage.py test apps.pipeline`
* [ ] Test extraction of sample multi-sheet Excel file.
* [ ] Test extraction of sample PDF annual report.
* [ ] Verify SQLite transaction retry handles concurrent processing jobs cleanly.

#### 7. What Must NOT Be Changed
* Do NOT alter extraction schema detector concepts without domain compatibility.
* Do NOT drop original file content during normalization.

#### 8. Expected Output / Demo Result
* Extracted records populate `StructuredRecord` table with detailed column mapping and cell provenance.

---

### PHASE 4: AI Excel/CSV Maintainer

#### 1. Goal
Provide an interactive, safe data quality workbench where users can inspect detected anomalies, review automated suggestions, and apply atomic corrections.

#### 2. Features to Implement / Reconcile
* Reconcile XLSX export in `apps/maintainer/views.py` now that `openpyxl` is installed.
* Verify deterministic rule suggester (`apps/maintainer/suggester.py`):
  * Whitespace cleanup, comma number formatting, financial year normalization, unit casing.
* Verify approval lifecycle: `PENDING → APPROVED → APPLIED` or `REJECTED`.
* Confirm conflict protection: verifies record's existing value has not drifted before applying.
* Confirm immutability: original uploaded files are never overwritten; revisions are non-destructive.
* Confirm XLSX and CSV export of cleaned datasets.

#### 3. Files / Modules Affected
* **Existing Modules:** `backend/apps/maintainer/` (models, views, suggester, tests).
* **Frontend:** Data Maintainer tab in `index.html`.

#### 4. Dependencies on Previous Phases
* Depends on Phase 3 structured datasets and `openpyxl` installation.

#### 5. Acceptance Criteria
* All 45 tests in `apps.maintainer` pass.
* `test_xlsx_dataset_overview` and `test_xlsx_export` pass.
* Batch approving suggestions and clicking "Apply Changes" updates records atomically with `AuditEvent` logging.

#### 6. Testing Checklist
* [ ] `./venv/Scripts/python.exe backend/manage.py test apps.maintainer`
* [ ] Test generating suggestions on seeded sample dataset.
* [ ] Test batch approval and rejection flow.
* [ ] Verify XLSX and CSV export files download cleanly.

#### 7. What Must NOT Be Changed
* Do NOT auto-apply suggestions without explicit user confirmation.
* Do NOT overwrite original uploaded source files.

#### 8. Expected Output / Demo Result
* Interactive 3-tab workbench in UI displaying before/after diffs, one-click batch review, and instant export.

---

### PHASE 5: Real Mining Intelligence AI / RAG

#### 1. Goal
Provide trustworthy, grounded natural language question-answering over indexed mining documents and structured production data with zero hallucinations and traceable citations.

#### 2. Features to Implement / Reconcile
* Validate Gemini 2.5 Flash client connectivity with configured `GEMINI_API_KEY`.
* Test deterministic chunking (`chunker.py`) and SHA-256 fingerprinting.
* Test query classification (`query_router.py`):
  * `STRUCTURED`: Numerical aggregations, subsidiary comparisons
  * `DOCUMENT`: Narrative, exploration, geological descriptions
  * `HYBRID`: Combined metric + qualitative facts
* Verify multi-tenant BM25 retrieval (`retriever.py`) ensuring zero cross-user chunk leakage.
* Verify prompt injection defense in `answer_engine.py` (passive XML data isolation).
* Verify deterministic offline synthesis fallback when LLM API key is absent or unreachable.
* Verify traceable source citation cards (Document title, Page #, Table/Section reference, Confidence).

#### 3. Files / Modules Affected
* **Existing Modules:** `backend/apps/intelligence/` (models, router, retrieval, generator, indexer, views).
* **Frontend:** AI Query interface in `index.html`.

#### 4. Dependencies on Previous Phases
* Depends on Phase 3 extracted document chunks and Phase 4 validated records.

#### 5. Acceptance Criteria
* All 22 tests in `apps.intelligence` pass.
* Numerical question (e.g. "What was SECL production in FY 2023-24?") executes exact database calculation.
* Qualitative question retrieves matching chunks with source cards.
* Questions with no matching evidence return: *"I could not find sufficient evidence in the available project data."*

#### 6. Testing Checklist
* [ ] `./venv/Scripts/python.exe backend/manage.py test apps.intelligence`
* [ ] Test query routing for structured, document, and hybrid prompts.
* [ ] Test multi-tenant isolation with two separate user accounts.
* [ ] Test offline synthesis fallback by disabling network connection.

#### 7. What Must NOT Be Changed
* Do NOT allow external LLM to fabricate numerical figures not in database.
* Do NOT expose another user's documents in retrieval results.

#### 8. Expected Output / Demo Result
* Grounded AI chat response displaying badge (`STRUCTURED`/`DOCUMENT`/`HYBRID`), confidence indicator, and clickable source cards with exact page numbers.

---

### PHASE 6: Dynamic Dashboard + Analytics + Data Explorer

#### 1. Goal
Establish live structured data as the Single Source of Truth across the platform by connecting both the main Dashboard and Analytics screens to the backend query engine.

#### 2. Features to Implement / Reconcile
* **Connect Main Dashboard to Backend API:**
  * Re-wire `pageDashboard()` and `afterDashboard()` in `index.html` to fetch real metrics from `GET /api/analytics/kpi/` and `GET /api/analytics/trends/`.
  * Replace hardcoded numbers ("1,047.52 MT", "781.06 MT", "2,450", "876") with dynamic values calculated from `StructuredRecord` database rows.
  * Keep fallback to mock data only when backend is offline.
* **Verify Analytics Query Engine:**
  * Chronological financial year sorting (`2021-22`, `2022-23`, `2023-24`, `2024-25`).
  * Dynamic KPIs (production, dispatch, target, achievement %, growth %, active mines).
  * Subsidiary production breakdown & coal grade distribution charts.
  * Interactive chart drill-down modal showing exact source records.
* **Verify Data Explorer:**
  * Server-side search, filtering by subsidiary/FY/sheet, sorting, pagination.
  * Detailed record inspection modal displaying full JSON and `ExtractionProvenance`.
  * Filtered CSV export (`GET /api/datasets/<id>/export/csv/`).

#### 3. Files / Modules Affected
* **Existing Files to Modify:**
  * `index.html` and `backend/templates/frontend/index.html` (`pageDashboard()`, `afterDashboard()` API wiring)
* **Existing Modules:**
  * `backend/apps/analytics/` (query engine, views, urls)
  * `backend/apps/datasets/` (views, serializers)

#### 4. Dependencies on Previous Phases
* Depends on Phase 3 extraction and Phase 4 structured data records.

#### 5. Acceptance Criteria
* Main Dashboard KPI cards display real calculated figures matching database records.
* All 19 tests in `apps.analytics` pass.
* All 7 tests in `apps.datasets` pass.
* Data Explorer filters and searches records in real-time with pagination.

#### 6. Testing Checklist
* [ ] `./venv/Scripts/python.exe backend/manage.py test apps.analytics apps.datasets`
* [ ] Verify Dashboard KPI numbers match `AnalyticsQueryEngine.calculate_kpis()` output.
* [ ] Verify chart drill-down displays exact provenance.
* [ ] Test Data Explorer CSV export with active filters.

#### 7. What Must NOT Be Changed
* Do NOT break offline demo fallback when backend is unreachable.
* Do NOT include records flagged with `ERROR` validation in production analytics.

#### 8. Expected Output / Demo Result
* Main dashboard immediately updates when new documents are uploaded or maintainer fixes are applied.

---

### PHASE 7: Real Report Generator

#### 1. Goal
Activate official, production-quality report generation with real PDF, DOCX, and XLSX document downloads across 8 mining report types with full governance review and approval.

#### 2. Features to Implement / Reconcile
* Install `reportlab` in `./venv` to enable real binary PDF export.
* Reconcile report export endpoints:
  * `GET /api/reports/<id>/export/pdf/` (ReportLab canvas, custom headers/footers, styled tables, numbered pages, sign-off blocks)
  * `GET /api/reports/<id>/export/docx/` (python-docx formatted tables and callout callouts)
  * `GET /api/reports/<id>/export/xlsx/` (openpyxl multi-tab workbooks with summary, data, and provenance)
* Verify 8 Roadmap Report Types:
  1. Production Report (production, dispatch, target, achievement, YoY growth)
  2. Geological Exploration Report (basins, coal grades G1-G17, coking status)
  3. Mining Performance Report (asset variance, dispatch efficiency)
  4. Exploration Report (blocks, drilling status, UNFC/ISP findings)
  5. Coal Seam Analysis Report (quality parameters, modal grades)
  6. Parliamentary Question Response (official Starred/Unstarred format + Annexure)
  7. Administrative Query Report (internal compliance, ledger audit)
  8. Custom Report (multi-source synthesis)
* Verify Report Lifecycle: `DRAFT → GENERATED → UNDER_REVIEW → VERIFIED → APPROVED → EXPORTED`.
* Verify in-place narrative editing and governance verification/approval remarks.

#### 3. Files / Modules Affected
* **Environment:** `./venv` (`pip install reportlab`).
* **Existing Modules:** `backend/apps/reports/` (models, services, exporters, views).
* **Frontend:** Report Generator 5-step wizard and viewer in `index.html`.

#### 4. Dependencies on Previous Phases
* Depends on Phase 3 (`python-docx`, `openpyxl`), Phase 5 (intelligence chunks), Phase 6 (analytics query engine).

#### 5. Acceptance Criteria
* All 17 tests in `apps.reports` pass.
* `test_export_pdf`, `test_export_docx`, and `test_export_xlsx` return HTTP 200 with valid binary MIME types (`application/pdf`, etc.).
* Generating any of the 8 report types produces a complete, factual document grounded in project data.
* Narrative edits increment revision count and set status to `UNDER_REVIEW`.

#### 6. Testing Checklist
* [ ] `./venv/Scripts/python.exe backend/manage.py test apps.reports`
* [ ] Generate each of the 8 report types via API.
* [ ] Download and verify PDF binary rendering and page numbering.
* [ ] Download and verify DOCX formatting.
* [ ] Download and verify XLSX multi-tab structure.

#### 7. What Must NOT Be Changed
* Do NOT fabricate missing data; reports must state: *"Data not available in selected sources."*
* Do NOT allow unauthorized users to approve or verify reports.

#### 8. Expected Output / Demo Result
* Fully formatted official PDF and DOCX reports with CMPDI headers, executive summaries, data tables, and signature sign-offs ready for presentation.

---

### PHASE 8: Topics + Word Cloud + Mining Map + 3D Geological View

#### 1. Goal
Verify and showcase spatial intelligence, dynamic topic modeling, and 3D geological strata visualization using verified Indian coal mining datasets.

#### 2. Features to Implement / Reconcile
* **Topics & Word Cloud:**
  * Dynamic TF-IDF topic modeling over real indexed `DocumentChunk` records.
  * Frequency-weighted word cloud generation (`GET /api/phase8/topics/wordcloud/`).
  * Topic list with associated documents (`GET /api/phase8/topics/topics/`).
* **Mining Map:**
  * 107 verified Indian coal mine locations with WGS-84 coordinates across 8 subsidiaries.
  * Subsidiary, state, and mine-type filtering (`GET /api/phase8/map/filters/`).
  * Interactive SVG map pins with details tooltips and production statistics.
* **3D Geological Strata View:**
  * 1,075 GSI exploration reports catalog and 2,226 OCBIS coal block records.
  * Interactive 3D cross-section visualization of coal seams, sandstone, shale, and overburden.
  * Seam thickness and depth exploration controls.

#### 3. Files / Modules Affected
* **Existing Modules:** `backend/apps/phase8/` (models, services, views, urls, data).
* **Frontend:** Topics, Map, and 3D Geology tabs in `index.html`.

#### 4. Dependencies on Previous Phases
* Depends on Phase 5 document chunks for dynamic topic modeling.

#### 5. Acceptance Criteria
* All 26 tests in `apps.phase8` pass.
* Mining map displays 107 verified mines correctly pinned within Indian borders.
* 3D Geological view renders interactive strata cross-section with real borehole depth parameters.
* Topics and word cloud reflect real text terms extracted from uploaded documents.

#### 6. Testing Checklist
* [ ] `./venv/Scripts/python.exe backend/manage.py test apps.phase8`
* [ ] Verify map filter controls (SECL, MCL, ECL, etc.) update pins dynamically.
* [ ] Verify 3D strata view responds to layer depth toggle.

#### 7. What Must NOT Be Changed
* Do NOT replace verified 107 mine coordinates with random mock numbers.
* Do NOT claim simulated 3D strata is a real-time live borehole survey without labeling.

#### 8. Expected Output / Demo Result
* Visually striking interactive map and 3D strata cross-section providing high-impact demonstration value for SIH evaluators.

---

### PHASE 9: Human Review + Approval + Audit Trail

#### 1. Goal
Replace the stubbed audit API with a real, authenticated audit log service and provide a transparent governance dashboard tracking every administrative, data maintenance, and AI decision.

#### 2. Features to Implement / Reconcile
* **Implement Real Audit API (`apps/audit/views.py`):**
  * Replace `audit_list_stub` with a real `GET /api/audit/` endpoint.
  * Enforce `IsAuthenticated` and user/role permissions.
  * Provide query filtering by: `event_type`, `actor`, `resource_type`, `date_from`, `date_to`.
  * Support server-side pagination and reverse chronological ordering.
* **Connect Frontend Audit Trail (`index.html`):**
  * Update `pageAudit()` and `afterAudit()` to fetch real audit events via `apiServices.audit.list()`.
  * Display actor username, client IP, action type, resource reference, and timestamp.
  * Add live filter dropdowns (by action type and user).
* **Unified Review & Approval Governance:**
  * Link Data Maintainer suggestion approvals and Report approvals directly into the Audit Trail.
  * Provide audit event detail modal displaying `metadata_json` (e.g. before/after values, approval notes).

#### 3. Files / Modules Affected
* **Existing Files to Modify:**
  * `backend/apps/audit/views.py` (replace stub with real list view)
  * `backend/apps/audit/serializers.py` (complete DRF serializer for `AuditEvent`)
  * `backend/apps/audit/tests.py` (comprehensive audit API test cases)
  * `index.html` and `backend/templates/frontend/index.html` (`afterAudit()` API wiring)

#### 4. Dependencies on Previous Phases
* Depends on Phase 2, 4, 5, and 7 audit event creators.

#### 5. Acceptance Criteria
* `GET /api/audit/` returns real paginated `AuditEvent` records with HTTP 200.
* Unauthenticated requests to `/api/audit/` receive HTTP 401.
* Audit table in UI populates with real events (uploads, maintenance approvals, AI queries, report generations).
* Original audit records remain strictly immutable (no update or delete APIs).

#### 6. Testing Checklist
* [ ] `./venv/Scripts/python.exe backend/manage.py test apps.audit`
* [ ] Perform a document upload and maintainer approval; verify events appear in `/api/audit/`.
* [ ] Verify audit log filtering by event type and user.

#### 7. What Must NOT Be Changed
* Do NOT implement any endpoint that allows editing or deleting `AuditEvent` records.

#### 8. Expected Output / Demo Result
* Fully functional enterprise audit trail showing an unalterable history of every human review, AI query, and system change.

---

### PHASE 10: UI/UX Polish + Complete End-to-End Testing

#### 1. Goal
Achieve a 100% test pass rate across the entire repository test suite, eliminate all visual bugs and console errors, and ensure seamless full-stack user flows.

#### 2. Features to Implement / Reconcile
* Run the complete test suite across all 12 apps and verify 100% pass rate (target: 250+ tests passing, 0 failures, 0 errors).
* Verify UI responsiveness across standard desktop displays (1920x1080, 1440x900, 1366x768).
* Audit all user feedback mechanisms (toast notifications, loading spinners, empty states, error banners).
* Ensure smooth navigation transitions between all 11 pages without page reloads.
* Clean up any obsolete temporary debug code or commented test snippets.

#### 3. Files / Modules Affected
* All apps, templates, and static assets across the repository.

#### 4. Dependencies on Previous Phases
* Depends on Phases 1 through 9.

#### 5. Acceptance Criteria
* `python manage.py test apps` passes 100% with 0 failures and 0 errors.
* End-to-end user journey works flawlessly:
  1. Login as `admin`
  2. Upload mining production document
  3. Inspect extracted data in Data Explorer
  4. Fix formatting issue in Data Maintainer and apply changes
  5. Ask AI question and receive grounded answer with citation
  6. Review live KPIs on Dashboard and trend charts on Analytics
  7. Generate, verify, approve, and download official PDF report
  8. Verify entire sequence recorded in Audit Trail.

#### 6. Testing Checklist
* [ ] Full regression test suite execution: `./venv/Scripts/python.exe backend/manage.py test apps --keepdb`
* [ ] Manual E2E walkthrough of the 8-step journey above.
* [ ] Verify browser console is free of uncaught errors or failed network requests.

#### 7. What Must NOT Be Changed
* Do NOT introduce breaking changes to existing models or APIs.

#### 8. Expected Output / Demo Result
* Flawless, production-grade application ready for evaluation and live demonstration.

---

### PHASE 11: SIH Demo Mode + Final Preparation

#### 1. Goal
Provide a foolproof, turnkey demonstration environment capable of running seamlessly either fully online (with live AI) or completely offline/air-gapped (with deterministic demo fallbacks).

#### 2. Features to Implement / Reconcile
* **Single Turnkey Setup Command:**
  * Create/verify `python manage.py setup_demo_environment` that orchestrates:
    * Seeding dev admin user (`seed_dev_user`)
    * Seeding sample multi-year mining production datasets (`seed_sample_mining_data`)
    * Seeding 107 verified mines, GSI reports, and OCBIS blocks (`seed_phase8_data`)
* **Air-Gapped / Offline Fallback Assurance:**
  * Verify UI gracefully indicates when backend is connected vs offline.
  * Verify AI Query uses deterministic synthesis fallback when external LLM API is unavailable.
  * Verify all charts, maps, and reports render rich data immediately upon initial launch.
* **Evaluation Presentation Kit:**
  * Quickstart guide in README for judges.
  * 5-minute live pitch demonstration script highlighting CMPDI/CIL problem solving, multi-tenancy, provenance, and auditability.

#### 3. Files / Modules Affected
* `backend/apps/core/management/commands/setup_demo_environment.py` (new convenience orchestrator)
* `README.md` (quickstart documentation)

#### 4. Dependencies on Previous Phases
* Depends on all previous phases (Phases 1 to 10).

#### 5. Acceptance Criteria
* Running `python manage.py setup_demo_environment` sets up a complete, fully populated demo database in under 15 seconds.
* Launching `python manage.py runserver` and opening `http://127.0.0.1:8000/` provides a jaw-dropping, fully interactive demo.
* Disconnecting internet completely does not crash or break any core screen.

#### 6. Testing Checklist
* [ ] Test clean setup command on fresh temporary test database.
* [ ] Test application in simulated offline mode (no internet access).
* [ ] Rehearse 5-minute judge demonstration script.

#### 7. What Must NOT Be Changed
* Do NOT delete actual project data or overwrite user documents.

#### 8. Expected Output / Demo Result
* Winning SIH 2026 presentation state with zero setup friction and flawless execution.

---

## 11. Controlled Execution Rules

1. **One Phase at a Time:** Only ONE phase will ever be implemented in a single turn.
2. **Explicit User Approval Required:** Work on Phase `N` will only commence when the user provides explicit written authorization (e.g. *"Approve Phase 1"*).
3. **No Automatic Chaining:** The agent will NEVER automatically proceed to Phase `N+1` after completing Phase `N`.
4. **Mandatory Post-Phase Reporting:** After completing each approved phase, the agent will:
   * Run relevant unit and integration tests.
   * Run Django system checks (`python manage.py check`).
   * Inspect git diff and git status.
   * Report changed files, created files, test results, and known issues.
   * **STOP and wait for explicit user approval before the next phase.**
