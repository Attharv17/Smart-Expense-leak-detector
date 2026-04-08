"""
services/pipeline.py
--------------------
Unified analysis pipeline for the Smart Expense Leak Detector.

Orchestration order
-------------------
  Step 1 — Load expenses from the database (single DB round-trip).
  Step 2 — Graph Engine  → build adjacency list, run BFS + DFS, extract insights.
  Step 3 — CSP Engine    → check every (month × category), vendor, and total
                           against budget constraints; collect violations.
  Step 4 — A* Engine     → detect and rank all anomaly types by f = g + h.
  Step 5 — Alert Factory → merge outputs from all three engines into a
                           deduplicated, severity-sorted alert list.
  Step 6 — Summarise     → aggregate counts, compliance score, top recommendation.

All three engines are imported from their existing modules — no logic is
duplicated here.  This file only wires them together and normalises the
combined output into a single, frontend-friendly response schema.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

# ── Existing engine imports ──────────────────────────────────────────────────
from services.graph_utils import build_graph, bfs_traversal, dfs_traversal, ROOT_NODE
from services.csp_solver  import (
    BudgetCSP, Variable,
    DEFAULT_MONTHLY_CATEGORY_BUDGETS,
    DEFAULT_VENDOR_BUDGETS,
    DEFAULT_TOTAL_CAP,
)
from services.astar import astar_prioritize
from models import Expense


# ---------------------------------------------------------------------------
# Step 2 helpers — Graph insights extractor
# ---------------------------------------------------------------------------

def _run_graph(expenses: List) -> Dict[str, Any]:
    """Build graph and extract condensed BFS / DFS insights."""
    graph = build_graph(expenses)

    bfs = bfs_traversal(graph, start=ROOT_NODE)
    dfs = dfs_traversal(graph, start=ROOT_NODE)

    # Keep only the insight summaries (not the full order lists) to
    # avoid bloating the unified response.
    return {
        "node_count":            len(graph),
        "edge_count":            sum(len(v) for v in graph.values()),
        "category_count":        sum(1 for n in graph if n.startswith("Category:")),
        "vendor_count":          sum(1 for n in graph if n.startswith("Vendor:")),
        "bfs": {
            "levels_found":          len(bfs.get("levels", {})),
            "top_spend_categories":  bfs["insights"].get("top_spend_categories",  [])[:5],
            "frequent_categories":   bfs["insights"].get("frequent_categories",   [])[:5],
            "total_nodes_visited":   bfs["insights"].get("total_nodes_visited",   0),
        },
        "dfs": {
            "total_chains_found":   dfs["insights"].get("total_chains_found",  0),
            "total_nodes_visited":  dfs["insights"].get("total_nodes_visited", 0),
            "deepest_chain":        dfs["insights"].get("deepest_chain"),
            "highest_spend_chain":  dfs["insights"].get("highest_spend_chain"),
        },
    }


# ---------------------------------------------------------------------------
# Step 3 helpers — CSP violation runner
# ---------------------------------------------------------------------------

def _make_domain(limit: float) -> List[float]:
    return [round(limit * 0.80, 2), limit]


def _run_csp(expenses: List) -> Dict[str, Any]:
    """Aggregate expenses and run the CSP backtracking solver."""
    from collections import defaultdict

    monthly: Dict[tuple, float]  = defaultdict(float)
    vendors: Dict[str, float]    = defaultdict(float)
    grand_total = 0.0

    for exp in expenses:
        month = exp.date[:7]
        monthly[(month, exp.category)] += exp.amount
        vendors[exp.vendor]            += exp.amount
        grand_total                    += exp.amount

    csp = BudgetCSP()

    for (month, cat), actual in sorted(monthly.items()):
        limit = DEFAULT_MONTHLY_CATEGORY_BUDGETS.get(cat)
        if limit is None:
            continue
        csp.add_variable(Variable(
            name             = f"monthly:{month}:{cat}",
            actual_spend     = actual,
            domain           = _make_domain(limit),
            constraint_type  = "monthly_category",
            meta             = {"month": month, "category": cat, "label": cat},
        ))

    for vendor, actual in sorted(vendors.items()):
        limit = DEFAULT_VENDOR_BUDGETS.get(vendor)
        if limit is None:
            continue
        csp.add_variable(Variable(
            name             = f"vendor:{vendor}",
            actual_spend     = actual,
            domain           = _make_domain(limit),
            constraint_type  = "vendor",
            meta             = {"vendor": vendor, "label": vendor},
        ))

    csp.add_variable(Variable(
        name             = "total:all",
        actual_spend     = grand_total,
        domain           = _make_domain(DEFAULT_TOTAL_CAP),
        constraint_type  = "total",
        meta             = {"label": "Total Spending"},
    ))

    result = csp.solve()
    return {
        "compliance_score_pct":   result["compliance_score_pct"],
        "total_vars_checked":     result["total_variables_checked"],
        "satisfied_count":        result["satisfied_count"],
        "violations_count":       result["violations_count"],
        "worst_offender":         result["worst_offender"],
        "violations":             result["violations"],
    }


# ---------------------------------------------------------------------------
# Step 4 helpers — A* anomaly prioritizer
# ---------------------------------------------------------------------------

def _run_astar(expenses: List, top_n: int = 15) -> Dict[str, Any]:
    """Detect and rank anomalies using A* priority search."""
    result = astar_prioritize(expenses, top_n=top_n)
    return {
        "total_detected":   result["total_detected"],
        "algorithm_details": result["algorithm_details"],
        "top_anomalies":    result["anomalies"],
    }


# ---------------------------------------------------------------------------
# Step 5 — Alert Factory
# ---------------------------------------------------------------------------

_SEV_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _make_alert(
    message:  str,
    severity: str,
    source:   str,
    meta:     Dict,
) -> Dict:
    return {
        "alert_id": str(uuid.uuid4())[:8],
        "message":  message,
        "severity": severity,
        "source":   source,
        **meta,
    }


def _alerts_from_csp(violations: List[Dict]) -> List[Dict]:
    """Convert CSP violation dicts into the unified alert format."""
    alerts = []
    for v in violations:
        ctype = v["constraint_type"]
        label = v.get("label", v["variable"])
        month = v.get("month", "")

        if ctype == "monthly_category":
            msg = (
                f"₹{v['overspent']:,.2f} overspent on {label}"
                + (f" in {month}" if month else "")
                + f" — budget ₹{v['limit']:,.2f}, actual ₹{v['actual']:,.2f}"
                  f" ({v['overspent_pct']:.1f}% over)"
            )
            meta = {"category": label, "month": month}
        elif ctype == "vendor":
            msg = (
                f"₹{v['overspent']:,.2f} over vendor threshold for {label} "
                f"— budget ₹{v['limit']:,.2f}, actual ₹{v['actual']:,.2f}"
                f" ({v['overspent_pct']:.1f}% over)"
            )
            meta = {"vendor": label}
        else:  # total
            msg = (
                f"₹{v['overspent']:,.2f} over total spending cap "
                f"— budget ₹{v['limit']:,.2f}, actual ₹{v['actual']:,.2f}"
                f" ({v['overspent_pct']:.1f}% over)"
            )
            meta = {}

        alerts.append(_make_alert(msg, v["severity"], "CSP", meta))
    return alerts


def _alerts_from_astar(anomalies: List[Dict]) -> List[Dict]:
    """Convert A* anomaly dicts into the unified alert format."""
    alerts = []
    for a in anomalies:
        atype = a["anomaly_type"]
        sev   = a["severity"]

        if atype == "HIGH_SPEND":
            msg  = (
                f"₹{a['g_score']:,.2f} single-transaction spike at {a.get('vendor')} "
                f"({a.get('category')}) on {a.get('date')} — "
                f"₹{a.get('amount', 0):,.2f} vs threshold ₹{a.get('threshold', 0):,.2f}"
            )
            meta = {"vendor": a.get("vendor"), "category": a.get("category"),
                    "expense_id": a.get("expense_id")}

        elif atype == "DUPLICATE":
            msg  = (
                f"Duplicate charge of ₹{a.get('amount', 0):,.2f} at {a.get('vendor')} "
                f"on {a.get('date')} — seen {a.get('duplicate_count', 2)} times"
            )
            meta = {"vendor": a.get("vendor"), "expense_ids": a.get("expense_ids")}

        elif atype == "CATEGORY_SPIKE":
            msg  = (
                f"₹{a['g_score']:,.2f} excess in {a.get('category')} "
                f"during {a.get('month')} — "
                f"{a.get('spike_ratio', '?')}× the usual spend "
                f"(avg ₹{a.get('baseline_avg', 0):,.2f})"
            )
            meta = {"category": a.get("category"), "month": a.get("month")}

        elif atype == "VENDOR_DOMINANCE":
            msg  = (
                f"{a.get('vendor')} absorbed {a.get('pct_of_total', 0):.1f}% "
                f"of total spend (₹{a.get('total_spent', 0):,.2f}) — "
                f"potential over-reliance"
            )
            meta = {"vendor": a.get("vendor")}

        else:   # RECURRING_VENDOR
            msg  = (
                f"Recurring vendor: {a.get('vendor')} active in "
                f"{a.get('month_count', 0)} months "
                f"(₹{a.get('total_spent', 0):,.2f} total)"
            )
            meta = {"vendor": a.get("vendor"),
                    "active_months": a.get("active_months", [])}

        alerts.append(_make_alert(msg, sev, "A*", meta))
    return alerts


def _merge_and_sort_alerts(
    csp_alerts:   List[Dict],
    astar_alerts: List[Dict],
) -> List[Dict]:
    """
    Deduplicate (same vendor/category + same severity) and sort
    CRITICAL → HIGH → MEDIUM → LOW, then by source (CSP first).
    """
    seen: set[str] = set()
    merged: List[Dict] = []

    for alert in csp_alerts + astar_alerts:
        # Build a lightweight fingerprint for dedup
        key = (
            alert.get("source"),
            alert.get("severity"),
            alert.get("category", ""),
            alert.get("vendor",   ""),
            alert.get("month",    ""),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(alert)

    # Sort: severity desc, then source (CSP before A*)
    merged.sort(
        key=lambda a: (
            -_SEV_ORDER.get(a["severity"], 0),
            0 if a["source"] == "CSP" else 1,
        )
    )
    return merged


# ---------------------------------------------------------------------------
# Step 6 — Summary builder
# ---------------------------------------------------------------------------

def _summarise(alerts: List[Dict], csp: Dict, astar: Dict) -> Dict:
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for a in alerts:
        counts[a["severity"]] = counts.get(a["severity"], 0) + 1

    # Pick top recommendation from the highest-priority alert
    top_alert = alerts[0] if alerts else None
    recommendation = (
        f"Immediate action required: {top_alert['message']}"
        if top_alert and top_alert["severity"] in ("CRITICAL", "HIGH")
        else "Spending is within acceptable limits — review LOW/MEDIUM alerts periodically."
        if top_alert
        else "No budget violations detected."
    )

    return {
        "total_alerts":    len(alerts),
        "by_severity":     counts,
        "compliance_pct":  csp["compliance_score_pct"],
        "anomalies_found": astar["total_detected"],
        "top_recommendation": recommendation,
    }


# ---------------------------------------------------------------------------
# Main pipeline entrypoint
# ---------------------------------------------------------------------------

def run_full_pipeline(db: Session, top_anomalies: int = 10) -> Dict[str, Any]:
    """
    Execute the complete analysis pipeline and return a unified report.

    Parameters
    ----------
    db            : Active SQLAlchemy session.
    top_anomalies : How many A* top-ranked anomalies to include.

    Returns
    -------
    A single dict with keys:
        meta, graph_insights, csp_violations,
        ranked_anomalies, alerts, summary
    """
    # ── Step 1: Load expenses (single query) ─────────────────────────────────
    expenses = db.query(Expense).order_by(Expense.date.asc()).all()
    expense_count = len(expenses)
    total_spend   = round(sum(e.amount for e in expenses), 2)

    if expense_count == 0:
        return {
            "meta":    {"expense_count": 0, "total_spend": 0.0},
            "message": "No expenses found in database. Upload expenses first.",
        }

    # ── Step 2: Graph ─────────────────────────────────────────────────────────
    graph_insights = _run_graph(expenses)

    # ── Step 3: CSP ──────────────────────────────────────────────────────────
    csp_result = _run_csp(expenses)

    # ── Step 4: A* ───────────────────────────────────────────────────────────
    astar_result = _run_astar(expenses, top_n=top_anomalies)

    # ── Step 5: Alert factory ─────────────────────────────────────────────────
    csp_alerts   = _alerts_from_csp(csp_result["violations"])
    astar_alerts = _alerts_from_astar(astar_result["top_anomalies"])
    alerts       = _merge_and_sort_alerts(csp_alerts, astar_alerts)

    # ── Step 6: Summary ───────────────────────────────────────────────────────
    summary = _summarise(alerts, csp_result, astar_result)

    return {
        "meta": {
            "expense_count":  expense_count,
            "total_spend":    total_spend,
            "pipeline_ran_at": datetime.now(timezone.utc).isoformat(),
            "pipeline_stages": ["Load", "Graph", "CSP", "A*", "Alerts", "Summary"],
        },
        "graph_insights":  graph_insights,
        "csp_violations":  csp_result,
        "ranked_anomalies": astar_result,
        "alerts":          alerts,
        "summary":         summary,
    }
