"""
main.py
-------
Application entry point for the Smart Expense Leak Detector API.

Startup sequence:
  1. Create all database tables (if they don't exist)
  2. Auto-seed dummy data (if the database is empty)
  3. Register all route modules
  4. Expose the FastAPI app object for Uvicorn

Run locally:
    uvicorn main:app --reload --port 8000

API docs available at:
    http://localhost:8000/docs        (Swagger UI)
    http://localhost:8000/redoc       (ReDoc)
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from database import engine
from models import Base
from routes import expenses, categories, alerts, graph, csp, anomalies, analyze


# ---------------------------------------------------------------------------
# Lifespan handler — runs on startup and shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Creates DB tables and seeds dummy data when the server starts.
    Uses the modern FastAPI lifespan pattern (replaces @app.on_event).
    """
    # Create all tables defined by our ORM models
    Base.metadata.create_all(bind=engine)

    # Auto-seed the database with sample data if it's empty
    try:
        from seed_data import seed_database
        seed_database()
    except Exception as e:
        print(f"⚠  Auto-seed skipped or failed: {e}")

    yield  # <-- Server runs here

    # (Cleanup logic, if needed, goes after yield)
    print(" Smart Expense Leak Detector shutting down.")


# ---------------------------------------------------------------------------
# FastAPI application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Smart Expense Leak Detector API",
    description=(
        "A scalable FastAPI backend for detecting expense anomalies, "
        "categorizing spend, and generating intelligent alerts for potential "
        "financial leaks in your organization. "
        "Includes graph-based expense modeling with BFS and DFS traversals "
        "for detecting spending patterns and hidden chains."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware
# Allow all origins in development — restrict in production
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Replace with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Register route modules
# ---------------------------------------------------------------------------

app.include_router(expenses.router)   # /expenses/*
app.include_router(categories.router) # /categories/*
app.include_router(alerts.router)     # /alerts/*
app.include_router(graph.router)      # /graph/*
app.include_router(csp.router)        # /csp/*
app.include_router(anomalies.router)  # /anomalies/*
app.include_router(analyze.router)    # /analyze-expenses

# ---------------------------------------------------------------------------
# Serve the frontend as static files
# ---------------------------------------------------------------------------

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")


# ---------------------------------------------------------------------------
# Root → serve index.html
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the LeakSense frontend dashboard."""
    idx = os.path.join(FRONTEND_DIR, "index.html")
    return FileResponse(idx) if os.path.isfile(idx) else {"status": "online", "docs": "/docs"}


@app.get("/style.css", include_in_schema=False)
def serve_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "style.css"), media_type="text/css")

@app.get("/app.js", include_in_schema=False)
def serve_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "app.js"), media_type="application/javascript")


@app.get("/health", tags=["Health"], summary="API health check")
def health_check():
    """Returns basic API status — useful for load balancer health probes."""
    return {
        "status":  "online",
        "service": "Smart Expense Leak Detector",
        "version": "1.0.0",
        "docs":    "/docs",
    }


@app.get("/health", tags=["Health"], summary="Detailed health check")
def detailed_health(db_check: bool = True):
    """Returns detailed health including database connectivity."""
    from database import SessionLocal
    db_status = "unknown"
    if db_check:
        try:
            db = SessionLocal()
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
            db_status = "connected"
            db.close()
        except Exception as e:
            db_status = f"error: {str(e)}"

    return {
        "status":   "healthy",
        "database": db_status,
        "service":  "Smart Expense Leak Detector",
    }
