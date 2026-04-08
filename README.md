# 💧 LeakSense — Smart Expense Leak Detector

> **AI-powered expense analysis using Graph traversal (BFS/DFS), Constraint Satisfaction Problems (CSP), and A\* search — all in a single unified pipeline.**

---

## 📌 What is LeakSense?

LeakSense is a full-stack financial intelligence system that ingests your expense data, models it as a graph, checks it against budget constraints using a backtracking CSP solver, and ranks critical anomalies using the A\* algorithm. Results are surfaced in a premium dark-mode dashboard served directly from the FastAPI backend.

---

## 🗂️ Project Structure

```
Smart Expense Detector/
│
├── main.py                  # FastAPI app, route registration, frontend serving
├── database.py              # SQLite engine + SQLAlchemy session factory
├── models.py                # ORM models (Expense, Alert)
├── schemas.py               # Pydantic V2 validation schemas
├── seed_data.py             # Auto-seeds 33 sample expenses on first run
├── run.py                   # Cross-platform launcher (fixes Windows multiprocessing)
├── requirements.txt         # Python dependencies
├── sample_expenses.csv      # ← Sample CSV for testing (30 real-world expenses)
│
├── routes/
│   ├── expenses.py          # POST /expenses/upload, /upload/bulk, /upload/csv
│   ├── categories.py        # GET /categories, /categories/summary
│   ├── alerts.py            # GET /alerts, /alerts/stats
│   ├── graph.py             # GET /graph/build, /graph/bfs, /graph/dfs
│   ├── csp.py               # GET|POST /csp/check-budget
│   ├── anomalies.py         # GET /anomalies/prioritize
│   └── analyze.py           # GET /analyze-expenses  ← unified pipeline
│
├── services/
│   ├── alert_engine.py      # Rule-based alert detection (4 rule types)
│   ├── graph_utils.py       # Adjacency-list graph, BFS, DFS traversals
│   ├── csp_solver.py        # CSP engine: BudgetCSP backtracking solver + default budgets
│   ├── astar.py             # A* anomaly ranker: 5 detector types, max-heap priority
│   └── pipeline.py          # Unified orchestrator: Load → Graph → CSP → A* → Alerts
│
└── frontend/
    ├── index.html           # Main dashboard HTML
    ├── style.css            # All styles (dark theme, animations, glassmorphism)
    └── app.js               # Backend integration, rendering, local fallback
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+, FastAPI, Uvicorn |
| **Database** | SQLite via SQLAlchemy ORM |
| **Validation** | Pydantic V2 |
| **Algorithms** | Graph (BFS/DFS), CSP (Backtracking), A\* Search |
| **Frontend** | Vanilla HTML + CSS + JS (no framework) |
| **Fonts** | Syne, DM Mono, Instrument Serif (Google Fonts) |

---

## 🚀 Setup & Running

### 1. Prerequisites

- Python **3.10+** installed
- `pip` available in your terminal

### 2. Clone / Open the Project

```bash
cd "Smart Expense Detector"
```

### 3. Create a Virtual Environment (Recommended)

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` includes:
```
fastapi
uvicorn[standard]
sqlalchemy
pydantic
python-multipart
```

### 5. Start the Server

```bash
python run.py
```

The server starts at **http://localhost:8000**

> On first launch, 33 sample expenses are automatically seeded into the database.

---

## 🌐 Accessing the Application

| URL | Description |
|-----|-------------|
| `http://localhost:8000` | 🎨 LeakSense Dashboard (Frontend) |
| `http://localhost:8000/docs` | 📖 Interactive Swagger API Docs |
| `http://localhost:8000/redoc` | 📄 ReDoc API Reference |
| `http://localhost:8000/health` | ✅ Health check endpoint |

---

## 📊 API Endpoints Reference

### Expenses
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/expenses/upload` | Upload a single expense (JSON) |
| `POST` | `/expenses/upload/bulk` | Upload multiple expenses (JSON array) |
| `POST` | `/expenses/upload/csv` | Upload a CSV file |
| `GET`  | `/expenses` | List all expenses |
| `GET`  | `/expenses/{id}` | Get one expense by ID |

### Categories
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/categories` | List all categories |
| `GET` | `/categories/summary` | Category-wise spend totals |
| `GET` | `/categories/{name}/expenses` | Expenses in a category |

