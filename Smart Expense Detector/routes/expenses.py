"""
routes/expenses.py
------------------
All expense-related REST endpoints:

  POST   /expenses/upload        — Upload a single expense (JSON)
  POST   /expenses/upload/bulk   — Upload multiple expenses (JSON list)
  POST   /expenses/upload/csv    — Upload expenses from a CSV file
  GET    /expenses               — List all expenses (with pagination & filters)
  GET    /expenses/{id}          — Get a single expense by ID
  DELETE /expenses/{id}          — Delete a single expense by ID
"""

import csv
import io
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models import Expense
from schemas import (
    ExpenseCreate,
    ExpenseRead,
    BulkUploadRequest,
    BulkUploadResponse,
    MessageResponse,
)
from services.alert_engine import run_alert_engine

router = APIRouter(prefix="/expenses", tags=["Expenses"])


# ---------------------------------------------------------------------------
# Helper: Persist one expense + run alert engine
# ---------------------------------------------------------------------------

def _insert_expense(db: Session, expense_data: ExpenseCreate) -> tuple[Expense, int]:
    """
    Inserts a single expense into the DB and runs the alert engine.
    Returns (expense_orm_object, number_of_alerts_generated).
    """
    db_expense = Expense(**expense_data.model_dump())
    db.add(db_expense)
    db.flush()  # Flush to assign an id before running the alert engine

    # Run the alert engine — it adds Alert records to the session
    alerts = run_alert_engine(db, db_expense)
    return db_expense, len(alerts)


