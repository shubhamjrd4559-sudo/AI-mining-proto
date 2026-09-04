# SIH 2026 Frontend Structure Audit and Plan

## 1. Executive Summary

This repository is a polished, single-file browser prototype. Its visual design and a substantial amount of useful interaction are concentrated in `index.html` (119,559 bytes); the only other tracked project file is a minimal `README.md`. The prototype is intentionally dependency-free apart from Google-hosted fonts, and renders its views, charts, map, geological scenes, tables, data, and interactions in vanilla HTML/CSS/JavaScript.

The safest six-day approach is **not** a rewrite. Preserve `index.html` as the visual baseline, keep it runnable at every step, and gradually extract stable seams: mock data, page renderers, SVG visual builders, shared UI utilities, and styles. Introduce one small modular frontend plus one modular-monolith API only when a team member is ready to connect a real vertical slice. Do not use microservices, Kubernetes, separate databases per feature, or a React migration during the initial demo-critical work.

Recommended eventual shape: a repository-level Django/Django REST Framework modular monolith with a preserved prototype, a frontend UI layer, one backend/API, asynchronous processing adapters, a first-class Excel/CSV Maintainer module, clearly separated data/AI/report modules, shared API contracts, documentation, and tests. SQLite is the initial database, designed to be PostgreSQL-ready. React may be evaluated after the demo baseline is protected; it is not necessary to achieve a stable SIH prototype.

## 2. Current Repository Structure

```text
AI-mining-proto/
├── .github/
│   └── workflows/
│       └── static.yml            # GitHub Actions workflow deploying the repository as static GitHub Pages content
├── index.html                 # Entire working application: markup, CSS, JS, mock data
├── README.md                  # "# AI-mining-proto"
└── SIH2026_FRONTEND_STRUCTURE.md  # This audit (new planning file only)
```

There are no package manifests, lockfiles, build scripts, backend files, test files, asset folders, or data files. The repository does include GitHub Actions configuration at `.github/workflows/static.yml`: it deploys the repository as static GitHub Pages content. The application currently runs as a static page.

## 3. Current Frontend Architecture

`index.html` contains four logical layers in one file:

1. Document shell: fonts, sidebar, sticky top bar, search, responsive app shell, content mount (`#content`), toast mount, document-details modal shell, and geological background mount.
2. Embedded CSS: design tokens, reusable primitives, page-specific styles, SVG/chart/map styles, utilities, and responsive media queries.
3. Data and view builders: a top-level `MOCK` data object, `SEARCH_INDEX`, constants, custom SVG factories, page template functions, and reusable rendering functions.
4. Runtime controller: one mutable `APP` state object; `goTo()` routes between page keys by replacing `#content.innerHTML`; `after*()` functions attach event listeners after each render.

There is no framework, client-side persistence, HTTP client, API call, authentication, upload transport, file parsing, OCR, database access, or server rendering. State lasts only while the page is open.

## 4. Complete UI/Page Inventory

| View / route key | Main UI and current behavior |
| --- | --- |
| Dashboard (`dashboard`) | Hero with AI prompt/upload entry points; rotating/zoomable decorative geological SVG; five KPI cards; production bar/line chart; subsidiary bar chart; production snapshot. |
| Documents (`documents`) | Drag/drop zone; upload and bulk-upload buttons; simulated eight-step processing pipeline; status metrics; filterable document library; View, Ask AI, and Download actions. |
| AI Query (`ai-query`) | Question input, Enter/Ask actions, preset chips, typing delay, answer card, source-reference cards, and fallback answer. |
| Analytics (`analytics`) | Year/subsidiary selector UI, production chart, coal-grade donut, subsidiary chart, and geological/geophysical area chart. The selector controls are currently display-only. |
| Report Generator (`reports`) | Seven-state wizard: report type, organization, date range, data sources, output format, simulated generation progress, and simulated preview/download/source actions. |
| Topics & Word Cloud (`topics`) | Word cloud, ranked topic bars, and a topic-trend area chart. |
| Data Explorer (`explorer`) | Tabs for Production, Mines, Exploration, Geological Data, Projects, Subsidiaries, and Dispatch; text filtering; HTML table; simulated CSV/Excel export. |
| 3D Geological View (`geo3d`) | SVG pseudo-3D block model; checkboxes for strata, coal seam, boreholes, exploration points, fault lines, and seismic data; rotation/zoom/reset buttons and mouse drag. |
| Mining Map (`map`) | Stylized SVG/GIS-grid background; mine/coalfield/survey pins; text and subsidiary filters; zoom controls; hover tooltip. |
| Audit Trail (`audit`) | Activity timeline and a user-filtered audit-log table. |
| Shared chrome | Sidebar navigation, mobile sidebar/scrim, global demo search, settings/profile/notifications toasts, environment badge, and ambient geological background. |

