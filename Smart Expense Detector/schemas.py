"""
schemas.py
----------
Pydantic models used for:
  - Request body validation (incoming data)
  - Response serialization (outgoing data)

Pydantic V2 is fully compatible with FastAPI and enforces strict typing.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


# ---------------------------------------------------------------------------
# Expense Schemas
# ---------------------------------------------------------------------------

class ExpenseBase(BaseModel):
    """Shared fields between create and read expense schemas."""
    date:        str   = Field(..., description="Transaction date, e.g. '2024-01-15'")
    amount:      float = Field(..., gt=0, description="Expense amount (must be positive)")
    category:    str   = Field(..., min_length=1, max_length=100)
    vendor:      str   = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default="", max_length=1000)

    @field_validator("category", "vendor", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Automatically strip leading/trailing whitespace from string fields."""
        return v.strip() if isinstance(v, str) else v


class ExpenseCreate(ExpenseBase):
    """Schema used when creating a single expense via the API."""
    pass


class ExpenseRead(ExpenseBase):
    """
    Schema returned when reading expenses.
    Includes server-generated fields: id and created_at.
    """
    id:         int
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}  # Allows ORM object → Pydantic conversion


# ---------------------------------------------------------------------------
# Bulk Upload Schemas
# ---------------------------------------------------------------------------

class BulkUploadRequest(BaseModel):
    """Schema for uploading multiple expenses in a single JSON payload."""
    expenses: List[ExpenseCreate] = Field(..., min_length=1)


class BulkUploadResponse(BaseModel):
    """Response after a bulk upload operation."""
    message:        str
    inserted_count: int
    alerts_generated: int


# ---------------------------------------------------------------------------
# Categorized Expense Schemas
# ---------------------------------------------------------------------------

class CategorySummary(BaseModel):
    """Aggregated spend per category."""
    category:      str
    total_amount:  float
    expense_count: int


class CategorizedExpensesResponse(BaseModel):
    """Full response for the categorized expenses endpoint."""
    summary:  List[CategorySummary]
    expenses: List[ExpenseRead]


# ---------------------------------------------------------------------------
# Alert Schemas
# ---------------------------------------------------------------------------

class AlertRead(BaseModel):
    """Schema returned when reading alerts."""
    id:         int
    alert_type: str
    severity:   str
    message:    str
    expense_id: Optional[int] = None
    resolved:   str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertsResponse(BaseModel):
    """Paginated alerts response."""
    total:    int
    alerts:   List[AlertRead]


# ---------------------------------------------------------------------------
# Generic Response
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    """Simple acknowledgment response."""
    message: str
    detail:  Optional[str] = None
