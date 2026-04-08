"""
routes/analyze.py
-----------------
Unified /analyze-expenses endpoint.

Runs the full pipeline:
    Load → Graph → CSP → A* → Alert Factory → Summary

Returns one structured JSON document combining all four modules.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from services.pipeline import run_full_pipeline

router = APIRouter(tags=["Unified Pipeline"])


@router.get(
    "/analyze-expenses",
    summary="Full expense analysis pipeline (Graph + CSP + A*)",
    description=(
        "Runs the complete Smart Expense Leak Detector pipeline in one call:\n\n"
        "1. **Load** — fetch all expenses from the database\n"
        "2. **Graph** — build BFS/DFS graph; extract top categories and spending chains\n"
        "3. **CSP** — check monthly category budgets, vendor thresholds, and total cap\n"
        "4. **A\\*** — detect and rank anomalies by criticality score f(n) = g(n) + h(n)\n"
        "5. **Alerts** — merge CSP violations + A\\* anomalies into a unified alert list\n"
        "6. **Summary** — compliance score, severity breakdown, top recommendation\n\n"
        "All outputs are combined into a single JSON response."
    ),
)
def analyze_expenses(
    top_anomalies: int = Query(
        default=10,
        ge=1,
        le=50,
        description="How many A* top-priority anomalies to include (1–50).",
    ),
    db: Session = Depends(get_db),
):
    """
    Execute the unified analysis pipeline and return the full report.

    Response sections:
    - `meta`             — run timestamp, expense count, total spend
    - `graph_insights`   — BFS/DFS findings: top categories, spending chains
    - `csp_violations`   — budget constraint violations with ₹ amounts
    - `ranked_anomalies` — A*-ranked anomaly list with f/g/h scores
    - `alerts`           — merged, deduplicated, severity-sorted alert list
    - `summary`          — compliance %, severity counts, top recommendation
    """
    return run_full_pipeline(db=db, top_anomalies=top_anomalies)
