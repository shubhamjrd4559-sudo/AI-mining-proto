# Phase 5 — RAG Mining Intelligence Walkthrough

## Summary of Completed Implementation

Phase 5 has been implemented strictly adhering to project requirements, providing grounded, real RAG-based natural language querying over verified mining documents and structured datasets.

### What Was Built:

1. **New App `apps.intelligence`**:
   - `DocumentChunk` model for granular, traceable document text chunks with deterministic SHA-256 fingerprinting.
   - `AIQueryLog` model for query history, questions, grounded answers, citations, and confidence scores.
   - Database migrations created and applied (`0001_initial.py`).

2. **Deterministic Chunking & Indexing Pipeline**:
   - `chunk_text()`: Splits document text along natural sentence and paragraph boundaries (~600 chars with 80-char overlap) while retaining page numbers and section headings.
   - `chunk_extracted_tables()`: Chunks structured extracted tables into readable records preserving row indices and column headers.
   - `index_document()`: Safe, atomic document chunk indexing with duplicate detection via content fingerprinting.
   - Hooked into `apps.pipeline.orchestrator` so documents reaching `INDEXED` or `NEEDS_REVIEW` automatically index.
   - `reindex_documents` management command for batch/single indexing.

3. **Intelligent Query Routing**:
   - `query_router.py`: Classifies queries into `STRUCTURED`, `DOCUMENT`, or `HYBRID`.
   - Entity & concept extraction for CIL subsidiaries (MCL, ECL, BCCL, CCL, WCL, SECL, NCL, CMPDI, CIL), metrics (production, dispatch, reserves, overburden, grade, borehole), financial years, and aggregations (highest, lowest, sum, average).

4. **Multi-Tenant Retrieval & Deterministic Calculations**:
   - `retriever.py`: Enforces owner filtering (`uploaded_by=request.user`) strictly during retrieval.
   - BM25 ranked chunk search with exact phrase and heading boosts.
   - Deterministic calculations on structured data records with full `ExtractionProvenance` tracking.

5. **Prompt Injection Defense & Grounded Generation**:
   - `llm_client.py`: Configurable Gemini client (`GEMINI_API_KEY`, model `gemini-2.5-flash`), timeouts, and exception safety.
   - `answer_engine.py`: Encapsulates evidence in `<document_evidence>` XML blocks and strictly instructs LLM to treat content as passive data.
   - Refuses missing facts with standard: *"I could not find sufficient evidence in the available project data."*
   - Confidence scoring (`HIGH`, `MEDIUM`, `LOW`) based on retrieval score and evidence counts.
   - Offline grounded synthesis fallback when LLM is unconfigured or unreachable.

6. **Authenticated APIs & Frontend Integration**:
   - `POST /api/chat/` and `POST /api/intelligence/query/` requiring `IsAuthenticated`.
   - `GET /api/intelligence/history/` for query history.
   - `POST /api/intelligence/reindex/` for user-triggered re-indexing.
   - `AuditEvent` logging with event type `ai.query`.
   - Frontend `runAIQuery(question)` in `index.html` updated to execute real backend queries and display grounded answers, query type badges, confidence chips, and structured source cards.

---

## Test Verification

- **Total Tests**: 123/123 PASSED (0 failures, 0 errors)
  - `apps.intelligence`: 22 tests (authentication, multi-tenancy, cross-user isolation, chunking, indexing, routing, structured calculations, BM25 retrieval, prompt injection defense, offline fallback, API validation, audit logging, query history)
  - `apps.documents`: 47 tests
  - `apps.pipeline`: 30 tests
  - `apps.storage`: 11 tests
  - `apps.core`: 6 tests
  - `apps.audit`: 4 tests
  - `apps.datasets`: 3 tests
- `manage.py check`: 0 issues
- `manage.py makemigrations --check --dry-run`: No changes detected
- `git diff --check`: 0 whitespace errors
- `index.html` JavaScript syntax: Validated with Node.js engine
