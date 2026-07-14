"""Persisted sales history and summary HTTP routes."""

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

router = APIRouter()


@router.get("/summary", response_model=SaleSummary)
def sales_summary(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Return lifetime and calendar-day sales aggregates."""
    sale_count = db.query(func.count(models.Sale.id)).scalar() or 0
    total_revenue = db.query(func.coalesce(func.sum(models.Sale.total), 0.0)).scalar() or 0.0

    day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sale_count = (
        db.query(func.count(models.Sale.id))
        .filter(models.Sale.created_at >= day_start)
        .scalar()
        or 0
    )
    today_revenue = (
        db.query(func.coalesce(func.sum(models.Sale.total), 0.0))
        .filter(models.Sale.created_at >= day_start)
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
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """List sales newest-first with line items."""
    total = db.query(func.count(models.Sale.id)).scalar() or 0
    rows = (
        db.query(models.Sale)
        .options(joinedload(models.Sale.items))
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