### Alerts
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/alerts` | All generated alerts |
| `GET` | `/alerts/stats` | Alert severity breakdown |
| `PATCH` | `/alerts/{id}/resolve` | Mark an alert as resolved |

### Graph Engine
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/graph/build` | Build the expense graph |
| `GET` | `/graph/bfs` | BFS traversal — top categories by spend |
| `GET` | `/graph/dfs` | DFS traversal — deep spending chains |

### CSP Budget Engine
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/csp/check-budget` | Check budgets with defaults |
| `POST` | `/csp/check-budget` | Check with custom budget limits |

### A\* Anomaly Ranker
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/anomalies/prioritize` | Rank all anomalies by f(n)=g(n)+h(n) |
| `GET` | `/anomalies/prioritize?top_n=5` | Top 5 ranked anomalies |
| `GET` | `/anomalies/prioritize?anomaly_type=DUPLICATE` | Filter by type |
| `GET` | `/anomalies/prioritize?min_severity=HIGH` | Filter by severity |

### Unified Pipeline
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/analyze-expenses` | Full pipeline: Graph + CSP + A\* in one call |
| `GET` | `/analyze-expenses?top_anomalies=10` | Control number of A\* results |

---

## 🧪 Testing with the Sample CSV

A ready-to-use test file is included: **`sample_expenses.csv`**

### Via the Dashboard (Recommended)
1. Open **http://localhost:8000**
2. Click **"Choose File"** in the upload zone (or drag-and-drop)
3. Select `sample_expenses.csv`
4. Click **"Detect Expense Leaks"**
5. View the full Graph + CSP + A\* report

### Via the API directly
```bash
# Upload the CSV
curl -X POST http://localhost:8000/expenses/upload/csv \
  -F "file=@sample_expenses.csv"

# Run the full analysis pipeline
curl http://localhost:8000/analyze-expenses
```

### CSV Format
```
id,date,amount,category,vendor,description
1,2026-03-01,250,Food,Zomato,Lunch order
```

| Column | Type | Example |
|--------|------|---------|
| `id` | int | `1` |
| `date` | string `YYYY-MM-DD` | `2026-03-01` |
| `amount` | float | `250` |
| `category` | string | `Food` |
| `vendor` | string | `Zomato` |
| `description` | string | `Lunch order` |

> **Note:** The `id` column is optional — the backend auto-assigns IDs if omitted.

---

## 🧠 Algorithm Details

### 1. Graph Engine (BFS + DFS)

Expenses are modeled as a directed graph:
- **Nodes**: `ROOT` → `Category:Food` → `Vendor:Zomato`
- **Edges**: Transactions with amount and date

```
ROOT
 ├── Category:Food
 │    ├── Vendor:Zomato      (₹250, ₹450, ₹1800…)
 │    └── Vendor:Swiggy      (₹300, ₹400…)
 └── Category:Transport
      └── Vendor:Uber        (₹1200, ₹900…)
