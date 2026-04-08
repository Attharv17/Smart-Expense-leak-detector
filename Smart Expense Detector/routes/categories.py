"""
routes/categories.py
--------------------
Endpoints that provide categorized / aggregated views of expenses:

  GET /categories                — List all unique categories with totals
  GET /categories/{name}/expenses — Get all expenses in a specific category
  GET /categories/summary        — Full breakdown: categories + per-category stats
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Expense
from schemas import CategorySummary, CategorizedExpensesResponse, ExpenseRead

router = APIRouter(prefix="/categories", tags=["Categories"])


# ---------------------------------------------------------------------------
# GET /categories  — All categories with spend totals
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=List[CategorySummary],
    summary="Get all expense categories with totals",
)
def get_categories(db: Session = Depends(get_db)):
    """
    Return a list of all categories with:
      - total_amount  : sum of all expenses in that category
      - expense_count : number of expense records
    Sorted by total_amount descending (biggest spenders first).
    """
    results = (
        db.query(
            Expense.category,
            func.sum(Expense.amount).label("total_amount"),
            func.count(Expense.id).label("expense_count"),
        )
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )

    return [
        CategorySummary(
            category=r.category,
            total_amount=round(r.total_amount, 2),
            expense_count=r.expense_count,
        )
        for r in results
    ]


# ---------------------------------------------------------------------------
# GET /categories/summary  — Full categorized breakdown
# ---------------------------------------------------------------------------

@router.get(
    "/summary",
    response_model=CategorizedExpensesResponse,
    summary="Get full categorized expense breakdown",
)
def get_categorized_summary(db: Session = Depends(get_db)):
    """
    Returns both:
      1. A summary list of categories with totals
      2. The full list of all individual expenses (ordered by date desc)

    Useful for dashboards that need both high-level and detailed views.
    """
    # Aggregate summary per category
    cat_results = (
        db.query(
            Expense.category,
            func.sum(Expense.amount).label("total_amount"),
            func.count(Expense.id).label("expense_count"),
        )
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )

    summary = [
        CategorySummary(
            category=r.category,
            total_amount=round(r.total_amount, 2),
            expense_count=r.expense_count,
        )
        for r in cat_results
    ]

    # All expenses sorted by date descending
    expenses = (
        db.query(Expense)
        .order_by(Expense.date.desc(), Expense.id.desc())
        .all()
    )

    return CategorizedExpensesResponse(summary=summary, expenses=expenses)


# ---------------------------------------------------------------------------
# GET /categories/{name}/expenses  — Expenses in a specific category
# ---------------------------------------------------------------------------

@router.get(
    "/{category_name}/expenses",
    response_model=List[ExpenseRead],
    summary="Get expenses for a specific category",
)
def get_expenses_by_category(category_name: str, db: Session = Depends(get_db)):
    """
    Return all expense records belonging to the given category (case-insensitive).
    Raises 404 if no expenses exist in that category.
    """
    expenses = (
        db.query(Expense)
        .filter(Expense.category.ilike(category_name))
        .order_by(Expense.date.desc())
        .all()
    )

    if not expenses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No expenses found for category '{category_name}'.",
        )

    return expenses