## 5. Existing Component Inventory

There are no separately stored component files yet. The following are the reusable logical components already present and should become extraction candidates rather than being redesigned:

- App shell: `app-shell`, `sidebar`, top bar, global search, mobile sidebar controls, toast stack, and `geoBg` background.
- Navigation: `NAV_ITEMS`, `renderSidebar()`, route dispatcher `goTo()`, `renderPage()`, and `afterRender()`.
- Shared visual primitives: cards, card headers, KPI cards (`kpiCard()`), mini stat cards (`statusMiniCard()`), buttons, chips, badges, status pills (`statusPill()`), filters, responsive grid helpers, tables, tooltips, modal shell, and toast utility.
- Chart builders: `buildProductionChart()`, `buildSubsidiaryChart()`, `buildDonutChart()`, `buildAreaChart()`, and SVG helper `svgEl()`.
- Geological/GIS visual builders: `buildGeoBackground()`, `buildHeroGeoBlock()`, `buildGeo3DScene()`, `buildMiningMapSVG()`, layer-toggle helper, map-pin renderer, and transform controls.
- Feature renderers: `page*()` and corresponding `after*()` functions for each of the ten views.
- Workflow components: document pipeline, `openDocDetail()` modal, AI answer card, report wizard, Explorer table, Audit table, and global search results.

## 6. Existing JavaScript Functionality

- Bootstraps after `DOMContentLoaded`; builds the ambient SVG background, renders navigation, wires shell actions, and opens Dashboard.
- Uses an in-memory `APP` object for route, document filter, Explorer tab, selected year, 3D layer state, and report-wizard state.
- Provides page replacement routing without URL/history synchronization.
- Renders all chart and geological visuals with custom inline SVG/DOM code; no chart, GIS, or 3D library is used.
- Supports responsive mobile sidebar opening/closing.
- Searches the fixed `SEARCH_INDEX`; selecting a result changes the view.
- Filters Documents by status, Explorer rows by text, Map pins by text/subsidiary, and Audit rows by user.
- Runs document-row actions: document insights modal, navigation to AI Query with a preset question, and a simulated download toast.
- Animates an upload/processing pipeline and a report-generation pipeline with `setTimeout`.
- Performs exact text matching of questions against `MOCK.aiQA`, otherwise uses a simulated fallback.
- Drives hero and full 3D SVG rotation, zoom, reset, checkbox visibility, and drag rotation.
- Renders map-pin hover tooltips and scales the map wrapper for zoom.
- Uses modal overlay click-to-close and transient toast messages.

## 7. CSS/Styling Inventory

All CSS is embedded in one `<style>` block. Its main sections are:

- Design tokens: CMPDI navy/royal/blue/gold/earth/semantic colors, fonts, radii, shadows, and sidebar width.
- Global base/reset, scrollbar styling, and focus-visible accessibility treatment.
- App shell, sidebar/brand/navigation, sticky top bar/global search, content container, page fade animation, and geological background watermark.
- Shared cards, KPI/stat cards, buttons, chips, badges/status pills, grids, rows, filters, tables, upload zone, pipeline, modal, toast, and utility classes.
- Dashboard hero and hero geological controls.
- AI panel/answer/source cards, report wizard/option cards/progress rows, topic cloud/bars, 3D geological stage/layer controls, map stage/tooltip, and audit timeline.
- Responsive breakpoints at 1180px, 860px, 600px, and 520px. The 860px breakpoint switches to the mobile sidebar pattern and collapses major grids.

Visual identity to preserve: `Fraunces` headings; `Inter` body text; `IBM Plex Mono` technical labels; navy/royal-blue/gold palette; rounded cards; geological contour/strata motifs; status colors; SVG-based visualizations; and mobile behavior.

## 8. Mock/Demo Data Inventory

