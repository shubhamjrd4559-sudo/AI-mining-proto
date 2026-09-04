# SIH 2026 Implementation Roadmap

## Project overview

**Project:** SIH26023 — AI-Powered Geological, Mining and other Reporting Solution for CMPDI/CIL subsidiaries.

This roadmap converts the existing polished static prototype into a reliable, demonstrable full-stack application without discarding its visual identity. Work must proceed one phase at a time, preserving a runnable demo and an offline fallback throughout.

## Final architecture

- **Frontend:** preserve `index.html` as the visual baseline; gradually modularize its vanilla HTML/CSS/JavaScript without forcing React during the six-day prototype.
- **Backend:** Python Django + Django REST Framework (DRF), REST API, modular monolith. No microservices, Kubernetes, or unnecessary enterprise infrastructure.
- **Database:** SQLite for the prototype; Django models/migrations and portable relational design ready for PostgreSQL. MongoDB is optional, not required.
- **Storage:** local media/file storage initially, behind a storage abstraction for future object storage.
- **AI:** provider abstraction; grounded RAG; deterministic Demo Mode when external AI is unavailable.
- **Deployment:** keep the current static GitHub Pages workflow only for the current prototype. Before adding Django backend content, deploy frontend/static output separately from backend/runtime/media content.

## Core data flow

```text
Upload PDF / scanned PDF / DOCX / XLSX / CSV / TXT / PNG/JPG
  -> processing
  -> extraction/OCR
  -> schema detection
  -> validation
  -> canonical structured data
  -> AI Excel/CSV Maintainer
  -> Mining AI/RAG
  -> dynamic Dashboard and Analytics
  -> Data Explorer
  -> Report Generator
  -> Human Review/Approval
  -> Audit Trail
```

## Single-source-of-truth principle

Canonical structured processed data is the single source of truth for Dashboard, Analytics, Data Explorer, AI/RAG, Excel/CSV Maintainer, Reports, Topics/Word Cloud, Mining Map, 3D Geological View, and Audit Trail. Original uploaded files remain immutable evidence. Every derived record must retain document, page, section/table/row, extraction method, validation state, and revision provenance. Demo fixtures must follow the same API/data contracts.

## Team ownership boundaries

| Owner | Primary responsibility |
| --- | --- |
| Frontend | Existing UI preservation, page modules, API adapters, loading/error/review states, visual regression checks. |
| Backend | Django/DRF, models, APIs, permissions foundation, storage abstraction, job states. |
| Data Processing | Extraction, OCR, schema detection, normalization, validation, provenance. |
| Excel/CSV Maintainer | Spreadsheet rules, corrections workflow, revisions, import/export contracts. |
| AI/RAG | Provider/retrieval abstraction, citations, Demo Mode, evaluation fixtures. |
| Reports | Templates, generation/review/approval/export pipeline. |
| Testing/Integration | Contracts, end-to-end scenarios, fixture reset, demo rehearsal, release checklist. |

## 6-day recommended execution schedule

| Day | Phases | Outcome |
| --- | --- | --- |
| 1 | Phase 1 | Full-stack foundation while retaining the visual baseline. |
| 2 | Phases 2–3 | Real uploads through structured, validated data. |
| 3 | Phases 4–5 | Spreadsheet maintainer and grounded AI/RAG vertical slices. |
| 4 | Phases 6–7 | Dynamic data views and real report generation. |
| 5 | Phases 8–9 | Lightweight enrichment visuals plus review/audit workflow. |
| 6 | Phases 10–11 | Stabilization, end-to-end verification, and a judge-ready Demo Mode. |

---

## PHASE 1 — Full-Stack Foundation + Existing UI Integration

### Goal

Create the Django/DRF modular-monolith foundation and a frontend service boundary while preserving the current `index.html` UI and its offline behavior.

### Features to implement

- Establish Django project/configuration and DRF API structure.
- Configure SQLite, media storage abstraction, environment settings, CORS, and `/api/health/`.
- Add initial models for Document, ProcessingJob, StructuredDataset/Record, AuditEvent, and user/role foundation.
- Introduce frontend API/service adapters and fixture repositories without redesigning existing pages.
- Define shared request/response examples and a team-friendly folder structure.
- Keep OCR, RAG, report generation, and spreadsheet intelligence unimplemented at this stage.

### Files/modules likely affected

