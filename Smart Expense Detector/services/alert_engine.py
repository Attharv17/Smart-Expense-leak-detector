"""
services/alert_engine.py
------------------------
Core business logic for detecting expense anomalies and generating alerts.

Rules implemented:
  1. HIGH_SPEND       — Any single expense over a configurable threshold
  2. DUPLICATE        — Same vendor + same amount on the same date (exact duplicate)
  3. UNUSUAL_CATEGORY — Spending category not seen in past history
  4. CATEGORY_SPIKE   — A category's spend is 2× above its running average
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Expense, Alert
from typing import List

# ---- Configurable thresholds -----------------------------------------------

HIGH_SPEND_THRESHOLD = 1000.0   # Flag any single expense above ₹1000
SPIKE_MULTIPLIER     = 2.0      # Flag if new expense is 2× the category average
KNOWN_CATEGORIES     = {        # Baseline known categories (seed set)
    "food", "travel", "accommodation", "saas", "utilities",
    "healthcare", "entertainment", "office supplies", "marketing",
    "payroll", "subscription", "subscriptions", "hardware", "consulting",
    # Indian / sample CSV categories
    "transport", "shopping", "rent", "gifts", "parking",
    "restaurant", "groceries", "education", "insurance",
}


def run_alert_engine(db: Session, expense: Expense) -> List[Alert]:
    """
    Evaluate a newly inserted expense against all alert rules.
    Returns a list of Alert ORM objects (already added to session, NOT committed).
    """
    generated_alerts: List[Alert] = []

    # ---- Rule 1: High-spend single transaction -----------------------------
    if expense.amount >= HIGH_SPEND_THRESHOLD:
        alert = Alert(
            alert_type = "HIGH_SPEND",
            severity   = "HIGH" if expense.amount >= HIGH_SPEND_THRESHOLD * 2 else "MEDIUM",
            message    = (
                f"Large expense detected: ₹{expense.amount:.2f} at '{expense.vendor}' "
                f"on {expense.date}. Threshold is ₹{HIGH_SPEND_THRESHOLD:.2f}."
            ),
            expense_id = expense.id,
            resolved   = "false",
        )
        db.add(alert)
        generated_alerts.append(alert)

    # ---- Rule 2: Exact duplicate (same vendor + amount + date) -------------
    duplicate = (
        db.query(Expense)
        .filter(
            Expense.vendor == expense.vendor,
            Expense.amount == expense.amount,
            Expense.date   == expense.date,
            Expense.id     != expense.id,   # exclude self
        )
        .first()
    )
    if duplicate:
        alert = Alert(
            alert_type = "DUPLICATE",
            severity   = "HIGH",
            message    = (
                f"Potential duplicate expense: ₹{expense.amount:.2f} at '{expense.vendor}' "
                f"on {expense.date} matches expense ID #{duplicate.id}."
            ),
            expense_id = expense.id,
            resolved   = "false",
        )
        db.add(alert)
        generated_alerts.append(alert)

    # ---- Rule 3: Unusual / unknown category --------------------------------
    category_lower = expense.category.strip().lower()
    if category_lower not in KNOWN_CATEGORIES:
        # Also check if this category has appeared before in the DB
        existing_category = (
            db.query(Expense)
            .filter(func.lower(Expense.category) == category_lower)
            .filter(Expense.id != expense.id)
            .first()
        )
        if not existing_category:
            alert = Alert(
                alert_type = "UNUSUAL_CATEGORY",
                severity   = "LOW",
                message    = (
                    f"New/unusual expense category detected: '{expense.category}'. "
                    f"This category has not been seen before."
                ),
                expense_id = expense.id,
                resolved   = "false",
            )
            db.add(alert)
            generated_alerts.append(alert)

    # ---- Rule 4: Category spend spike (2× running average) -----------------
    category_stats = (
        db.query(func.avg(Expense.amount), func.count(Expense.id))
        .filter(func.lower(Expense.category) == category_lower)
        .filter(Expense.id != expense.id)
        .first()
    )
    if category_stats and category_stats[1] >= 3:  # need at least 3 data points
        avg_spend, _ = category_stats
        if avg_spend and expense.amount >= avg_spend * SPIKE_MULTIPLIER:
            alert = Alert(
                alert_type = "CATEGORY_SPIKE",
                severity   = "MEDIUM",
                message    = (
                    f"Spending spike in '{expense.category}': ₹{expense.amount:.2f} is "
                    f"{expense.amount / avg_spend:.1f}× the category average "
                    f"(₹{avg_spend:.2f})."
                ),
                expense_id = expense.id,
                resolved   = "false",
            )
            db.add(alert)
            generated_alerts.append(alert)

    return generated_alerts