`MOCK` is the central demo-data boundary and is already a good future adapter seam. It contains:

- Five annual national/CIL production records (2021–2025).
- Seven CIL subsidiary records with production and state.
- Ten document records with type, organization, year, page/table counts, status, and confidence/accuracy.
- One detailed document-insight record (`D-1001`), reused as a fallback for the other document detail actions.
- Five fixed AI question/answer/citation records plus one simulated fallback answer.
- Five topics and fifteen word-cloud entries.
- Twelve mine/coalfield/exploration/survey locations represented by display coordinates, not geographic coordinates.
- Ten audit events.
- Seven Explorer datasets, all represented as arrays of column names and string rows.
- A ten-entry `SEARCH_INDEX`.
- Inline chart series for grade distribution, geological activity, and topic trends.
- Report type definitions, fixed year ranges/formats, initial report sources, named demo user/profile, notification count/message, and multiple fixed geological coordinates/labels.

The page labels distinguish some values as official, demo, or prototype, but provenance is inconsistent at field level. Before real data is shown, each dataset should receive explicit `source`, `source_document_id`, `page`, `period`, `verified_at`, and `is_demo` metadata.

## 9. Hard-coded/Simulated Functionality

The following must be described as prototype behavior until replaced by real services:

- Upload buttons and drag/drop never upload or retain a file; a dropped file name only feeds the visual pipeline.
- OCR, extraction, table detection, entity extraction, validation, AI indexing, completion, and failed OCR entries are UI simulation only.
- Document download, document preview, extracted insights, source-view button, and document-specific details are simulated; all non-`D-1001` details reuse `D-1001` content.
- AI answers are hard-coded exact-question matches with a fixed fallback; confidence values and citations are not retrieval results.
- Report generation is timer-based; preview/download/source controls do not create/open/download report files.
- Explorer exports only show toasts; no CSV/XLSX is produced.
- Analytics filter controls do not update charts.
- Map geometry is a stylized SVG grid and pin `x/y` percentages, not real GIS boundaries, coordinates, tiles, or spatial queries.
- The 3D view is an SVG illustration with transforms, not a geological model, mesh, volume, or real layer data.
- Audit entries are static and do not record user actions.
- Settings, profile, notifications, global search, user identity, KPI values, query prompts, and hero coordinates are hard-coded.
- There is no authentication, authorization, validation, error recovery, persistence, file-size/type policy, antivirus scanning, accessibility audit, or data-provenance enforcement.

## 10. Working vs Partial vs Mock vs Missing Features

| Status | Features |
| --- | --- |
| Working in-browser UI | Navigation; responsive shell; search over a fixed index; filters; tabs; table rendering; modal/toasts; custom SVG charts; SVG map/3D/hero interactions; report-wizard state transitions. |
| Partial UI | Analytics selectors appear but are unwired; source links are styled but non-functional; document-detail data is complete only for one mocked document; URL routing and back/forward navigation are absent. |
| Mock / simulated | Upload/OCR/extraction/indexing; AI/RAG; document preview/download; exports; report generation/files; GIS; geological model; audit logging; notifications/settings/profile. |
| Missing for a real demo backend | API, database/schema/migrations, authentication/roles, object storage, background jobs, Excel/CSV parser, OCR, ingestion validation, document provenance, RAG/indexing, report renderer, real exports, observability, automated quality/test CI, environment configuration, and API contracts. The existing GitHub Actions workflow is static GitHub Pages deployment configuration, not a test/quality pipeline. |

## 11. Recommended Target Architecture

Adopt a **Django + Django REST Framework modular monolith**, not microservices. One deployable frontend and one deployable API are adequate for the six-day prototype. Keep feature modules internally separated so team ownership remains clear. Do not introduce Kubernetes.

```text
Browser UI
  -> Frontend API client / shared contracts
  -> Django + DRF single Backend API
       -> SQLite initially (PostgreSQL-ready relational design; MongoDB is optional, not required)
       -> file/object storage (original uploads and generated reports)
       -> worker/queued job boundary (ingestion, parsing, indexing, reports)
       -> first-class Excel/CSV Maintainer module
       -> AI/RAG adapter (only when enabled)
```

