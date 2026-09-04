# SIH 2026 — Frontend Structure Reference

## Overview

The frontend is a **single-file static application** (`index.html`, ~120 KB).
It is a fully functional demo/prototype built with vanilla HTML + CSS + JavaScript.

**IMPORTANT:** This file must be preserved exactly through Phase 1, 2, and 3.
Gradual React migration begins in Phase 4 if approved.

---

## Pages / Sections

| Page ID | Nav Label | Description |
|---|---|---|
| `dashboard` | Dashboard | KPI cards, coal production chart, document pipeline status, recent documents |
| `documents` | Documents | Document list, upload button, status pills, document detail |
| `query` | AI Query | Chat interface for natural language queries over mining data |
| `analytics` | Analytics | Production trend charts, seam analysis, subsidiary comparison |
| `reports` | Report Generator | Report template selection, parameter form, export controls |
| `topics` | Topics & Word Cloud | Topic modeling results, word cloud visualization |
| `explorer` | Data Explorer | Tabular structured data browser with filters |
| `geo3d` | 3D Geological View | Interactive SVG geological block cross-section |
| `map` | Mining Map | SVG map of mine sites with pins, tooltips, zoom |
| `audit` | Audit Trail | Activity timeline + filterable audit log table |

---

## Navigation

Implemented via `goTo(pageId)` function in `<script>`.
Sidebar nav links call `goTo('pageId')`.

## Mock Data

All data is in the `MOCK` object at the top of the `<script>` section:
- `MOCK.documents` — array of document objects
- `MOCK.mines` — array of mine site objects
- `MOCK.auditTrail` — array of audit events
- `MOCK.topics` — topic modeling results
- `MOCK.coalData` — production timeseries

**Phase 1:** All mock data remains. Demo mode is always active.
**Phase 2+:** Real data progressively replaces mock data per section.

---

## API Service Boundary (added Phase 1)

A non-breaking `<script>` block at the bottom of `index.html` defines:

```javascript
const API_BASE = 'http://127.0.0.1:8000';
const apiServices = { health, documents, analytics, chat, excel, reports, topics, audit };
```

- When the backend is running: health check succeeds silently in console
- When the backend is not running: graceful fallback, mock data continues working
- No existing UI behavior is changed

---

## CSS Design Tokens

Defined in `:root` at the top of the `<style>` block:

| Token | Value | Usage |
|---|---|---|
| `--navy` | `#071A3D` | Sidebar, headings |
| `--royal` | `#0B4DB8` | Primary action |
| `--blue` | `#1976D2` | Links, charts |
| `--gold` | `#DFAE24` | Highlights, alerts |
| `--green` | `#1E9E63` | Success status |
| `--red` | `#D64545` | Error status |
| `--font-display` | Fraunces | Headings |
| `--font-body` | Inter | Body text |
| `--font-mono` | IBM Plex Mono | Code, metadata |

---

## External Dependencies (CDN — no build step)

None — all CSS and JavaScript is self-contained within `index.html`.
Google Fonts loaded via `<link>` (gracefully degrades offline).
