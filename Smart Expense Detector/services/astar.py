"""
services/astar.py
-----------------
A* Search Algorithm for prioritizing expense anomalies.

### Why A* for anomaly ranking?
Classical A* finds the *optimal path* in a graph by expanding nodes in
order of f(n) = g(n) + h(n).  Here we repurpose this idea as an
*informed priority ranking*:

    • Each anomaly is a search node.
    • g(n) — concrete, known cost   = actual financial overspend (₹)
    • h(n) — forward-looking cost   = estimated future impact, modelled
                                      as a frequency-weighted projection
                                      of the overspend if the pattern
                                      continues at its observed rate.
    • f(n) = g(n) + h(n)            = total criticality score.

The algorithm inserts all anomaly nodes into a min-heap keyed by -f(n)
(negated so the heap becomes a max-priority queue — highest criticality
first).  It then extracts the top-N nodes in O((N + K) log K) time where
K is the total number of anomalies.

### Anomaly types detected
1. HIGH_SPEND         — single transaction above a per-category threshold.
2. DUPLICATE          — same vendor × amount × date seen > once.
3. CATEGORY_SPIKE     — a month's category spend is ≥ SPIKE_RATIO × avg.
4. VENDOR_DOMINANCE   — one vendor absorbs ≥ DOMINANCE_PCT of total spend.
5. RECURRING_VENDOR   — a vendor appears in ≥ MIN_RECURRENCE months (good
                         for catching forgotten subscriptions / shadow-IT).

### Heuristic h(n) design  (admissible & consistent)
    h(n) = (occurrences / max_occurrences_in_dataset) × g(n)

Interpretation: if this anomaly type has been observed MAX times it is
assumed to recur at full rate → h = g (doubles the score). If seen
only once h → 0 (no forward-looking penalty).

This keeps h(n) ≤ g(n) which preserves the admissibility property
(never over-estimates future cost), making the ranking consistent with
classical A* guarantees on optimality of the extracted ordering.
"""

from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Tuneable thresholds
# ---------------------------------------------------------------------------

HIGH_SPEND_THRESHOLDS: Dict[str, float] = {
    # Per-category single-transaction alert thresholds (₹)
    "Food":            300.0,
    "Travel":          500.0,
    "Accommodation":   400.0,
    "SaaS":            250.0,
    "Utilities":       300.0,
    "Office Supplies": 200.0,
    "Marketing":       600.0,
    "Healthcare":      150.0,
    "Consulting":      1000.0,
    "Gifts":           100.0,
    "Parking":         80.0,
    "Hardware":        300.0,
    "__default__":     400.0,   # fallback for unlisted categories
}

SPIKE_RATIO      = 1.5    # flag if month spend ≥ 1.5× that category's average
DOMINANCE_PCT    = 30.0   # flag a vendor that takes ≥ 30 % of total spend
MIN_RECURRENCE   = 2      # flag vendors seen in ≥ N distinct months


# ---------------------------------------------------------------------------
# AnomalyNode — the unit inserted into the A* priority queue
# ---------------------------------------------------------------------------

@dataclass
class AnomalyNode:
    """
    Represents one detected expense anomaly.

    Attributes
    ----------
    anomaly_id   : Unique deterministic key for this node.
    anomaly_type : One of HIGH_SPEND | DUPLICATE | CATEGORY_SPIKE |
                   VENDOR_DOMINANCE | RECURRING_VENDOR.
    description  : Human-readable summary.
    g_score      : Concrete financial cost — actual overspend in ₹.
    h_score      : Forward-looking heuristic cost — estimated future impact.
    f_score      : g + h — total criticality used by the priority queue.
    severity     : LOW | MEDIUM | HIGH | CRITICAL derived from f_score.
    meta         : Extra context dict (category, vendor, month, …).
    occurrences  : How many times this anomaly pattern was observed.
    """
    anomaly_id:   str
    anomaly_type: str
    description:  str
    g_score:      float
    h_score:      float
    f_score:      float   = field(init=False)
    severity:     str     = field(init=False)
    meta:         Dict    = field(default_factory=dict)
    occurrences:  int     = 1

    def __post_init__(self):
        self.f_score  = round(self.g_score + self.h_score, 2)
        self.severity = _severity(self.f_score)

    # heapq comparisons — needed when f_scores are equal
    def __lt__(self, other: "AnomalyNode"):
        return self.f_score > other.f_score   # higher f = higher priority