Use Django and Django REST Framework as the preferred backend for this prototype. Django’s ORM, migrations, admin, authentication foundation, and mature Python ecosystem make it a practical fit for document processing, spreadsheets, report generation, and AI integration. Start with SQLite to keep setup and demo packaging simple; use portable models, migrations, and standard relational features so PostgreSQL can replace it cleanly if deployment or concurrency later demands it. MongoDB is not mandatory and should not be introduced without a concrete need. This is an implementation-phase decision, not a request to install anything now.

The current `.github/workflows/static.yml` GitHub Pages workflow is suitable for the present static frontend prototype. Before adding Django/DRF backend content, separate the deployment strategy: deploy only the frontend/static build to GitHub Pages (if Pages remains in use) and deploy the Django backend through a distinct server/container/platform workflow. Do not allow `backend/` source, environment files, runtime artifacts, or uploaded/generated data to be included accidentally in the static Pages artifact.

Key design rules:

- Keep one API boundary and one database for the prototype.
- Model documents, extracted datasets, sources/citations, jobs, reports, and audit events explicitly.
- Make normalized structured processed data the single source of truth for Dashboard, Analytics, Data Explorer, AI/RAG, Reports, Topics, charts, map/3D visualizations, and any future UI view models.
- Make Excel/CSV Maintainer a core module that validates, normalizes, versions, previews, imports, exports, and traces spreadsheet/CSV data rather than treating it as a secondary utility.
- Run long work behind job status endpoints; the frontend should poll/query status instead of faking timers once connected.
- Treat source citations and dataset provenance as first-class data, not display strings.
- Isolate vendor-specific AI/OCR/GIS/report integrations behind adapters.
- Preserve a `demo` mode where the UI can use fixtures if backend services are unavailable at judging time.

## 12. Recommended Frontend Structure

Do not migrate to React now. First retain vanilla JavaScript and extract the current code verbatim into ES modules, preserving markup/class names and CSS. That minimizes visual regression and avoids package installation/build-tool risk.

Suggested future frontend layout:

```text
frontend/
├── public/
│   └── prototype-baseline/       # read-only copy/reference of verified original UI, if later needed
├── src/
│   ├── app/                      # bootstrap, router, app state, layout
│   ├── pages/                    # dashboard, documents, ai-query, analytics, reports, topics,
│   │                             # explorer, geo3d, map, audit
│   ├── components/               # shell, navigation, table, modal, toast, chart, status primitives
│   ├── features/                 # document-intelligence, querying, reporting, explorer, geospatial, audit
│   ├── services/                 # API client and feature repositories/adapters
│   ├── data/                     # development fixtures derived from MOCK
│   ├── styles/                   # tokens, base, layout, components, page styles, responsive rules
│   ├── utils/                    # SVG and DOM helpers
│   └── types/                    # frontend-only view models if needed
└── tests/
```

Keep page renderer and `after*()` pairing together during the first extraction. Extract shared chart/visual builders before changing their APIs. Keep the existing class names and design tokens during this phase. A later React migration is appropriate only if it offers a clear team-speed benefit after the prototype has regression screenshots and the core vertical slices are stable; map each current page to one route/component and preserve the same fixture adapter first.

## 13. Recommended Backend Structure

```text
backend/
├── config/                       # Django settings, URLs, ASGI/WSGI, environment configuration
├── apps/
│   ├── documents/                # uploads, document metadata, storage and processing job entry points
│   ├── processing/               # OCR/extraction/validation orchestration and job states
│   ├── structured_data/          # canonical normalized records, provenance, validation and query services
│   ├── spreadsheet_maintainer/   # first-class Excel/CSV import, validation, normalization, preview and export
│   ├── ai_rag/                   # retrieval/query/citation contracts and provider adapter
│   ├── analytics/                # Dashboard/Analytics/Topics/visualization read models derived from canonical data
│   ├── reports/                  # report requests, templates, rendering jobs and generated files
│   ├── audit/                    # immutable audit-event creation and read APIs
│   └── users/                    # roles/authentication foundation
├── common/                       # shared Django utilities, storage and external-service adapters
├── manage.py
└── tests/
```

Initial API vertical slices should be small: health/demo status, documents list/detail, Explorer datasets, and audit list. Add upload/job status only when the actual processing path is available. AI query and report endpoints should return structured citations/job/report metadata, not page-ready HTML.

## 14. Recommended Data/Database Structure