- `backend/config/`, `backend/apps/documents/`, `backend/apps/structured_data/`, `backend/apps/audit/`, `backend/apps/users/`, `backend/common/`
- `frontend/` modules created by safe extraction only; `shared/` API contracts; `docs/` setup/contracts; `.env.example`
- Preserve root `index.html` as baseline.

### Dependencies on previous phases

- None.

### Acceptance criteria

- Django/DRF starts with SQLite and `GET /api/health/` returns a documented healthy response.
- Media/config values come from environment configuration, not committed secrets.
- Initial migrations run cleanly on a new local database.
- Existing prototype remains visually/functionally runnable in fixture mode.

### Testing checklist

- Health endpoint test; migration smoke test; CORS/config tests.
- API contract fixture validation.
- Existing ten-view navigation and visual baseline smoke test.

### What must NOT be changed

- Do not rewrite or remove `index.html`, alter its visual language, or force a React migration.
- Do not implement OCR/RAG/reports beyond interfaces and placeholders with truthful labels.
- Do not replace static GitHub Pages with a backend deployment in this phase.

### Expected output/demo result

The original interface still works, with a health-checked Django/DRF foundation ready for incremental feature wiring.

---

## PHASE 2 — Real Document Upload + Storage

### Goal

Replace simulated upload entry points with a real, safe upload and document-status workflow.

### Features to implement

- Support PDF, scanned PDF, DOCX, XLSX, CSV, TXT, PNG, and JPG.
- Implement drag/drop, select-file, multiple upload, validation, metadata capture, local media storage, progress/status, retry/reprocess, delete policy, and immutable original files.
- Create document and processing-job APIs; show real status in the existing Documents UI.
- Validate file type, size, count, and filename safely; expose useful error/retry states.

### Files/modules likely affected

- `backend/apps/documents/`, `backend/apps/processing/`, `backend/common/storage/`
- Frontend Documents feature/service adapter; contracts and upload tests.

### Dependencies on previous phases

- Phase 1 health/API/model/storage foundations.

### Acceptance criteria

- Each supported file type can be uploaded, stored, listed, and shown with metadata/status.
- Multiple files create separate immutable document records/jobs.
- Retry/reprocess creates a new processing attempt without overwriting the original.
- Delete behavior is explicit, authorized, and audit-ready; never silently deletes evidence.

### Testing checklist

- Valid/invalid type, size, empty file, duplicate filename, multiple upload, failed upload, retry, and refresh persistence.
- Drag/drop and keyboard upload paths; media access restrictions.

### What must NOT be changed

- Do not fake successful upload, processing, or download.
- Do not mutate original uploads or store them inside source directories.
- Do not remove fixture-mode upload simulation until the real path has a reliable fallback.

### Expected output/demo result

A user uploads representative documents and sees real persisted document metadata and truthful processing states.

---

## PHASE 3 — Extraction + OCR + Schema Detection + Validation

### Goal

Produce traceable canonical structured data from uploaded documents without changing original evidence.

### Features to implement

- Implement PDF text/table extraction; OCR for scanned PDF/images; DOCX text/table extraction; XLSX/CSV parsing.
- Add schema detection, mining/geological field detection, normalization, validation, and document detail information.
- Persist extraction results, pages, chunks, tables, normalized records, confidence/method metadata, validation findings, and provenance.
- Create asynchronous/job-state boundary and error/reprocess path.

### Files/modules likely affected

- `backend/apps/processing/`, `backend/apps/structured_data/`, `backend/apps/documents/`, extraction adapters in `backend/common/`
- Documents detail UI/API adapter; fixtures/schemas/data dictionary; processing tests.

### Dependencies on previous phases

- Phase 2 documents, storage, job status, and file validation.

### Acceptance criteria

- At least one representative PDF and one XLSX/CSV produce persisted structured records.
- Scanned material reports OCR method/confidence and failure state honestly.
- Each structured record links to its original document and available page/section/table/row source.
- Validation findings do not overwrite originals and can be reviewed later.

### Testing checklist

- Text PDF, scanned PDF/image, DOCX, XLSX, CSV, malformed/empty input, unsupported schema, and reprocess cases.
- Provenance integrity and schema-normalization tests.

### What must NOT be changed

- Never silently modify original files, invent pages/sources, or claim OCR/extraction succeeded when it failed.
- Do not hard-code the UI around a single document layout.

### Expected output/demo result

An uploaded document moves through real processing to validated, source-traceable structured data visible in document detail.

---

## PHASE 4 — AI Excel/CSV Maintainer

### Goal