def _severity(f: float) -> str:
    if f >= 1000:  return "CRITICAL"
    if f >= 400:   return "HIGH"
    if f >= 150:   return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Heuristic h(n)
# ---------------------------------------------------------------------------

def compute_heuristic(g_score: float, occurrences: int, max_occurrences: int) -> float:
    """
    h(n) = (occurrences / max_occurrences) × g(n)

    Rationale
    ---------
    • An anomaly seen max_occurrences times is the most recurring pattern;
      its projected future impact equals its current overspend → h = g.
    • An anomaly seen only once has min recurrence → h ≈ 0.
    • h(n) ≤ g(n) always, so the heuristic is admissible.
    """
    if max_occurrences <= 0:
        return 0.0
    ratio = occurrences / max_occurrences
    return round(g_score * ratio, 2)


# ---------------------------------------------------------------------------
# Anomaly detectors — each returns a list of raw (anomaly_id, type, g, occ, meta)
# ---------------------------------------------------------------------------

def _detect_high_spend(expenses) -> List[Tuple]:
    """Flag single transactions exceeding per-category thresholds."""
    results = []
    for exp in expenses:
        threshold = HIGH_SPEND_THRESHOLDS.get(exp.category,
                    HIGH_SPEND_THRESHOLDS["__default__"])
        if exp.amount > threshold:
            overspend = exp.amount - threshold
            results.append((
                f"high_spend:{exp.id}",
                "HIGH_SPEND",
                overspend,
                1,
                {
                    "expense_id": exp.id,
                    "date":       exp.date,
                    "vendor":     exp.vendor,
                    "category":   exp.category,
                    "amount":     exp.amount,
                    "threshold":  threshold,
                },
            ))
    return results


def _detect_duplicates(expenses) -> List[Tuple]:
    """Flag (vendor, amount, date) groups with more than one transaction."""
    seen: Dict[Tuple, List[int]] = defaultdict(list)
    for exp in expenses:
        key = (exp.vendor, exp.amount, exp.date)
        seen[key].append(exp.id)

    results = []
    for (vendor, amount, date), ids in seen.items():
        if len(ids) > 1:
            results.append((
                f"duplicate:{vendor}:{amount}:{date}",
                "DUPLICATE",
                amount * (len(ids) - 1),   # extra ₹ paid relative to one tx
                len(ids),
                {
                    "vendor":       vendor,
                    "amount":       amount,
                    "date":         date,
                    "expense_ids":  ids,
                    "duplicate_count": len(ids),
                },
            ))
    return results


def _detect_category_spikes(expenses) -> List[Tuple]:
    """
    For each (month, category) compute spend vs. that category's
    all-time monthly average.  Flag months ≥ SPIKE_RATIO × average.
    """
    # Running totals per (month, category)
    monthly: Dict[Tuple[str, str], float] = defaultdict(float)
    # All-time monthly totals per category (for averaging)
    cat_months: Dict[str, List[float]]    = defaultdict(list)

    for exp in expenses:
        month = exp.date[:7]
        monthly[(month, exp.category)] += exp.amount

    for (month, cat), total in monthly.items():
        cat_months[cat].append(total)

    results = []
    for (month, cat), actual in monthly.items():
        averages = cat_months[cat]
        if len(averages) < 2:
            continue   # need at least 2 months to establish a baseline
        avg = (sum(averages) - actual) / (len(averages) - 1)  # leave-one-out avg
        if avg <= 0:
            continue
        if actual >= avg * SPIKE_RATIO:
            overspend = actual - avg
            results.append((
                f"spike:{cat}:{month}",
                "CATEGORY_SPIKE",
                overspend,
                1,
                {
                    "category":     cat,
                    "month":        month,
                    "actual":       actual,
                    "baseline_avg": round(avg, 2),
                    "spike_ratio":  round(actual / avg, 2),
                },
            ))
    return results


