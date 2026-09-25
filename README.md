# 🚀 Bulk Job Website → Excel Extractor

An autonomous, production-quality web application designed to extract thousands of job records from user-provided website URLs and export them into a cleanly formatted Excel spreadsheet.

Built with **FastAPI**, **Playwright (Chromium)**, **Pandas**, **OpenPyXL**, and a modern **React + TypeScript + Tailwind CSS** frontend.

---

## 🌟 Key Features

* **Autonomous Discovery**: No manual CSS selectors, XPaths, or field mapping required. Intelligently discovers job records via Schema.org JSON-LD (`JobPosting`), Next.js/Nuxt hydration payloads, and heuristic DOM repeated-card clustering.
* **Bulk Multi-Page Traversal**: Exhaustively crawls pagination sequences (`Next`, `›`, `»`, `?page=N`), dynamic JavaScript `Load More` / `Show More` buttons, and infinite scroll without arbitrary early cutoffs.
* **Strict Extraction Fields**: Extracts exactly:
  1. `Company Name`
  2. `Job Role`
  3. `Number of People` (Employee Count)
* **Smart Employee Count Normalization**: Converts values such as `"250 employees"`, `"1,250"`, and `"1.2K"` into clean numeric counts. Employs a strict fallback to `"N/A"` if unavailable—**never guesses, estimates, or hallucinates**.
* **In-Memory Session Caching**: Resolves employee counts from company profile pages when omitted on listing cards, caching results in memory to avoid redundant HTTP requests during the crawl session.
* **Stateless Architecture**: No external database (PostgreSQL, MySQL, SQLite, Redis) required. Data streams in-memory from Playwright to Pandas to OpenPyXL.
* **Real-time Live Progress Stream**: Server-Sent Events (SSE) update the dashboard in real time with pages processed, jobs discovered, unique companies found, duplicates pruned, and current activity status.
* **Professional Excel Output**: Formats `.xlsx` with bold headers, auto-filters, frozen top row, auto-fitted column dimensions, right-aligned numbers, and an extraction `Summary` worksheet.
* **Robust Security**: Built-in SSRF protection blocking localhost, private RFC-1918 subnets, and cloud metadata services.

---

## 🏗️ Architecture

```text
┌────────────────────────────────────────────────────────┐
│             React + TypeScript + Tailwind              │
│       (URL Input, Real-time SSE Progress, Download)    │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP & SSE (EventSource)
                            ▼
┌────────────────────────────────────────────────────────┐
│                 FastAPI Backend                        │
│   (/api/extraction/start, /progress, /download, /stop) │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             Extraction Orchestration Service           │
│       (Job State, Concurrency, SSE Event Emitter)      │
└─────────────┬────────────────────────────┬─────────────┘
              │                            │
              ▼                            ▼
┌───────────────────────────┐  ┌─────────────────────────┐
│     Playwright Crawler    │  │   Autonomous Extractors │
│ - Page Rendering          │  │ - JSON-LD / Hydration   │
│ - Pagination Detection    │  │ - DOM Repeated Cards    │
│ - Infinite Scroll Handler │  │ - Company Profile Cache │
│ - Loop / Cycle Prevention │  │ - Employee Count Parser │
└─────────────┬─────────────┘  └───────────┬─────────────┘
              │                            │
              └─────────────┬──────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│                 Processing Pipeline                    │
│ - DataCleaner (normalize text, whitespace, entities)   │
│ - DataValidator (mandatory fields, types)              │
│ - JobDeduplicator (URL primary, Company+Role fallback) │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                 OpenPyXL Excel Exporter                │
│ - 'Jobs' Sheet: Bold header, auto-filter, freeze pane  │
│ - 'Summary' Sheet: Execution statistics & metadata     │
│ - Output: jobs.xlsx                                    │
└────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, TypeScript, Tailwind CSS, Vite, Lucide Icons |
| **Backend API** | Python 3.12+, FastAPI, Pydantic v2, Pydantic Settings, Uvicorn |
| **Browser Automation**| Playwright, Chromium (Headless Shell) |
| **HTML Parsing** | BeautifulSoup4, lxml |
| **Data Processing** | Pandas |
| **Spreadsheet Output**| OpenPyXL |
| **Quality & Tests** | Pytest, Pytest-Asyncio, Ruff, Black, ESLint 9 |

---

## 📂 Project Structure

```text
job-data-extractor/
│
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── pyproject.toml
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── eslint.config.js
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── components/
│       │   ├── UrlInput.tsx
│       │   ├── ExtractionProgress.tsx
│       │   ├── ExtractionSummary.tsx
│       │   ├── StatusIndicator.tsx
│       │   └── DownloadButton.tsx
│       ├── pages/
│       │   └── HomePage.tsx
│       ├── services/
│       │   └── extractionApi.ts
│       ├── types/
│       │   └── extraction.ts
│       ├── hooks/
│       │   └── useExtraction.ts
│       ├── utils/
│       │   └── formatters.ts
│       └── styles/
│           └── globals.css
│
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── routes/
│   │   │       └── extraction.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   ├── models/
│   │   │   └── job.py
│   │   ├── schemas/
│   │   │   ├── extraction.py
│   │   │   └── job.py
│   │   ├── services/
│   │   │   ├── extraction_service.py
│   │   │   └── export_service.py
│   │   ├── scraper/
│   │   │   ├── browser.py
│   │   │   ├── crawler.py
│   │   │   ├── pagination.py
│   │   │   └── discovery.py
│   │   ├── extractors/
│   │   │   ├── job_extractor.py
│   │   │   ├── company_extractor.py
│   │   │   └── employee_extractor.py
│   │   ├── processors/
│   │   │   ├── cleaner.py
│   │   │   ├── deduplicator.py
│   │   │   └── validator.py
│   │   └── exporters/
│   │       └── excel.py
│   └── tests/
│       ├── unit/
│       │   ├── test_cleaner.py
│       │   ├── test_deduplicator.py
│       │   ├── test_employee_extractor.py
│       │   └── test_excel.py
│       ├── integration/
│       │   └── test_extraction_pipeline.py
│       └── fixtures/
│           └── sample_jobs.html
│
└── scripts/
    ├── setup.ps1
    └── setup.sh