Make spreadsheet/CSV maintenance a first-class reviewable workflow over canonical structured data.

### Features to implement

- Detect missing values, duplicates, invalid values/dates, inconsistent units/names, outliers, and suspicious values.
- Generate rule-based and AI-assisted suggestions with confidence and clear reasoning/source context.
- Provide Accept, Reject, Edit, and Accept All Safe Changes controls.
- Maintain revision history, audit events, validation state, and real XLSX/CSV export.
- Support multiple schemas through schema profiles/field mappings, not hard-coded spreadsheet columns.

### Files/modules likely affected

- `backend/apps/spreadsheet_maintainer/`, `structured_data/`, `audit/`, export adapters
- Frontend Data Explorer/Maintainer views and services; schema fixtures; tests.

### Dependencies on previous phases

- Phase 3 canonical records, validation results, and provenance.

### Acceptance criteria

- A CSV/XLSX dataset produces reviewable findings and proposed corrections.
- Accepted changes create a new revision; rejected/edited changes are retained with actor/reason.
- “Accept All Safe Changes” applies only documented high-confidence, non-destructive rules.
- Exports contain the selected revision and traceable source/revision metadata.

### Testing checklist

- Missing/duplicate/unit/date/name/outlier cases; accept/reject/edit/all-safe; export/re-import; revision/audit integrity.

### What must NOT be changed

- Do not alter originals, apply opaque AI changes automatically, or constrain the module to a single fixed schema.
- Do not display suggestions as verified facts before human review.

### Expected output/demo result

A judge can review spreadsheet findings, accept or edit corrections, inspect history, and download a real corrected export.

---

## PHASE 5 — Real Mining Intelligence AI / RAG

### Goal

Replace the mock chatbot with grounded answers and truthful source traceability.

### Features to implement

- Introduce AI-provider and retrieval abstractions plus deterministic Demo Mode.
- Use structured database queries for numerical questions, document retrieval for document questions, and hybrid retrieval when needed.
- Return answer, document/page/section/table citations, confidence/limitations, source cards, source preview, loading/error/retry, and chat history.
- Ensure unsupported/insufficient-data questions say so rather than fabricate sources or pages.

### Files/modules likely affected

- `backend/apps/ai_rag/`, `structured_data/`, `documents/`, provider/retrieval adapters
- AI Query frontend/service; source preview component; curated evaluation fixtures/tests.

### Dependencies on previous phases

- Phase 3 source chunks/structured data; Phase 4 reviewed spreadsheet revisions where relevant.

### Acceptance criteria

- Demo numerical and document questions answer from uploaded/processed data with valid citations.
- Citation links resolve to stored source metadata/preview.
- Provider failure/network absence reliably falls back to deterministic Demo Mode, clearly labelled.

### Testing checklist

- Numerical, document, hybrid, no-result, conflicting-source, provider-error, retry, and citation-integrity tests.

### What must NOT be changed

- Do not retain the current hard-coded answer/fabricated-confidence behavior for live mode.
- Do not send sensitive documents to a provider without an explicit configured policy.

### Expected output/demo result

A Mining AI question receives an evidence-grounded answer with a usable source trail, or an honest no-answer/fallback response.

---

## PHASE 6 — Dynamic Dashboard + Analytics + Data Explorer

### Goal

Drive the existing dashboard, analytics, and Explorer from canonical structured data instead of hard-coded values wherever real data exists.

### Features to implement

- Build analytics/read-model APIs from processed records and reviewed revisions.
- Implement dynamic KPIs, production trends, subsidiary/state/mine analysis, geological charts where applicable, filters, search, sorting, pagination, row details, and source references.
- Implement real CSV/XLSX export for Explorer results.
- Make charts adapt to detected dataset structure and visibly handle absent/incomplete fields.

### Files/modules likely affected

- `backend/apps/analytics/`, `structured_data/`, `spreadsheet_maintainer/`
- Dashboard, Analytics, Data Explorer frontend adapters/charts/tables; contract/visual tests.

### Dependencies on previous phases

- Phase 3 canonical data; Phase 4 approved revisions; Phase 5 only for optional explanatory AI actions.

### Acceptance criteria

- At least one upload-to-dashboard and upload-to-Explorer data path is live.
- Filters and exports operate on actual API data.
- Every displayable row/metric can expose its source references.
- Empty state replaces invented hard-coded metrics where no real dataset applies; Demo Mode remains explicit.

### Testing checklist

- API aggregation, filter/search/sort/page boundaries, chart empty/error/data states, export fidelity, and source-reference checks.