Use SQLite for a self-contained demo first, with a clean path to PostgreSQL if deployment/concurrency later requires it. Use Django ORM migrations, stable identifiers, normalized relations, portable constraints, and no SQLite-specific SQL in domain code. MongoDB is not required. Keep original files and generated reports outside the database in a local storage directory for demo or object storage later.

Suggested core entities:

- `users` and `roles` (even if demo login is deferred).
- `documents`: identity, filename, MIME type, organization, period, storage key, checksum, upload status, source/provenance.
- `processing_jobs`: document/job type/status/stage/errors/timestamps.
- `document_pages`, `document_chunks`, `extractions`, `tables`, and `table_rows`: parsed material and traceability.
- `datasets`, `dataset_versions`, `dataset_records`, and `field_provenance`: normalized canonical processed data, source document/page/table reference, validation state, and spreadsheet lineage. These records are the single source of truth for all downstream UI, analytics, AI, reports, topics, and visualizations.
- `mines`, `coalfields`, `geological_layers`, and optional spatial geometry/coordinates only after verified source data exists.
- `reports`: requested parameters, job/status, output key, template/version, source set.
- `audit_events`: actor, action, entity type/id, metadata, timestamp, outcome.
- `ai_queries` and `citations`: query/answer/model metadata and exact source chunk/page references when RAG is introduced.

Store schemas, sample fixtures, and data dictionaries separately from raw files:

```text
data/
├── fixtures/                     # demo JSON/CSV matching current MOCK data
├── samples/                      # approved non-sensitive example documents only
├── schemas/                      # CSV/Excel column contracts and JSON schemas
└── dictionaries/                 # mining/geology terms, subsidiaries, statuses
```

### Core demo data flow

The demo should be built around one honest, traceable path:

```text
Upload PDF / scanned PDF / DOCX / XLSX / CSV / image
  -> processing job
  -> extraction and OCR where applicable
  -> validation
  -> canonical structured processed data
  -> Excel/CSV Maintainer (review, correction, normalization, import/export, versioning)
  -> AI Query/RAG with citations from canonical data and source documents
  -> dynamic Dashboard and Analytics
  -> Report Generator
  -> Audit Trail
```

The canonical structured processed data is the sole data source for Dashboard, Analytics, Data Explorer, AI/RAG, Reports, Topics, charts, GIS/map display data, and geological visualizations. Original documents remain the evidence source; each structured record must preserve its document/page/table/row provenance. Offline/demo fixtures must implement the same contracts and remain available as a reliable judging fallback when live processing or external AI services are unavailable.

## 15. Safe Frontend Migration Strategy

1. Freeze a visual baseline: open the current `index.html`, exercise all ten pages, and capture agreed desktop/mobile screenshots before moving code.
2. Keep `index.html` working and untouched until a copied/extracted implementation reproduces it. Do not remove the prototype during SIH preparation.
3. Extract only the `MOCK`, `SEARCH_INDEX`, `COLORS`, and `NAV_ITEMS` declarations into fixtures/constants; verify the browser behavior is unchanged.
4. Extract shared helpers in this order: SVG helpers/builders, modal/toast utilities, shell/router, CSS tokens/primitives, then page modules one at a time.
5. Retain existing IDs, class names, element hierarchy where practical, copy wording/spacing/design tokens, and compare screenshots after every page extraction.
6. Replace mock reads with repository interfaces such as `documentsRepository.list()` that initially return fixtures. Connect APIs page by page only after a backend vertical slice is verified.
7. Keep demo fixtures and an explicit fallback banner/mode for judges; never silently present generated/simulated content as verified production data.
8. Consider React only after the vanilla modular version is stable. If adopted, migrate one view at a time behind the same fixture/API contracts and retain visual regression checks.

## 16. Team-Friendly Folder Structure

```text
AI-mining-proto/
├── index.html                    # Preserve as the current visual baseline during migration
├── frontend/                     # UI owner; feature folders reduce merge overlap
├── backend/                      # API owner; modular-monolith backend
├── data/                         # fixtures, schemas, dictionaries, approved samples
├── docs/                         # architecture, API contract, demo script, data dictionary
├── shared/                       # language-neutral API schemas/OpenAPI and example payloads
├── tests/                        # end-to-end, visual/checklist, contract fixtures
├── scripts/                      # safe developer/demo helpers only when actually needed
├── .env.example                  # names only; never secrets
├── README.md                     # setup, run, demo, and contribution instructions
└── SIH2026_FRONTEND_STRUCTURE.md
```