# ---------------------------------------------------------------------------
# POST /expenses/upload  — Single expense upload
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a single expense",
)
def upload_expense(expense: ExpenseCreate, db: Session = Depends(get_db)):
    """
    Accept a single expense JSON payload, persist it to SQLite,
    and run the alert engine against it.
    """
    db_expense, _ = _insert_expense(db, expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense


# ---------------------------------------------------------------------------
# POST /expenses/upload/bulk  — Bulk JSON upload
# ---------------------------------------------------------------------------

@router.post(
    "/upload/bulk",
    response_model=BulkUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload multiple expenses (JSON array)",
)
def upload_expenses_bulk(payload: BulkUploadRequest, db: Session = Depends(get_db)):
    """
    Accept a list of expenses in a single JSON body.
    All expenses are inserted in a single transaction.
    Returns a summary of how many were inserted and how many alerts were generated.
    """
    total_alerts = 0
    for expense_data in payload.expenses:
        _, alert_count = _insert_expense(db, expense_data)
        total_alerts += alert_count

    db.commit()

    return BulkUploadResponse(
        message=f"Successfully uploaded {len(payload.expenses)} expense(s).",
        inserted_count=len(payload.expenses),
        alerts_generated=total_alerts,
    )


# ---------------------------------------------------------------------------
# POST /expenses/upload/csv  — CSV file upload
# ---------------------------------------------------------------------------

@router.post(
    "/upload/csv",
    response_model=BulkUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload expenses from a CSV file",
)
async def upload_expenses_csv(
    file: UploadFile = File(..., description="CSV file with expense data"),
    db: Session = Depends(get_db),
):
    """
    Parse an uploaded CSV file and insert each row as an expense.

    Expected CSV columns (header required):
        date, amount, category, vendor, description
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are accepted by this endpoint.",
        )

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))

    # Validate that required columns are present
    required_columns = {"date", "amount", "category", "vendor"}
    if reader.fieldnames is None or not required_columns.issubset(
        set(f.strip().lower() for f in reader.fieldnames)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CSV must contain columns: {', '.join(required_columns)}",
        )

    inserted = 0
    total_alerts = 0
    errors = []

    for line_num, row in enumerate(reader, start=2):  # start=2 because row 1 is header
        try:
            expense_data = ExpenseCreate(
                date        = row.get("date", "").strip(),
                amount      = float(row.get("amount", 0)),
                category    = row.get("category", "").strip(),
                vendor      = row.get("vendor", "").strip(),
                description = row.get("description", "").strip(),
            )
            _, alert_count = _insert_expense(db, expense_data)
            total_alerts += alert_count
            inserted += 1
        except Exception as e:
            errors.append(f"Row {line_num}: {str(e)}")

    if errors and inserted == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "All rows failed validation.", "errors": errors},
        )

    db.commit()

    msg = f"Imported {inserted} expense(s) from '{file.filename}'."
    if errors:
        msg += f" Skipped {len(errors)} invalid row(s)."

    return BulkUploadResponse(
        message=msg,
        inserted_count=inserted,
        alerts_generated=total_alerts,
    )


# ---------------------------------------------------------------------------
# GET /expenses  — List all expenses (with optional filters & pagination)
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=List[ExpenseRead],
    summary="Get all expenses",
)
def get_expenses(
    skip:     int            = Query(0,     ge=0,   description="Number of records to skip"),
    limit:    int            = Query(100,   ge=1, le=500, description="Max records returned"),
    category: Optional[str] = Query(None,  description="Filter by category (case-insensitive)"),
    vendor:   Optional[str] = Query(None,  description="Filter by vendor name (partial match)"),
    min_amt:  Optional[float]= Query(None,  description="Minimum expense amount"),
    max_amt:  Optional[float]= Query(None,  description="Maximum expense amount"),
    db: Session = Depends(get_db),
):
    """
    Return a paginated list of all expenses.
    Optional query parameters allow filtering by category, vendor, or amount range.
    """
    query = db.query(Expense)

    if category:
        query = query.filter(Expense.category.ilike(f"%{category}%"))
    if vendor:
        query = query.filter(Expense.vendor.ilike(f"%{vendor}%"))
    if min_amt is not None:
        query = query.filter(Expense.amount >= min_amt)
    if max_amt is not None:
        query = query.filter(Expense.amount <= max_amt)

    return query.order_by(Expense.id.desc()).offset(skip).limit(limit).all()


# ---------------------------------------------------------------------------
# GET /expenses/{id}  — Get a single expense
# ---------------------------------------------------------------------------

@router.get(
    "/{expense_id}",
    response_model=ExpenseRead,
    summary="Get a single expense by ID",
)
def get_expense(expense_id: int, db: Session = Depends(get_db)):
    """Retrieve a specific expense record by its primary key."""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense with id={expense_id} not found.",
        )
    return expense


# ---------------------------------------------------------------------------
# DELETE /expenses/{id}  — Delete a single expense
# ---------------------------------------------------------------------------

@router.delete(
    "/{expense_id}",
    response_model=MessageResponse,
    summary="Delete an expense by ID",
)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    """Permanently remove an expense and any linked alerts."""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense with id={expense_id} not found.",
        )
    db.delete(expense)
    db.commit()
    return MessageResponse(message=f"Expense #{expense_id} deleted successfully.")


# ---------------------------------------------------------------------------
# PUT /expenses/{id}  — Update an expense
# ---------------------------------------------------------------------------

@router.put(
    "/{expense_id}",
    response_model=ExpenseRead,
    summary="Update an expense by ID",
)
def update_expense(
    expense_id: int,
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
):
    """Update every field of an existing expense record."""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense with id={expense_id} not found.",
        )
    for field, value in payload.model_dump().items():
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return expense


# ---------------------------------------------------------------------------
# DELETE /expenses  — Clear ALL expenses (hard reset for testing)
# ---------------------------------------------------------------------------

@router.delete(
    "",
    response_model=MessageResponse,
    summary="Delete ALL expenses (hard reset)",
)
def delete_all_expenses(db: Session = Depends(get_db)):
    """
    Permanently remove ALL expense records and their linked alerts.
    Useful for resetting the database between test runs.
    Returns the count of deleted records.
    """
    from models import Alert
    alert_count = db.query(Alert).delete()
    expense_count = db.query(Expense).delete()
    db.commit()
    return MessageResponse(
        message=f"Deleted {expense_count} expense(s) and {alert_count} alert(s). Database cleared.",
        detail=f"expenses_deleted={expense_count}, alerts_deleted={alert_count}",
    )