def _detect_vendor_dominance(expenses) -> List[Tuple]:
    """Flag any vendor that consumes ≥ DOMINANCE_PCT of total spend."""
    vendor_totals: Dict[str, float] = defaultdict(float)
    grand_total = 0.0
    for exp in expenses:
        vendor_totals[exp.vendor] += exp.amount
        grand_total += exp.amount

    if grand_total == 0:
        return []

    results = []
    for vendor, total in vendor_totals.items():
        pct = total / grand_total * 100
        if pct >= DOMINANCE_PCT:
            overspend = total - (grand_total * DOMINANCE_PCT / 100)
            results.append((
                f"dominance:{vendor}",
                "VENDOR_DOMINANCE",
                overspend,
                1,
                {
                    "vendor":       vendor,
                    "total_spent":  round(total, 2),
                    "pct_of_total": round(pct, 1),
                    "grand_total":  round(grand_total, 2),
                },
            ))
    return results


def _detect_recurring_vendors(expenses) -> List[Tuple]:
    """Flag vendors active in ≥ MIN_RECURRENCE distinct calendar months."""
    vendor_months: Dict[str, set] = defaultdict(set)
    vendor_totals: Dict[str, float] = defaultdict(float)

    for exp in expenses:
        vendor_months[exp.vendor].add(exp.date[:7])
        vendor_totals[exp.vendor] += exp.amount

    results = []
    for vendor, months in vendor_months.items():
        n = len(months)
        if n >= MIN_RECURRENCE:
            # g = total spend on this vendor (recurring cost)
            total = vendor_totals[vendor]
            results.append((
                f"recurring:{vendor}",
                "RECURRING_VENDOR",
                total,       # g = total financial exposure
                n,           # occurrences = number of active months
                {
                    "vendor":         vendor,
                    "active_months":  sorted(months),
                    "month_count":    n,
                    "total_spent":    round(total, 2),
                },
            ))
    return results


# ---------------------------------------------------------------------------
# A* prioritization
# ---------------------------------------------------------------------------