Within `frontend/src/features`, one feature should own its own API adapter, view state, and tests. Within `backend/app/domain`, one domain owns its validation and service logic. `shared/` must contain contracts, not business logic duplicated across runtimes. Avoid a generic catch-all `utils/` becoming the main team integration point.

## 17. Team Responsibility Boundaries

| Owner | Scope and merge boundary | Avoid changing without coordination |
| --- | --- | --- |
| Frontend | `frontend/`; app shell; preserved CSS/design system; page integration; fixture/API adapters. | Backend internals, source data definitions, report/AI business rules. |
| Backend | `backend/app/api`, domain/services, repository interfaces, migrations, authentication boundary. | Frontend markup/styling and visual contracts. |
| Data Processing | `backend/app/adapters` and `workers` ingestion/parsing contracts; `data/schemas`; validation/provenance rules. | API response shape without shared-contract review. |
| AI/RAG | AI adapter, chunk/citation/query contracts, retrieval evaluation fixtures and prompts. | Claiming citations/confidence that are not traceable. |
| Excel/CSV Maintainer | `data/schemas`, fixture CSV/JSON, spreadsheet import/export adapter, normalization/data dictionary. | Manually changing frontend display datasets directly. |
| Reports | report templates, structured report request/output contract, renderer adapter, generated-file storage flow. | UI wizard design unless coordinating with Frontend. |
| Testing | `tests/`, acceptance checklist, fixture contract checks, regression screenshot matrix, smoke scripts. | Production fixture/data changes without reviewing expected behavior. |

One rotating integration owner should merge contract changes. Require a short API/schema change note in `docs/` before parallel owners alter shared payloads.

## 18. Files/Components to Preserve

Preserve `index.html` exactly during this planning stage and as the source-of-truth visual baseline during later work. In particular preserve:

- The current app shell, sidebar order/labels, header/search layout, responsive sidebar, and typography/color token system.
- Existing CSS classes, card spacing, button/chip/status patterns, SVG visual styling, and breakpoint behavior.
- The ten page concepts, `NAV_ITEMS` route keys, `MOCK` fixture shape (until a documented mapping replaces it), and `SEARCH_INDEX` behavior.
- Custom chart builders and geology/map builders; they avoid a new dependency and are appropriate for a six-day prototype.
- Document library, AI answer/citation layout, report-wizard visual sequence, Explorer table format, and Audit presentation.

## 19. Files/Components to Refactor Later

The only source file is `index.html`; refactor by extraction, not redesign:

- Split its embedded CSS into tokens/base/layout/components/pages/responsive files while retaining selectors.
- Split `MOCK`, `SEARCH_INDEX`, hard-coded labels, and chart series into typed fixtures/constants.
- Replace global `APP` with a small scoped store/router after page behavior is covered by tests.
- Separate page markup/rendering from event binding; use feature repository interfaces to replace `MOCK` incrementally.
- Replace `innerHTML` handling for dynamic untrusted/API content with safe rendering/escaping before accepting external document or AI content.
- Add URL routes, empty/loading/error states, input/file validation, and accessibility semantics during implementation.
- Convert the simulated timer workflows to real job-state polling only after backend job endpoints exist.

## 20. Files/Components That Should NOT Be Touched Unnecessarily

- `index.html` must not be rewritten, moved, renamed, deleted, or replaced by a template during the planning phase.
- Do not replace custom SVG charts with a chart library or the SVG map/3D visual with GIS/3D libraries solely for architecture aesthetics.
- Do not change design tokens, sidebar information architecture, component class names, icon language, or responsive breakpoints without visual comparison and product agreement.
- Do not remove mock fixtures before a verified replacement and an offline demo fallback exist.
- Do not introduce package/build/config churn while the current static prototype is the only stable runnable artifact.

## 21. 6-Day Critical Path

