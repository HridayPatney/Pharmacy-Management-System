"""Sales history, summary, and void/return HTTP routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.core.deps import require_roles
from backend.core.roles import STAFF_ROLES
from backend.db import models
from backend.db.database import get_db
from backend.schemas.sales import PaginatedSales, SaleOut, SaleSummary
from backend.services.audit import write_audit

router = APIRouter()

STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"


def _completed_filter():
    return models.Sale.status == STATUS_COMPLETED


@router.get("/summary", response_model=SaleSummary)
def sales_summary(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Return lifetime and calendar-day sales aggregates (completed sales only)."""
    sale_count = (
        db.query(func.count(models.Sale.id)).filter(_completed_filter()).scalar() or 0
    )
    total_revenue = (
        db.query(func.coalesce(func.sum(models.Sale.total), 0.0))
        .filter(_completed_filter())
        .scalar()
        or 0.0
    )

    day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sale_count = (
        db.query(func.count(models.Sale.id))
        .filter(_completed_filter(), models.Sale.created_at >= day_start)
        .scalar()
        or 0
    )
    today_revenue = (
        db.query(func.coalesce(func.sum(models.Sale.total), 0.0))
        .filter(_completed_filter(), models.Sale.created_at >= day_start)
        .scalar()
        or 0.0
    )

    return SaleSummary(
        sale_count=int(sale_count),
        total_revenue=float(total_revenue),
        today_sale_count=int(today_sale_count),
        today_revenue=float(today_revenue),
    )


@router.get("/", response_model=PaginatedSales)
def list_sales(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(
        None, description="Filter: completed | cancelled | omit for all"
    ),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """List sales newest-first with line items."""
    query = db.query(models.Sale)
    if status:
        normalized = status.strip().lower()
        if normalized not in (STATUS_COMPLETED, STATUS_CANCELLED):
            raise HTTPException(
                status_code=400,
                detail="status must be 'completed' or 'cancelled'",
            )
        query = query.filter(models.Sale.status == normalized)

    total = query.count()
    rows = (
        query.options(joinedload(models.Sale.items))
        .order_by(models.Sale.created_at.desc(), models.Sale.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return PaginatedSales(items=rows, page=page, limit=limit, total=int(total))


@router.get("/{sale_id}", response_model=SaleOut)
def get_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Return one sale with line items."""
    sale = (
        db.query(models.Sale)
        .options(joinedload(models.Sale.items))
        .filter(models.Sale.id == sale_id)
        .first()
    )
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale


@router.post("/{sale_id}/void", response_model=SaleOut)
def void_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Cancel a completed sale and restore stock for each line item."""
    sale = (
        db.query(models.Sale)
        .options(joinedload(models.Sale.items))
        .filter(models.Sale.id == sale_id)
        .first()
    )
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    if sale.status == STATUS_CANCELLED:
        raise HTTPException(status_code=409, detail="Sale is already cancelled")

    restored: list[dict] = []
    missing: list[str] = []

    try:
        for item in sale.items:
            medicine = None
            if item.medicine_id:
                medicine = (
                    db.query(models.Medicine)
                    .filter(models.Medicine.id == item.medicine_id)
                    .first()
                )
            if medicine is None:
                medicine = (
                    db.query(models.Medicine)
                    .filter(models.Medicine.name == item.medicine_name)
                    .first()
                )
            if medicine is None:
                missing.append(item.medicine_name)
                continue
            medicine.quantity += item.quantity
            restored.append(
                {
                    "medicine_id": medicine.id,
                    "name": medicine.name,
                    "quantity": item.quantity,
                }
            )

        sale.status = STATUS_CANCELLED
        sale.cancelled_at = datetime.utcnow()
        sale.cancelled_by_user_id = user.id

        write_audit(
            db,
            user=user,
            action="sale.void",
            entity_type="sale",
            entity_id=str(sale.id),
            details={"restored": restored, "missing": missing, "total": sale.total},
        )
        db.commit()
        db.refresh(sale)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return sale