```

---

## ⚡ Quick Start

### 1. Automated Setup

#### Windows (PowerShell):
```powershell
.\scripts\setup.ps1
```

#### Linux / macOS:
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

---

### 2. Manual Installation

#### Backend Setup
```bash
# Create Python virtual environment
python -m venv backend/.venv

# Activate environment
# Windows:
.\backend\.venv\Scripts\Activate.ps1
# macOS/Linux:
source backend/.venv/bin/activate

# Upgrade pip and install dependencies
pip install -r backend/requirements.txt

# Install Playwright Chromium browser
playwright install chromium
```

#### Frontend Setup
```bash
cd frontend
npm install
```

---

## 🚀 Running the Application

### 1. Start the Backend API
```powershell
# Option A (Recommended):
.\backend\.venv\Scripts\python -m backend.app.main

# Option B (Direct Uvicorn):
.\backend\.venv\Scripts\python -m uvicorn backend.app.main:app --port 8000 --reload --loop asyncio:ProactorEventLoop
```
API docs available at: `http://localhost:8000/docs`

### 2. Start the Frontend Application
```powershell
# In a separate terminal:
cd frontend
npm.cmd run dev
```
Open your browser at: `http://localhost:5173`

---

## 📊 Excel Output Format

The output file `jobs.xlsx` contains 2 worksheets:

### Sheet 1: `Jobs`
| Company Name | Job Role | Number of People |
| :--- | :--- | :---: |
| ABC Technologies | Software Engineer | 250 |
| XYZ Solutions | Backend Developer | 1,250 |
| Microsoft | Data Scientist | 228,000 |
| Stealth Startup | Frontend Engineer | N/A |

* **Bold slate headers**
* **Excel auto-filter** enabled across all columns
* **Frozen top row** (`ws.freeze_panes = "A2"`)
* **Auto-fitted column widths**
* **Numeric employee counts** formatted as integer values; missing values cleanly displayed as `"N/A"`

### Sheet 2: `Summary`
Contains execution audit metadata:
* Source URL
* Extraction Date (UTC)
* Total Jobs Extracted
* Unique Companies Found
* Duplicates Filtered Out
* Employee Counts Missing (N/A)
* Pages Processed

---

## 🧪 Testing & Quality Assurance

Run the complete test suite:
```bash
# Unit & Integration Tests (31 tests)
.\backend\.venv\Scripts\pytest -v backend/tests

# Code Quality & Linting
.\backend\.venv\Scripts\ruff check backend
.\backend\.venv\Scripts\black --check backend

# Frontend Lint & Production Build
cd frontend
npm run lint
npm run build
```

---

## 🔒 Security Guardrails

* **SSRF Protection**: Validates and restricts all target URLs. Rejects loopback addresses (`127.0.0.1`, `localhost`, `::1`), private networks (`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`), and cloud metadata APIs (`169.254.169.254`).
* **Domain Scope Limitation**: Prevents crawlers from chasing off-site ads, external redirects, or arbitrary web domains.
* **No Credential Storage**: Completely stateless utility with zero credentials or accounts stored.
