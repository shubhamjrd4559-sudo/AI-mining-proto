# ⛏️ AI — Mining Intelligence Command Center

> **Enterprise AI-Powered Geological, Mining, and Production Reporting Solution**  
> Developed for **Central Mine Planning & Design Institute (CMPDI)** & **Coal India Limited (CIL)** Subsidiaries.

[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.16-red?logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![Gemini](https://img.shields.io/badge/Gemini-3.1--Flash--Lite-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)
[![Leaflet](https://img.shields.io/badge/GIS-Leaflet%201.9-199900?logo=leaflet&logoColor=white)](https://leafletjs.com/)
[![License](https://img.shields.io/badge/License-Proprietary-blue.svg)](#)

---

## 📸 Platform Previews

| Executive Dashboard & AI Command Center | Interactive GIS Mining Map & Spatial Intelligence |
|:---:|:---:|
| ![Dashboard Preview](./readmy%20photo.png) | ![GIS Map Preview](./readmy%20photo2.png) |

---

## 🌟 Key Capabilities

### 1. 🤖 Zero-Hallucination AI Query Assistant (RAG Engine)
* **Strict Ground-Truth Retrieval:** Combines BM25 chunk retrieval with structured dataset matching, guaranteeing deterministic figures for production, dispatch, capex, overburden, and coal grade.
* **Intelligent Variance & Gap Analysis:** Compares current uploaded documents against historical baselines or production targets (*calculates shortfall, surplus, achievement rate, and dispatch backlogs*).
* **Operational Improvement Diagnostic:** Generates practical mining recommendations based strictly on verified operational data (*preventive maintenance for HEMM, dispatch logistics optimization, overburden synchronization*).
* **Entity-Specific Precision:** Directly resolves subsidiary rows (**MCL**, **NCL**, **SECL**, **CCL**, **WCL**, **BCCL**, **ECL**) and individual mine queries without mixing up mine totals.

### 2. 📑 Universal Document Extraction Pipeline
* **Multi-Format Processing:** Ingests PDF, DOCX, XLSX, and CSV documents with automated structure detection.
* **Robust PDF Parsing:** Multi-engine fallback pipeline combining `pypdfium2`, `pdfplumber`, and `pytesseract` OCR for high-fidelity tabular data extraction.
* **Resilient Retry Architecture:** Self-healing job execution engine with automatic recovery for interrupted extractions.

### 3. 📊 Structured Data Explorer (Phase 6)
* **National Mine Statistics Directory:** Integrated database covering **408+ coal mines** across all major Indian coalfields.
* **Dynamic Table Controls:** Instant search, multi-column filtering by State, District, Subsidiary, and Mine Name, server-side pagination, and one-click CSV export.

### 4. 🗺️ GIS & 3D Spatial Intelligence (Phase 8)
* **Interactive Mine Distribution Map:** Leaflet 1.9 GIS engine with high-resolution ArcGIS Esri satellite/street tiles.
* **Precise Geospatial Metadata:** Verified coordinates, mining type (Open-Cast / Underground), coalfields, and annual production figures.
* **3D Geological Strata Visualization:** Interactive 3D borehole layers and stratigraphic cross-sections.

### 5. 🛡️ Data Maintainer & Immutable Audit Trail
* **Human-in-the-Loop Verification:** Review and approve AI-generated data suggestions and cleanings before database persistence.
* **Tamper-Evident Audit Logging:** Comprehensive actor, action, timestamp, and resource tracking for regulatory compliance.

---

## 🏗️ System Architecture

```
                                ┌──────────────────────────────────────────────────────────┐
                                │               SINGLE-PAGE APPLICATION (SPA)              │
                                │           Vanilla HTML5 / CSS3 / ES6+ JavaScript         │
                                │   Dashboard • Documents • AI Query • Analytics • Data    │
                                │  Explorer • GIS Map • 3D Geo • Maintainer • Audit Trail  │
                                └────────────────────────────┬─────────────────────────────┘
                                                             │ RESTful APIs / Token Auth
                                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                             DJANGO MODULAR MONOLITH BACKEND                                            │
├───────────────────┬───────────────────┬───────────────────┬───────────────────┬───────────────────┬────────────────────┤
│   apps.frontend   │  apps.documents   │   apps.pipeline   │ apps.intelligence │   apps.datasets   │   apps.analytics   │
│ SPA Shell Server  │  Upload, Storage, │ Extraction, OCR,  │ Gemini 3.1 Flash, │  Data Explorer,   │ Dynamic KPIs,      │
│ Static Assets     │  Job Lifecycle    │ Schema Detection  │ BM25 Chunker/RAG  │ Provenance Engine │ Aggregates, Trends │
├───────────────────┼───────────────────┼───────────────────┼───────────────────┼───────────────────┼────────────────────┤
│   apps.maintainer │   apps.reports    │    apps.phase8    │    apps.audit     │   apps.storage    │     apps.core      │
│ Clean Suggestions │ 8 Report Formats, │ WordCloud, Topics,│ Immutable Audit   │ Local & S3 File   │ Health Checks,     │
│ Batch Validation  │ PDF/XLSX Export   │ 408 GIS Mines     │ Trail & Events    │ Abstraction Layer │ Seed Utilities     │
└───────────────────┴───────────────────┴───────────────────┴───────────────────┴───────────────────┴────────────────────┘
                                                             │
                                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                  DATA & STORAGE LAYER                                                  │
│  • SQLite Database (Development & Demo Prototype) — 100% PostgreSQL-Ready Django ORM Models                            │
│  • Local / S3 File Storage — Scalable media and document repository                                                    │
│  • Zero Mandatory External Dependencies — Runs self-contained without Redis, Celery, or vector databases               │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

| Layer | Technologies |
|:---|:---|
| **Backend Framework** | Python 3.12 / 3.14, Django 6.1, Django REST Framework 3.16 |
| **AI / RAG Engine** | Google Gemini API (`gemini-3.1-flash-lite`), Custom BM25 Chunker & Retriever |
| **Document Processing** | `pdfplumber`, `pypdfium2`, `openpyxl`, `python-docx`, `Pillow`, `pytesseract` |
| **Database** | SQLite (Development) / PostgreSQL (Production ready via `dj-database-url`) |
| **Frontend** | Vanilla ES6+ JavaScript, Responsive CSS3, Single-Page Architecture |
| **GIS & 3D Visuals** | Leaflet 1.9.4, ArcGIS ESRI Map Tiles, Three.js 3D Strata |
| **Deployment** | Gunicorn, WhiteNoise, Render / Docker ready |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
* **Python:** 3.12 or 3.14 installed
* **Git:** Installed on your system

### 2. Clone the Repository
```bash
git clone https://github.com/shubhamjrd4559-sudo/AI-mining-proto.git
cd AI-mining-proto
```

### 3. Create & Activate Virtual Environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 5. Configure Environment Variables
Create a `.env` file inside the `backend/` directory (or update `backend/.env`):
```env
DEBUG=True
SECRET_KEY=your-secure-secret-key-here
ALLOWED_HOSTS=127.0.0.1,localhost

# Google Gemini API Key
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-3.1-flash-lite

# Development credentials
DEV_ADMIN_USER=admin
DEV_ADMIN_PASS=Dev_wXtnygAXRE_Ihjqq!9
```

### 6. Apply Migrations & Initialize
```bash
cd backend
python manage.py migrate
python manage.py seed_sample_mining_data
```

### 7. Run the Development Server
```bash
python manage.py runserver 127.0.0.1:8000
```

Open your browser and navigate to:  
👉 **[http://localhost:8000/](http://localhost:8000/)**

* **Default Admin Username:** `admin`  
* **Default Admin Password:** `Dev_wXtnygAXRE_Ihjqq!9`

---

## 📡 Key API Endpoints

| Endpoint | Method | Description |
|:---|:---:|:---|
| `/api/auth/token/` | `POST` | Authenticate and obtain DRF token |
| `/api/chat/` | `POST` | Natural language grounded AI Query (RAG Assistant) |
| `/api/documents/` | `GET`, `POST` | List and upload mining documents |
| `/api/documents/<id>/status/` | `GET` | Real-time extraction pipeline status |
| `/api/documents/<id>/retry/` | `POST` | Retry failed or queued document extraction |
| `/api/datasets/list/` | `GET` | List all structured tabular datasets |
| `/api/datasets/<id>/records/` | `GET` | Paginated records with filters & search |
| `/api/phase8/mines/` | `GET` | GIS verified mine locations with coordinates |
| `/api/phase8/geo3d/boreholes/`| `GET` | 3D borehole exploration coordinates & strata |
| `/api/audit/events/` | `GET` | Immutable system audit log trail |
| `/api/health/` | `GET` | System health check and component status |

---

## 📂 Project Directory Structure

```
AI-mining-proto/
├── 2026_FRONTEND_STRUCTURE.md      # Frontend architecture reference
├── 2026_IMPLEMENTATION_ROADMAP.md  # Comprehensive project roadmap (Phases 1–11)
├── README.md                       # Project documentation
├── index.html                      # Frontend Single-Page Application (SPA)
├── mine_statistics_data_*.csv      # 408 Verified National Coal Mines Dataset
├── readmy photo.png                # Dashboard preview screenshot
├── readmy photo2.png               # GIS Map preview screenshot
│
├── backend/
│   ├── config/                     # Django project configuration & settings
│   ├── manage.py                   # Django CLI utility
│   ├── requirements.txt            # Python dependencies
│   ├── templates/                  # Frontend SPA HTML template
│   └── apps/
│       ├── core/                   # Shared utilities, auth, stubs, seed commands
│       ├── documents/              # File upload, storage, lifecycle management
│       ├── pipeline/               # Multi-format extractors, OCR & validators
│       ├── intelligence/           # Gemini RAG assistant, chunker, query router
│       ├── datasets/               # Structured records, Data Explorer API
│       ├── analytics/              # Dynamic KPIs, aggregation & chart engines
│       ├── maintainer/             # Human-in-the-loop data cleaning suggestions
│       ├── reports/                # Multi-format report builder & exporters
│       ├── phase8/                 # GIS Map directory, 3D Borehole Strata, Topics
│       └── audit/                  # Immutable audit trail & compliance logging
```

---

## 📜 License & Acknowledgments
Developed for **Coal India Limited (CIL)** and **Central Mine Planning & Design Institute (CMPDI)** mining intelligence workflows.
All geological and mine statistics are aligned with official **Coal Directory of India** reporting standards.