```

- **BFS** — Level-wise traversal → finds the most frequent and highest-spend categories.
- **DFS** — Depth-first traversal → detects the deepest spending chains and hidden vendor hierarchies.

---

### 2. CSP Budget Engine (Backtracking)

Formally modeled as a Constraint Satisfaction Problem:

| CSP Component | Mapping |
|--------------|---------|
| **Variables** | Each `(month, category)` pair + each vendor + global total |
| **Domain** | `[warn_limit (80%), hard_limit (100%)]` |
| **Constraints** | `actual_spend ≤ budget_limit` |

The **backtracking solver** assigns actual spend values to variables and checks constraints, recording violations with severity (LOW / MEDIUM / HIGH / CRITICAL) and overspent % above limit.

**Default monthly budgets:**
```
Food         → ₹500/month      Travel       → ₹800/month
SaaS         → ₹400/month      Consulting   → ₹1,500/month
Utilities    → ₹300/month      Marketing    → ₹600/month
Office       → ₹250/month      ...
Total cap    → ₹10,000 all-time
```

---

### 3. A\* Anomaly Prioritization

Each detected anomaly is a search node ranked by:

```
f(n) = g(n) + h(n)
```

| Component | Definition |
|-----------|-----------|
| `g(n)` | Actual financial overspend in ₹ (known cost) |
| `h(n)` | `(occurrences / max_occurrences) × g(n)` (future impact heuristic) |
| `f(n)` | Total criticality score — higher = more urgent |

**Heuristic property:** `h(n) ≤ g(n)` always → **admissible** (never over-estimates).

**5 anomaly detectors:**
| Type | Description |
|------|-------------|
| `HIGH_SPEND` | Single transaction above per-category threshold |
| `DUPLICATE` | Same vendor + amount + date seen more than once |
| `CATEGORY_SPIKE` | Monthly spend ≥ 1.5× the category baseline |
| `VENDOR_DOMINANCE` | Vendor absorbs ≥ 30% of total spend |
| `RECURRING_VENDOR` | Vendor active across ≥ 2 distinct months |

---

### 4. Unified Pipeline (`/analyze-expenses`)

```
Step 1 — LOAD      :  Fetch all expenses from SQLite (single query)
Step 2 — GRAPH     :  Build adjacency list, run BFS + DFS, extract insights
Step 3 — CSP       :  Check monthly budgets, vendor thresholds, total cap
Step 4 — A*        :  Detect & rank anomalies by f-score
Step 5 — ALERTS    :  Merge + deduplicate CSP violations + A* anomalies
Step 6 — SUMMARY   :  Compliance score, severity counts, top recommendation
```

---

## 🔧 Customizing Budget Limits

### Via the API (POST body)
```bash
curl -X POST http://localhost:8000/csp/check-budget \
  -H "Content-Type: application/json" \
  -d '{
    "monthly_category_limits": {"Food": 300, "Shopping": 2000},
    "vendor_limits": {"Amazon": 3000},
    "total_cap": 20000
  }'
```

### In the code
Edit the constants in `services/csp_solver.py`:
```python
DEFAULT_MONTHLY_CATEGORY_BUDGETS = {
    "Food":     500.00,   # ← change this
    "Travel":   800.00,
    ...
}
DEFAULT_TOTAL_CAP = 10_000.00
```

---

## 🗄️ Database

- **Engine**: SQLite (`expenses.db`) — created automatically on first run
- **ORM**: SQLAlchemy
- **Tables**: `expenses`, `alerts`
- **Auto-seed**: 33 sample expenses loaded if the database is empty

To **reset** the database:
```bash
# Delete the SQLite file and restart
del expenses.db   # Windows
python run.py
```

---

## 🖥️ Frontend Dashboard

The LeakSense dashboard is served at `http://localhost:8000` and consists of:

| File | Role |
|------|------|
| `frontend/index.html` | Page structure, nav, hero, upload zone, results container |
| `frontend/style.css` | Dark theme, glassmorphism cards, animations, responsive layout |
| `frontend/app.js` | Backend API calls, result rendering, CSV parsing, local fallback |

**API integration flow in `app.js`:**
```
1. POST /expenses/upload/bulk   ← upload form rows
2. GET  /analyze-expenses       ← run full pipeline
3. renderResults(analysis)      ← display Graph + CSP + A* cards
   └─ if API offline → renderLocalFallback(rows)  ← JS-only analysis
```

---

## 📦 requirements.txt

```
fastapi
uvicorn[standard]
sqlalchemy
pydantic
python-multipart
```

Install with:
```bash
pip install -r requirements.txt
```

---

## 🏗️ Extending the Project

| Feature | Where to add |
|---------|-------------|
| New anomaly detector | `services/astar.py` → add `_detect_*` function |
| New budget constraint | `services/csp_solver.py` → add to `DEFAULT_MONTHLY_CATEGORY_BUDGETS` |
| New graph traversal | `services/graph_utils.py` → add traversal function |
| New API endpoint | Create in `routes/`, register in `main.py` |
| Binary CSP constraints | `services/csp_solver.py` → implement `_forward_check()` |

---

## 🐛 Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'fastapi'` | Run `pip install -r requirements.txt` |
| Port 8000 already in use | Change port in `run.py`: `port=8001` |
| CSS/JS not loading in browser | Hard-refresh with `Ctrl+Shift+R` |
| Database errors | Delete `expenses.db` and restart |
| IDE shows red imports | False positives from Pyrefly — server runs fine |

---

## 👤 Author

Built as a demonstration of AI/ML backend engineering concepts:
- **Graph theory** applied to financial data modelling
- **Constraint Satisfaction Problems** for budget rule enforcement
- **Informed search (A\*)** for anomaly prioritization
- **FastAPI** for scalable REST API design

---

*LeakSense — Find where your money leaks.*