### What must NOT be changed

- Do not redesign CMPDI visual identity or replace custom charts unnecessarily.
- Do not display fake “official” values as real data after live mode is wired.

### Expected output/demo result

Uploading and processing sample data changes Dashboard, Analytics, and Explorer views with traceable values.

---

## PHASE 7 — Real Report Generator

### Goal

Preserve the existing Report Generator experience while producing reviewable, source-referenced files from real structured data.

### Features to implement

- Support Production, Geological & Exploration, Mining Performance, Exploration, Coal Seam Analysis, Parliamentary Question Response, Administrative Query, and Custom Report types.
- Implement Select -> Configure -> Generate -> Review -> Edit -> Verify -> Approve -> Export workflow.
- Generate PDF, DOCX, and XLSX where applicable; store output and report version metadata.
- Include actual processed/indexed data, source references, validation/review status, and truthful warnings for missing evidence.

### Files/modules likely affected

- `backend/apps/reports/`, `structured_data/`, `audit/`, render/export adapters
- Existing Report Generator frontend/service and report preview/review components; templates/tests.

### Dependencies on previous phases

- Phase 3 canonical data; Phase 4 revisions; Phase 6 analytics read models; Phase 9 approval rules can be introduced as a minimal report-specific precursor if required.

### Acceptance criteria

- One representative report type generates a real downloadable file from sample processed data.
- Report citations map to source records; preview/review/approval statuses persist.
- Unsupported report/data combinations fail with clear user guidance rather than fake success.

### Testing checklist

- Every output format, missing-data behavior, citation check, preview/download authorization, and render verification.

### What must NOT be changed

- Do not replace the existing wizard UX or claim a report was generated unless a file exists.
- Do not include unverifiable AI prose or citations.

### Expected output/demo result

A user configures, reviews, approves, and downloads a real source-referenced report.

---

## PHASE 8 — Topics + Word Cloud + Mining Map + 3D Geological View

### Goal

Enrich the prototype with lightweight data-driven visualizations without risking the core flow.

### Features to implement

- Derive topics, keywords, frequency, related documents, filters, and source references from indexed text.
- Use real coordinates for Mine Map where available; otherwise label all display coordinates as demo/simulated.
- Preserve the 3D geological visual concept; bind real layers/attributes only when data exists, otherwise label the model as simulated/demo.
- Retain safe fallback fixtures for all three views.

### Files/modules likely affected

- `backend/apps/analytics/`, `structured_data/`, optional geospatial read-model adapters
- Topics, Map, and 3D frontend modules; visualization fixtures/tests.

### Dependencies on previous phases

- Phase 3 indexed text/structured data and Phase 6 read-model APIs.

### Acceptance criteria

- Topics and word cloud use actual indexed text for the curated corpus.
- Map/3D clearly distinguish real from simulated data.
- Failure or absent geospatial/geological inputs cannot block upload, AI, analytics, reports, or audit demo paths.

### Testing checklist

- Topic reproducibility/filter/source links; missing-coordinate labels; layer/control interactions; responsive visual smoke tests.

### What must NOT be changed

- Do not introduce heavy GIS/3D platforms or let these stretch features delay P0.
- Do not portray decorative coordinates/models as verified field data.

### Expected output/demo result

Supporting visual pages are informative, source-aware, and explicitly honest about any simulation.

---

## PHASE 9 — Human Review + Approval + Audit Trail

### Goal

Add a consistent human-in-the-loop governance path for consequential generated or corrected data.

### Features to implement

- Implement states: AI Generated -> Under Review -> Edited -> Verified -> Approved -> Exported.
- Apply states where relevant to extraction, validation corrections, Excel Maintainer changes, reports, and important AI outputs.
- Record user, action, entity, previous/new state, changes, timestamp, reason, source, and revision.
- Expose Audit Trail filters and item detail from real audit events.

### Files/modules likely affected

- `backend/apps/audit/`, `documents/`, `structured_data/`, `spreadsheet_maintainer/`, `reports/`, `ai_rag/`
- Existing Audit Trail frontend/service; shared status components; audit tests.

### Dependencies on previous phases

- Phase 2 immutable documents; Phases 3–7 entity/revision workflows.

### Acceptance criteria

- Meaningful actions create immutable, queryable audit events.
- Approval/export permissions and state transitions are enforced by backend rules.
- Original uploads remain immutable; derived revisions are explicit.

### Testing checklist

