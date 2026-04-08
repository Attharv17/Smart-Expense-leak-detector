"""
routes/alerts.py
----------------
Endpoints for managing system-generated expense leak alerts:

  GET    /alerts             — Get all alerts (with optional filters & pagination)
  GET    /alerts/{id}        — Get a specific alert by ID
  PATCH  /alerts/{id}/resolve — Mark an alert as resolved
  DELETE /alerts/{id}        — Delete an alert
  GET    /alerts/stats        — Aggregate alert statistics
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Alert
from schemas import AlertRead, AlertsResponse, MessageResponse

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# ---------------------------------------------------------------------------
# GET /alerts  — List all alerts with optional filters
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=AlertsResponse,
    summary="Get all expense leak alerts",
)
def get_alerts(
    skip:       int            = Query(0,    ge=0,  description="Pagination offset"),
    limit:      int            = Query(50,   ge=1, le=200, description="Max results"),
    severity:   Optional[str] = Query(None,  description="Filter by severity: LOW|MEDIUM|HIGH|CRITICAL"),
    alert_type: Optional[str] = Query(None,  description="Filter by alert type (e.g. HIGH_SPEND)"),
    resolved:   Optional[bool]= Query(None,  description="True = only resolved, False = only open"),
    db: Session = Depends(get_db),
):
    """
    Return a paginated list of alerts with optional filters.
    Alerts are ordered by creation time (newest first).
    """
    query = db.query(Alert)

    if severity:
        query = query.filter(Alert.severity == severity.upper())
    if alert_type:
        query = query.filter(Alert.alert_type.ilike(f"%{alert_type}%"))
    if resolved is not None:
        query = query.filter(Alert.resolved == ("true" if resolved else "false"))

    total = query.count()
    alerts = query.order_by(Alert.id.desc()).offset(skip).limit(limit).all()

    return AlertsResponse(total=total, alerts=alerts)


# ---------------------------------------------------------------------------
# GET /alerts/stats  — Aggregate alert statistics
# ---------------------------------------------------------------------------

@router.get(
    "/stats",
    summary="Get alert statistics summary",
)
def get_alert_stats(db: Session = Depends(get_db)):
    """
    Returns aggregate counts of alerts grouped by severity and type.
    Useful for building a dashboard overview.
    """
    # Total by severity
    severity_counts = (
        db.query(Alert.severity, func.count(Alert.id).label("count"))
        .group_by(Alert.severity)
        .all()
    )

    # Total by type
    type_counts = (
        db.query(Alert.alert_type, func.count(Alert.id).label("count"))
        .group_by(Alert.alert_type)
        .all()
    )

    # Counts by resolved status
    total          = db.query(Alert).count()
    total_open     = db.query(Alert).filter(Alert.resolved == "false").count()
    total_resolved = db.query(Alert).filter(Alert.resolved == "true").count()

    return {
        "total_alerts":    total,
        "open_alerts":     total_open,
        "resolved_alerts": total_resolved,
        "by_severity":     {r.severity:   r.count for r in severity_counts},
        "by_type":         {r.alert_type: r.count for r in type_counts},
    }


# ---------------------------------------------------------------------------
# GET /alerts/{id}  — Get a single alert
# ---------------------------------------------------------------------------

@router.get(
    "/{alert_id}",
    response_model=AlertRead,
    summary="Get a specific alert by ID",
)
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    """Retrieve a single alert record by its primary key."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id={alert_id} not found.",
        )
    return alert


# ---------------------------------------------------------------------------
# PATCH /alerts/{id}/resolve  — Mark an alert as resolved
# ---------------------------------------------------------------------------

@router.patch(
    "/{alert_id}/resolve",
    response_model=AlertRead,
    summary="Mark an alert as resolved",
)
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    """
    Toggle the resolved status of an alert to 'true'.
    Idempotent — calling it multiple times has no additional effect.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id={alert_id} not found.",
        )

    alert.resolved = "true"
    db.commit()
    db.refresh(alert)
    return alert


# ---------------------------------------------------------------------------
# DELETE /alerts/{id}  — Delete an alert
# ---------------------------------------------------------------------------

@router.delete(
    "/{alert_id}",
    response_model=MessageResponse,
    summary="Delete an alert by ID",
)
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    """Permanently remove an alert record."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id={alert_id} not found.",
        )
    db.delete(alert)
    db.commit()
    return MessageResponse(message=f"Alert #{alert_id} deleted successfully.")