def astar_prioritize(expenses: list, top_n: int = 10) -> Dict:
    """
    Run A* over the detected expense anomalies and return the top-N
    most critical ones ranked by f(n) = g(n) + h(n).

    Algorithm
    ---------
    1. Collect all raw detections from every detector.
    2. Normalise occurrence counts to compute max_occurrences globally.
    3. For each detection compute h(n) and build an AnomalyNode.
    4. Push every node into a max-heap keyed by f(n).
    5. Pop up to top_n nodes — this is the A* extraction step.

    Parameters
    ----------
    expenses : List of Expense ORM objects from the database.
    top_n    : Number of highest-priority anomalies to return.

    Returns
    -------
    Dict with keys: anomalies, total_detected, top_n, algorithm_details.
    """

    # ── Step 1: Detect all anomalies ────────────────────────────────────────
    raw: List[Tuple] = []
    raw.extend(_detect_high_spend(expenses))
    raw.extend(_detect_duplicates(expenses))
    raw.extend(_detect_category_spikes(expenses))
    raw.extend(_detect_vendor_dominance(expenses))
    raw.extend(_detect_recurring_vendors(expenses))

    if not raw:
        return {
            "status":         "no_anomalies_detected",
            "total_detected": 0,
            "top_n":          top_n,
            "anomalies":      [],
        }

    # ── Step 2: Compute global max_occurrences for heuristic normalisation ──
    max_occurrences = max(occ for *_, occ, _ in raw) if raw else 1

    # ── Step 3 & 4: Build nodes and push onto the max-heap ──────────────────
    #   heapq is a min-heap; we negate f(n) to get max-heap behaviour.
    heap: List[Tuple] = []
    counter = 0   # tie-breaker to avoid comparing AnomalyNode objects

    for (anomaly_id, atype, g, occ, meta) in raw:
        h = compute_heuristic(g, occ, max_occurrences)
        node = AnomalyNode(
            anomaly_id   = anomaly_id,
            anomaly_type = atype,
            description  = _build_description(atype, meta, g, h),
            g_score      = round(g, 2),
            h_score      = round(h, 2),
            meta         = meta,
            occurrences  = occ,
        )
        # Push (-f_score, counter, node) — negated for max-heap
        heapq.heappush(heap, (-node.f_score, counter, node))
        counter += 1

    # ── Step 5: Extract top-N (A* expansion step) ───────────────────────────
    extracted: List[AnomalyNode] = []
    while heap and len(extracted) < top_n:
        _, _, node = heapq.heappop(heap)
        extracted.append(node)

    # ── Serialise and return ────────────────────────────────────────────────
    rank = 1
    serialized = []
    for node in extracted:
        serialized.append({
            "rank":         rank,
            "anomaly_id":   node.anomaly_id,
            "anomaly_type": node.anomaly_type,
            "description":  node.description,
            "g_score":      node.g_score,
            "h_score":      node.h_score,
            "f_score":      node.f_score,
            "severity":     node.severity,
            "occurrences":  node.occurrences,
            **node.meta,
        })
        rank += 1

    return {
        "status":         "anomalies_prioritized",
        "total_detected": len(raw),
        "top_n":          len(extracted),
        "algorithm_details": {
            "algorithm":         "A* (informed priority search)",
            "g_n_definition":    "Actual financial overspend in ₹",
            "h_n_definition":    "Frequency-weighted future impact: (occurrences / max_occurrences) × g(n)",
            "f_n_definition":    "f(n) = g(n) + h(n) — total criticality score",
            "heuristic_property":"Admissible (h ≤ g always) — never over-estimates",
            "max_occurrences_observed": max_occurrences,
        },
        "anomalies": serialized,
    }


# ---------------------------------------------------------------------------
# Description builder
# ---------------------------------------------------------------------------

def _build_description(atype: str, meta: Dict, g: float, h: float) -> str:
    if atype == "HIGH_SPEND":
        return (
            f"Single transaction of ₹{meta['amount']:,.2f} at {meta['vendor']} "
            f"({meta['category']}) exceeds threshold of ₹{meta['threshold']:,.2f} "
            f"by ₹{g:,.2f}."
        )
    if atype == "DUPLICATE":
        return (
            f"Duplicate charge of ₹{meta['amount']:,.2f} at {meta['vendor']} "
            f"on {meta['date']} — seen {meta['duplicate_count']} times. "
            f"Extra spend: ₹{g:,.2f}."
        )
    if atype == "CATEGORY_SPIKE":
        return (
            f"{meta['category']} spend in {meta['month']} was ₹{meta['actual']:,.2f} "
            f"({meta['spike_ratio']}× the baseline avg of ₹{meta['baseline_avg']:,.2f}). "
            f"Excess: ₹{g:,.2f}."
        )
    if atype == "VENDOR_DOMINANCE":
        return (
            f"{meta['vendor']} absorbed {meta['pct_of_total']}% of total spend "
            f"(₹{meta['total_spent']:,.2f} of ₹{meta['grand_total']:,.2f}). "
            f"Amount beyond {DOMINANCE_PCT}% threshold: ₹{g:,.2f}."
        )
    if atype == "RECURRING_VENDOR":
        return (
            f"{meta['vendor']} appeared in {meta['month_count']} distinct months "
            f"({', '.join(meta['active_months'])}). "
            f"Total recurring spend: ₹{meta['total_spent']:,.2f}."
        )
    return f"Anomaly of type {atype}. Overspend: ₹{g:,.2f}."
