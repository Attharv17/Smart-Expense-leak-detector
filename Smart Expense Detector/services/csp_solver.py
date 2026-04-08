"""
services/csp_solver.py
----------------------
Constraint Satisfaction Problem (CSP) engine for expense budget monitoring.

### Formal CSP Definition
  Variables   : Spending dimensions — one per (month × category), per vendor,
                and one global "total" variable.
  Domains     : For each variable, the domain is the set of candidate budget
                allocations {0, budget_limit}.  The *actual* observed spend is
                checked against whichever value the solver assigns; if the
                actual exceeds every domain value the constraint is violated.
  Constraints : Unary "≤" constraints — actual_spend ≤ budget_limit.

### Backtracking Solver
  The solver maintains a partial assignment and tries to extend it one
  variable at a time.  After assigning a variable it runs forward-checking
  (arc-consistency) to prune impossible future assignments early, then
  recurses.  If a branch fails (actual > limit) it backtracks and records
  the violation with full diagnostic information.

  Because every variable has exactly one relevant domain value (its budget
  limit) the search tree degenerates to a single branch per variable, but
  the backtracking structure remains algorithmically correct and makes it
  trivial to extend to multi-limit domains (e.g. warn / hard-stop tiers).

### Violation Severity Tiers
  LOW      : 0 %  < over-budget ≤ 20 %
  MEDIUM   : 20 % < over-budget ≤ 50 %
  HIGH     : 50 % < over-budget ≤ 100 %
  CRITICAL : over-budget > 100 %
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import sys
sys.setrecursionlimit(2000)   # safety for deep variable lists


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Variable:
    """
    One CSP variable representing a spending dimension.

    Attributes:
        name         : Unique key, e.g. "Category:Food:2024-01"
        actual_spend : Observed value drawn from the database.
        domain       : Ordered list of candidate budget limits to try.
                       The solver picks the first element whose constraint
                       is satisfied; if none is satisfied it records a violation.
        constraint_type : 'monthly_category' | 'vendor' | 'total'
        meta         : Extra context (month, category name, vendor name …)
    """
    name:            str
    actual_spend:    float
    domain:          List[float]          # candidate budget limits
    constraint_type: str
    meta:            Dict = field(default_factory=dict)


@dataclass
class Violation:
    """A single constraint violation detected by the CSP solver."""
    variable:        str
    constraint_type: str
    limit:           float
    actual:          float
    overspent:       float
    overspent_pct:   float
    severity:        str
    message:         str
    meta:            Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "variable":        self.variable,
            "constraint_type": self.constraint_type,
            "limit":           round(self.limit, 2),
            "actual":          round(self.actual, 2),
            "overspent":       round(self.overspent, 2),
            "overspent_pct":   round(self.overspent_pct, 1),
            "severity":        self.severity,
            "message":         self.message,
            **self.meta,
        }


# ---------------------------------------------------------------------------
# Severity helper
# ---------------------------------------------------------------------------

def _severity(pct: float) -> str:
    """Convert an over-budget percentage to a severity tier."""
    if pct <= 20:
        return "LOW"
    if pct <= 50:
        return "MEDIUM"
    if pct <= 100:
        return "HIGH"
    return "CRITICAL"


# ---------------------------------------------------------------------------
# CSP Solver
# ---------------------------------------------------------------------------

class BudgetCSP:
    """
    Backtracking CSP solver for expense budget constraints.

    Usage:
        csp = BudgetCSP()
        csp.add_variable(Variable(...))
        result = csp.solve()
    """

    def __init__(self):
        self._variables: List[Variable] = []

    # ── Public interface ────────────────────────────────────────────────────

    def add_variable(self, var: Variable) -> None:
        self._variables.append(var)

    def solve(self) -> Dict:
        """
        Run the backtracking search and return a structured result dict.
        """
        violations:   List[Violation] = []
        satisfied:    List[str]       = []
        assignment:   Dict[str, float]= {}    # var.name → chosen limit

        self._backtrack(
            variables  = list(self._variables),
            assignment = assignment,
            violations = violations,
            satisfied  = satisfied,
        )

        # ── Summary ──────────────────────────────────────────────────────
        total_vars = len(self._variables)
        sat_count  = len(satisfied)
        viol_dicts = [v.to_dict() for v in violations]

        # Worst violator by absolute overspend
        worst = max(violations, key=lambda v: v.overspent, default=None)

        # Compliance score: percentage of variables that satisfy constraints
        compliance = round(sat_count / total_vars * 100, 1) if total_vars else 100.0

        return {
            "status": (
                "all_constraints_satisfied"
                if not violations
                else "budget_violations_detected"
            ),
            "compliance_score_pct": compliance,
            "total_variables_checked": total_vars,
            "satisfied_count":  sat_count,
            "violations_count": len(violations),
            "worst_offender":   worst.to_dict() if worst else None,
            "violations":       viol_dicts,
            "satisfied":        satisfied,
        }

    # ── Core backtracking ───────────────────────────────────────────────────

    def _backtrack(
        self,
        variables:  List[Variable],
        assignment: Dict[str, float],
        violations: List[Violation],
        satisfied:  List[str],
    ) -> None:
        """
        Recursive backtracking over the variable list.

        For each variable we iterate its domain (ordered list of budget
        limits).  The first limit that satisfies  actual ≤ limit  is
        committed to the assignment and we recurse.  If *no* domain value
        satisfies the constraint, we record a violation using the smallest
        (tightest) limit and still continue — this gives us a complete
        violation scan rather than stopping at the first failure.
        """
        # Base case ─────────────────────────────────────────────────────
        if not variables:
            return

        var         = variables[0]
        remaining   = variables[1:]

        # Try each domain value (budget tier) in order ─────────────────
        consistent_limit: Optional[float] = None

        for limit in var.domain:
            if var.actual_spend <= limit:
                consistent_limit = limit
                break   # first consistent limit found → take it

        if consistent_limit is not None:
            # ── Constraint satisfied ──────────────────────────────────
            assignment[var.name] = consistent_limit
            satisfied.append(var.name)

            # Forward-checking: nothing to prune in a unary CSP, but
            # we call it explicitly to keep the structure extensible.
            self._forward_check(var, remaining)

        else:
            # ── Constraint violated — record it ───────────────────────
            # Use the tightest (smallest) domain value as the reference limit
            tightest_limit = min(var.domain) if var.domain else 0.0
            assignment[var.name] = tightest_limit    # mark as failed

            overspent     = var.actual_spend - tightest_limit
            overspent_pct = (overspent / tightest_limit * 100) if tightest_limit else 100.0
            severity      = _severity(overspent_pct)

            # Build human-readable message
            label = var.meta.get("label", var.name)
            month = var.meta.get("month", "")
            suffix = f" in {month}" if month else ""
            message = (
                f"Overspent ₹{overspent:,.2f} on {label}{suffix} "
                f"(Budget: ₹{tightest_limit:,.2f} | Actual: ₹{var.actual_spend:,.2f} | "
                f"{overspent_pct:.1f}% over)"
            )

            violations.append(Violation(
                variable        = var.name,
                constraint_type = var.constraint_type,
                limit           = tightest_limit,
                actual          = var.actual_spend,
                overspent       = overspent,
                overspent_pct   = overspent_pct,
                severity        = severity,
                message         = message,
                meta            = var.meta,
            ))

            # Backtrack: we do NOT commit, but we continue to the next
            # variable (complete violation search, not just first failure)

        # ── Recurse to next variable ──────────────────────────────────
        self._backtrack(remaining, assignment, violations, satisfied)

    # ── Forward-checking stub ───────────────────────────────────────────────

    @staticmethod
    def _forward_check(
        assigned_var: Variable,
        remaining:    List[Variable],
    ) -> None:
        """
        Arc-consistency / forward-checking hook.

        In a purely unary CSP there are no inter-variable arcs to prune.
        This method exists as an extension point: add binary constraints
        here (e.g. "Category A + Category B ≤ total cap") by narrowing
        the domains of `remaining` variables as needed.
        """
        pass   # no binary constraints yet — intentionally left as a hook


# ---------------------------------------------------------------------------
# Canonical default budget configuration (imported by routes/csp.py and
# services/pipeline.py — single source of truth)
# ---------------------------------------------------------------------------

DEFAULT_MONTHLY_CATEGORY_BUDGETS: dict[str, float] = {
    # Core business categories (original seed data)
    "Food":            500.00,    # ₹500/month food budget
    "Travel":          800.00,
    "Accommodation":   600.00,
    "SaaS":            400.00,
    "Utilities":       300.00,
    "Office Supplies": 250.00,
    "Marketing":       600.00,
    "Healthcare":      200.00,
    "Consulting":      1500.00,
    "Gifts":           150.00,
    "Parking":         100.00,
    "Hardware":        400.00,
    # Sample CSV categories
    "Transport":       1000.00,   # ₹1000/month transport budget
    "Shopping":        3000.00,   # ₹3000/month shopping budget
    "Entertainment":   500.00,    # ₹500/month entertainment budget
    "Rent":            12000.00,  # ₹12000/month rent budget
    "Subscriptions":   500.00,    # ₹500/month subscription budget
}

DEFAULT_VENDOR_BUDGETS: dict[str, float] = {
    # Original seed vendors
    "AWS":             800.00,
    "Slack":           600.00,
    "Make My Trip":    600.00,
    "Google Ads":      800.00,
    "Meta Ads":        800.00,
    "McKinsey & Co.": 2000.00,
    # Indian vendors from sample CSV
    "Zomato":          600.00,    # ₹600/month cap on Zomato
    "Swiggy":          400.00,    # ₹400/month cap on Swiggy
    "Uber":            1000.00,   # ₹1000/month cap on Uber
    "Ola":             800.00,    # ₹800/month cap on Ola
    "Amazon":          4000.00,   # ₹4000/month cap on Amazon
    "Flipkart":        3000.00,   # ₹3000/month cap on Flipkart
    "Netflix":         300.00,    # ₹300/month cap on Netflix
    "Restaurant":      1500.00,   # ₹1500/month cap on restaurant
}

DEFAULT_TOTAL_CAP: float = 30_000.00   # ₹30,000 total monthly cap