- Allowed/disallowed state transitions; before/after capture; actor/reason capture; audit filtering; report/export audit events.

### What must NOT be changed

- Do not log sensitive file contents unnecessarily or permit UI-only status changes without an auditable API action.
- Do not mutate original documents.

### Expected output/demo result

The demo shows a correction/report moving through review and approval with a truthful Audit Trail.

---

## PHASE 10 — UI/UX Polish + Complete End-to-End Testing

### Goal

Make the implemented P0 flow stable, clear, accessible, and demonstrably real without redesigning the product.

### Features to implement

- Preserve CMPDI/Mining Intelligence visual identity.
- Add/refine responsive, loading, empty, error, retry, upload-progress, notification, accessibility, console-error, broken-link, and truthful-success states.
- Remove or replace obvious fake success messages/interactions only once real equivalents and Demo Mode states exist.
- Fix critical bugs only; do not add large features.

### Files/modules likely affected

- Frontend feature modules/styles/tests; backend integration tests; `tests/`; demo fixtures and docs.

### Dependencies on previous phases

- P0 vertical slices from Phases 1–7 and governance from Phase 9.

### Acceptance criteria

- The full curated happy path completes without console errors or false success claims.
- Core pages remain responsive at baseline breakpoints.
- Known failure/offline conditions are understandable and recoverable.

### Testing checklist

- Upload PDF -> upload XLSX/CSV -> process -> extract -> validate -> review -> Maintainer accept/reject -> export -> AI query/source verification -> Analytics -> Explorer/export -> report PDF/DOCX -> approve -> Audit Trail.
- Check keyboard navigation, mobile layouts, broken links, error/retry, fixture reset, and no-network Demo Mode.

### What must NOT be changed

- Do not redesign navigation/pages or start non-critical feature work.
- Do not hide known limitations behind fake loading/success states.

### Expected output/demo result

A reliable, rehearsed end-to-end workflow with clear state, evidence, and recovery behavior.

---

## PHASE 11 — SIH Demo Mode + Final Preparation

### Goal

Deliver a dependable 3–5 minute judging demonstration that works even when external services fail.

### Features to implement

- Prepare deterministic Demo Mode, fixture reset, and an explicit demo/live status indicator.
- Curate a small representative dataset: PDF, scanned PDF if available, XLSX, CSV, mining/production data, and geological/report data.
- Rehearse: Dashboard -> Upload -> Processing -> Extraction -> Validation -> Human Review -> Excel AI Maintainer -> Mining AI -> Source Traceability -> Dynamic Analytics -> Explorer -> Report -> Approve -> Download -> Audit Trail.
- Label demo/simulated data and limitations clearly; remove obvious unfinished placeholders and fake downloads/interactions.
- Prepare a concise demo script, fallback path, known-limitations list, and final runbook.

### Files/modules likely affected

- `data/fixtures/`, approved `data/samples/`, demo configuration/docs, tests, and only the already-implemented frontend/backend feature modules needed for Demo Mode.

### Dependencies on previous phases

- Phase 10 stabilized P0 flow; Phase 8 visual enrichments only if stable.

### Acceptance criteria

- A clean machine/session can run the curated demo offline or with unavailable external AI.
- Demo data resets predictably and all main claims are truthful.
- The complete run fits in 3–5 minutes, with an alternate path for a failed upload/provider.

### Testing checklist

- Two complete rehearsals from clean state; offline/provider-failure rehearsal; timing rehearsal; artifact/download verification; source/citation spot check.

### What must NOT be changed

- Do not add scope, large datasets, cloud complexity, or untested integrations immediately before judging.
- Do not remove reliable fixture mode in favor of a fragile live-only path.

### Expected output/demo result

A small, polished, repeatable SIH demo proving the P0 flow: Upload -> Extraction -> Validation -> Excel Maintainer -> AI/RAG -> Analytics -> Report -> Audit.

## Delivery priorities

- **P0 — Must work:** Upload -> Extraction -> Validation -> Excel Maintainer -> AI/RAG -> Analytics -> Report -> Audit.
- **P1 — Strong demo:** Topics -> Word Cloud -> Mining Map -> 3D Geological View.
- **P2 — Future:** advanced GIS, large-scale OCR, complex authentication, cloud scaling, and other non-demo-critical work.

## Implementation Rule

Antigravity must complete only one phase at a time. After each phase it must run tests, report changed files, test results, known issues and remaining work, then STOP and wait for explicit approval before starting the next phase.
