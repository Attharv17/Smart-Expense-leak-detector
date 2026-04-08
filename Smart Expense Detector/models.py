"""
models.py
---------
SQLAlchemy ORM models for the Smart Expense Leak Detector.

Tables:
  - expenses: Stores all uploaded expense records
  - alerts:   Stores system-generated anomaly / leak alerts
"""

from sqlalchemy import Column, Integer, Float, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Expense(Base):
    """
    Represents a single expense transaction.

    Fields:
        id          - Auto-incremented primary key
        date        - Date string of the transaction (e.g. "2024-01-15")
        amount      - Monetary value of the expense
        category    - High-level bucket (e.g. "Food", "Travel", "SaaS")
        vendor      - Name of the vendor / merchant
        description - Free-text description of the expense
        created_at  - Server-side timestamp when record was inserted
    """
    __tablename__ = "expenses"

    id          = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date        = Column(String(20),  nullable=False)
    amount      = Column(Float,       nullable=False)
    category    = Column(String(100), nullable=False, index=True)
    vendor      = Column(String(200), nullable=False)
    description = Column(Text,        nullable=True, default="")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    """
    Represents a system-generated expense leak / anomaly alert.

    Fields:
        id          - Auto-incremented primary key
        alert_type  - Category of alert (e.g. "HIGH_SPEND", "DUPLICATE", "UNUSUAL_VENDOR")
        severity    - One of: LOW | MEDIUM | HIGH | CRITICAL
        message     - Human-readable description of the alert
        expense_id  - Optional FK to the triggering expense (nullable)
        resolved    - Whether the alert has been acknowledged / resolved
        created_at  - Server-side timestamp when alert was generated
    """
    __tablename__ = "alerts"

    id          = Column(Integer, primary_key=True, index=True, autoincrement=True)
    alert_type  = Column(String(50),  nullable=False, index=True)
    severity    = Column(String(20),  nullable=False, default="MEDIUM")
    message     = Column(Text,        nullable=False)
    expense_id  = Column(Integer,     ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True)
    resolved    = Column(String(5),   nullable=False, default="false")  # "true" | "false"
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship back to the triggering expense (optional)
    expense = relationship("Expense", backref="alerts", foreign_keys=[expense_id])