| Day | Demo-critical outcome |
| --- | --- |
| 1 | Freeze visual baseline; agree API/data contracts; create fixtures/data dictionary; assign owners; retain a runnable static demo. |
| 2 | Establish Django/DRF skeleton only if needed; implement Documents list/detail, canonical structured-data, and Explorer read API using fixtures/SQLite; verify UI adapters. |
| 3 | Implement one reliable upload-to-job-status-to-validation vertical slice for a small approved file set. Include the Excel/CSV Maintainer review/normalization path and audit-event creation; retain an explicit fallback if live processing is not ready. |
| 4 | Implement one bounded AI/RAG query flow with citations from canonical structured data and source documents; prioritize truthful source display over broad coverage. |
| 5 | Derive dynamic Dashboard/Analytics from canonical data; implement one report template/output flow and one real Excel/CSV import/export flow; maintain offline demo fixtures. |
| 6 | End-to-end rehearsal, fixture reset, error/offline checks, responsive visual comparison, source/provenance verification, packaging, and demo script. No large architecture changes. |

If time tightens, prioritize: retained polished UI; Documents/structured data/Explorer with provenance; Excel/CSV Maintainer; one reliable AI/citation scenario; one dynamic dashboard/analytics scenario; one report scenario; stable offline demo fixture mode. Treat broad OCR support, full GIS, full 3D data, broad document support, and broad RAG as stretch work.

## 22. Risks and Blockers

- **Single-file coupling:** multiple developers editing `index.html` will create merge conflicts and visual regressions. Mitigation: establish file ownership and extract by feature only after a baseline.
- **Misleading demo claims:** current static “confidence,” “verified,” OCR, audit, source, and production claims can be interpreted as live. Mitigation: label fixtures/simulations visibly and retain exact provenance.
- **No data provenance model:** values are duplicated across cards, AI responses, Explorer rows, and charts. Mitigation: centralize source datasets and derive view models.
- **No persistence or jobs:** upload/report/AI flows cannot survive refresh or support genuine status. Mitigation: build one small job/status pattern or keep the demo path explicit.
- **Untrusted-content injection:** dynamic templates interpolate values using `innerHTML`; real filenames, extracted text, and model output need escaping/sanitization. Mitigation: make safe rendering a prerequisite of live uploads/AI output.
- **Visual fragility:** custom SVG dimensions/transforms and inline styles are easy to break during migration. Mitigation: screenshot comparison at the listed breakpoints.
- **Scope pressure:** OCR, RAG, Excel intelligence, reports, GIS, and 3D are separate product tracks. Mitigation: vertical slices and one curated data corpus, not broad feature claims.
- **Data sensitivity/licensing:** CMPDI/CIL documents may have access, accuracy, and redistribution constraints. Mitigation: use approved demo samples and document sources/permissions.
- **Tooling uncertainty:** no existing stack/dependencies means selecting a framework now costs time. Mitigation: keep vanilla UI for the prototype and defer package decisions.
- **Git status limitation:** the repository owner differs from the sandbox user, so ordinary `git status` requires a temporary command-scoped safe-directory override; no Git configuration should be changed for this audit.

## 23. Testing/Validation Checklist

Before implementation/migration:

- [ ] Record baseline screenshots at desktop and at the existing 1180px, 860px, 600px, and 520px breakpoints.
- [ ] Manually traverse every sidebar route and global-search result.
- [ ] Verify document status filter, document modal, AI preset/unknown query, Explorer tabs/search, map filters/tooltip/zoom, 3D controls/layers/drag, audit filter, and report wizard steps.
- [ ] Confirm demo/simulated labels appear wherever a feature has no live backend.

For every future vertical slice:

- [ ] Validate API response against a versioned shared contract and fixture.
- [ ] Validate a source record/page/citation is retained from input through UI/report output.
- [ ] Test loading, empty, invalid-input, failed-job, offline, and retry states.
- [ ] Test real uploads only with approved file types/sizes and validate filename/content handling.
- [ ] Test permissions/roles before exposing upload, report, or audit actions.
- [ ] Compare screenshots/critical styles against the preserved baseline.
- [ ] Smoke test a clean startup and a no-network/offline fixture demo.
- [ ] Run feature unit tests, API contract tests, and one end-to-end happy path: document -> extracted/explorer data -> cited query -> report -> audit event.
- [ ] Rehearse the final judging demo with resettable fixtures and no dependence on an unverified external service.

## Audit Scope Confirmation

This audit inspected the complete available repository content. It made no application source-code change. The only created file is this Markdown planning document. No files were deleted, moved, or renamed; no dependencies were installed; and no commit or push was performed.
