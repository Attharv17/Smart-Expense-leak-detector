"""
routes/csp.py
-------------
REST endpoint that drives the CSP budget-constraint solver.

Endpoint:
    GET  /csp/check-budget   — run CSP with built-in default budgets
    POST /csp/check-budget   — run CSP with caller-supplied custom budgets

Both variants:
  1. Aggregate live expense data from SQLite (by month × category,
     by vendor, and globally).
  2. Build a CSPVariable for each dimension with a domain drawn from
     the budget configuration.
  3. Hand off to BudgetCSP.solve() which runs the backtracking search.
  4. Return the full structured result.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Optional

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Expense
from services.csp_solver import (
    BudgetCSP, Variable,
    DEFAULT_MONTHLY_CATEGORY_BUDGETS,
    DEFAULT_VENDOR_BUDGETS,
    DEFAULT_TOTAL_CAP,
)

router = APIRouter(prefix="/csp", tags=["CSP Rules Engine"])

# Budget defaults are imported from services.csp_solver (single source of truth).
# They can be overridden at call time via the POST variant.


# ---------------------------------------------------------------------------
# Helper: build domain from a hard-stop limit (warn tier at 80 %)
# ---------------------------------------------------------------------------

def _make_domain(limit: float) -> list[float]:
    """
    Returns [warn_limit, hard_limit] so the solver can distinguish
    'approaching budget' (satisfied at warn level only) from truly OK.
    In our current unary setup both values satisfy the constraint if
    actual ≤ warn; only the hard limit is used when warn fails.
    We always expose both tiers for forward-compatibility.
    """
    warn = round(limit * 0.80, 2)
    return [warn, limit]


# ---------------------------------------------------------------------------
# Helper: aggregate expense data from DB
# ---------------------------------------------------------------------------

def _aggregate(db: Session):
    """
    Returns three aggregated dictionaries from live DB data:
      monthly_cat : { (month_str, category) → total_amount }
      vendor      : { vendor_name           → total_amount }
      total       : float
    """
    expenses = db.query(Expense).all()

    monthly_cat: Dict[tuple, float] = defaultdict(float)
    vendor_agg:  Dict[str, float]   = defaultdict(float)
    grand_total = 0.0

    for exp in expenses:
        # Parse year-month from date string "YYYY-MM-DD"
        try:
            month = exp.date[:7]   # e.g. "2024-01"
        except Exception:
            month = "unknown"

        monthly_cat[(month, exp.category)] += exp.amount
        vendor_agg[exp.vendor]             += exp.amount
        grand_total                        += exp.amount

    return monthly_cat, vendor_agg, grand_total


# ---------------------------------------------------------------------------
# Core solver factory
# ---------------------------------------------------------------------------

def _build_and_run_csp(
    db:               Session,
    monthly_budgets:  Dict[str, float],
    vendor_budgets:   Dict[str, float],
    total_cap:        float,
) -> Dict:
    """
    Aggregates data, creates CSP variables, and runs the backtracking solver.
    Returns the raw result dict from BudgetCSP.solve().
    """
    monthly_cat, vendor_agg, grand_total = _aggregate(db)

    csp = BudgetCSP()

    # ── 1. Monthly category variables ────────────────────────────────────
    # Variable per (month, category) pair that has a configured budget limit.
    for (month, cat), actual in sorted(monthly_cat.items()):
        limit = monthly_budgets.get(cat)
        if limit is None:
            continue   # no constraint defined for this category — skip

        csp.add_variable(Variable(
            name             = f"monthly:{month}:{cat}",
            actual_spend     = actual,
            domain           = _make_domain(limit),
            constraint_type  = "monthly_category",
            meta             = {
                "month":    month,
                "category": cat,
                "label":    cat,
            },
        ))

    # ── 2. Vendor variables ──────────────────────────────────────────────
    for vendor, actual in sorted(vendor_agg.items()):
        limit = vendor_budgets.get(vendor)
        if limit is None:
            continue

        csp.add_variable(Variable(
            name             = f"vendor:{vendor}",
            actual_spend     = actual,
            domain           = _make_domain(limit),
            constraint_type  = "vendor",
            meta             = {
                "vendor": vendor,
                "label":  vendor,
            },
        ))

    # ── 3. Global total variable ─────────────────────────────────────────
    csp.add_variable(Variable(
        name             = "total:all",
        actual_spend     = grand_total,
        domain           = _make_domain(total_cap),
        constraint_type  = "total",
        meta             = {"label": "Total Spending"},
    ))

    result = csp.solve()

    # Attach budget configuration to the response for transparency
    result["budget_config"] = {
        "monthly_category_limits": monthly_budgets,
        "vendor_limits":           vendor_budgets,
        "total_cap":               total_cap,
    }
    result["data_summary"] = {
        "total_expenses_amount": round(grand_total, 2),
        "unique_months":         len({k[0] for k in monthly_cat}),
        "unique_categories":     len({k[1] for k in monthly_cat}),
        "unique_vendors":        len(vendor_agg),
    }

    return result


# ---------------------------------------------------------------------------
# GET /csp/check-budget  — use built-in defaults
# ---------------------------------------------------------------------------

@router.get(
    "/check-budget",
    summary="Check spending violations using CSP (default budgets)",
    description=(
        "Runs the backtracking CSP solver against **pre-configured** monthly "
        "category budgets, vendor thresholds, and a global spending cap. "
        "Returns a full violation report with severity, ₹ amounts, and a "
        "compliance score. Use the POST variant to supply custom budgets."
    ),
)
def check_budget_default(db: Session = Depends(get_db)):
    """
    Evaluate all expenses in the database against the default budget constraints
    using the CSP backtracking engine.
    """
    return _build_and_run_csp(
        db              = db,
        monthly_budgets = DEFAULT_MONTHLY_CATEGORY_BUDGETS,
        vendor_budgets  = DEFAULT_VENDOR_BUDGETS,
        total_cap       = DEFAULT_TOTAL_CAP,
    )


# ---------------------------------------------------------------------------
# POST /csp/check-budget  — caller-supplied budgets
# ---------------------------------------------------------------------------

class CustomBudgetRequest:
    pass


@router.post(
    "/check-budget",
    summary="Check spending violations using CSP (custom budgets)",
    description=(
        "Same as the GET variant but accepts a JSON body so you can supply "
        "your own budget limits without modifying server code. Any field "
        "you omit falls back to the built-in defaults."
    ),
)
def check_budget_custom(
    monthly_category_limits: Optional[Dict[str, float]] = Body(
        default=None,
        description="Map of category → monthly budget limit in ₹",
        example={"Food": 400, "SaaS": 300},
    ),
    vendor_limits: Optional[Dict[str, float]] = Body(
        default=None,
        description="Map of vendor name → total spend threshold in ₹",
        example={"AWS": 500},
    ),
    total_cap: Optional[float] = Body(
        default=None,
        description="Global all-time total spending cap in ₹",
        example=8000.0,
    ),
    db: Session = Depends(get_db),
):
    """
    Evaluate expenses against caller-provided budget constraints.
    Falls back to the built-in defaults for any values not supplied.
    """
    merged_monthly = {**DEFAULT_MONTHLY_CATEGORY_BUDGETS, **(monthly_category_limits or {})}
    merged_vendor  = {**DEFAULT_VENDOR_BUDGETS,            **(vendor_limits or {})}
    merged_cap     = total_cap if total_cap is not None else DEFAULT_TOTAL_CAP

    return _build_and_run_csp(
        db              = db,
        monthly_budgets = merged_monthly,
        vendor_budgets  = merged_vendor,
        total_cap       = merged_cap,
    )
