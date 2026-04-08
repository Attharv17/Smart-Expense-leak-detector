"""
routes/anomalies.py
-------------------
REST endpoint that exposes the A* anomaly prioritization engine.

  GET  /anomalies/prioritize            — run with defaults (top 10)
  GET  /anomalies/prioritize?top_n=5    — customize result count
  GET  /anomalies/prioritize?type=HIGH_SPEND  — filter by anomaly type
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Expense
from services.astar import astar_prioritize

router = APIRouter(prefix="/anomalies", tags=["A* Anomaly Prioritization"])

VALID_TYPES = {
    "HIGH_SPEND", "DUPLICATE", "CATEGORY_SPIKE",
    "VENDOR_DOMINANCE", "RECURRING_VENDOR",
}


@router.get(
    "/prioritize",
    summary="Rank critical expense anomalies using A* search",
    description=(
        "Scans all expenses and ranks detected anomalies using the **A\\* algorithm**.\n\n"
        "**f(n) = g(n) + h(n)**\n"
        "- `g(n)` = actual financial overspend (₹) — concrete cost already incurred\n"
        "- `h(n)` = frequency-weighted future impact heuristic — how likely this pattern repeats\n\n"
        "Anomaly types detected:\n"
        "- `HIGH_SPEND` — single transaction above threshold\n"
        "- `DUPLICATE` — same vendor × amount × date repeated\n"
        "- `CATEGORY_SPIKE` — a month's spend spikes above the category baseline\n"
        "- `VENDOR_DOMINANCE` — one vendor absorbs ≥ 30% of all spend\n"
        "- `RECURRING_VENDOR` — hidden subscriptions active across multiple months\n"
    ),
)
def prioritize_anomalies(
    top_n: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Number of top-priority anomalies to return (1–100).",
    ),
    anomaly_type: Optional[str] = Query(
        default=None,
        description=(
            "Filter results to a specific anomaly type: "
            "HIGH_SPEND | DUPLICATE | CATEGORY_SPIKE | VENDOR_DOMINANCE | RECURRING_VENDOR"
        ),
    ),
    min_severity: Optional[str] = Query(
        default=None,
        description="Minimum severity to include: LOW | MEDIUM | HIGH | CRITICAL",
    ),
    db: Session = Depends(get_db),
):
    """
    Returns the top-N most critical expense anomalies ranked by A* f-score.

    Each result includes:
    - `rank`         — position in the priority order (1 = most critical)
    - `f_score`      — combined criticality score  (g + h)
    - `g_score`      — actual overspend in ₹
    - `h_score`      — projected future impact (heuristic)
    - `severity`     — LOW | MEDIUM | HIGH | CRITICAL
    - `description`  — human-readable explanation
    - `anomaly_type` — category of the detected issue
    """
    # Validate anomaly_type filter
    if anomaly_type:
        anomaly_type = anomaly_type.upper()
        if anomaly_type not in VALID_TYPES:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid anomaly_type '{anomaly_type}'. "
                    f"Choose from: {', '.join(sorted(VALID_TYPES))}"
                ),
            )

    # Severity ordering for filter
    severity_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    min_sev_rank = 0
    if min_severity:
        min_sev_rank = severity_order.get(min_severity.upper(), 0)

    # Load all expenses and run A*
    expenses = db.query(Expense).order_by(Expense.date.asc()).all()

    # Request more than needed so we can post-filter without re-running
    fetch_n = top_n * 5 if (anomaly_type or min_severity) else top_n
    result = astar_prioritize(expenses, top_n=min(fetch_n, 200))

    # Post-filter by type and severity
    filtered = result["anomalies"]
    if anomaly_type:
        filtered = [a for a in filtered if a["anomaly_type"] == anomaly_type]
    if min_severity:
        filtered = [
            a for a in filtered
            if severity_order.get(a["severity"], 0) >= min_sev_rank
        ]

    # Re-rank after filtering and cap at top_n
    filtered = filtered[:top_n]
    for i, item in enumerate(filtered, start=1):
        item["rank"] = i

    result["anomalies"]       = filtered
    result["top_n"]           = len(filtered)
    result["filters_applied"] = {
        "anomaly_type": anomaly_type,
        "min_severity": min_severity,
    }

    return result
