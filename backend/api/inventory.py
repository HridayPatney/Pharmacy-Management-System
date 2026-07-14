"""Inventory CRUD, low-stock, sell/invoice, and paginated list HTTP routes."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, or_
from sqlalchemy.orm import Session

from backend.core.deps import require_roles
from backend.core.roles import INVENTORY_WRITE_ROLES, STAFF_ROLES
from backend.db import models
from backend.db.database import get_db
from backend.schemas.inventory import (
    MedicineSchema,
    PaginatedMedicines,
    SellRequest,
    SellResponse,
)
from backend.services.audit import write_audit
from backend.services.drug_api import fetch_drug_summary
from backend.services.vector_sync import remove_medicine_embedding, sync_medicine_embedding

router = APIRouter()

_SORT_COLUMNS = {
    "name": models.Medicine.name,
    "quantity": models.Medicine.quantity,
    "price": models.Medicine.price,
    "expiry_date": models.Medicine.expiry_date,
    "id": models.Medicine.id,
}


@router.post("/add", response_model=MedicineSchema)
def add_medicine(
    med: MedicineSchema,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles(*INVENTORY_WRITE_ROLES)),
):
    """Create a medicine in the DB and embed its drug summary in Chroma."""
    if db.query(models.Medicine).filter(models.Medicine.id == med.id).first():
        raise HTTPException(status_code=400, detail="Medicine with this ID already exists")
    new_med = models.Medicine(**med.model_dump())
    db.add(new_med)
    db.commit()
    db.refresh(new_med)

    summary = fetch_drug_summary(new_med.name) or ""
    sync_medicine_embedding(new_med.id, new_med.name, summary)

    return new_med


@router.get("/", response_model=PaginatedMedicines)
def list_medicines(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="Case-insensitive name/id search"),
    low_stock: int | None = Query(
        None, ge=0, description="If set, only medicines with quantity <= this value"
    ),
    expiry: str | None = Query(
        None,
        description="Filter by expiry: expired | soon | omit for none",
    ),
    days: int = Query(
        30,
        ge=1,
        le=365,
        description="Window (days) used when expiry=soon",
    ),
    sort: str = Query("name", description="One of: name, quantity, price, expiry_date, id"),
    order: str = Query("asc", description="asc or desc"),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Paginated inventory with optional search, low-stock, expiry, and sorting."""
    if order.lower() not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="order must be 'asc' or 'desc'")

    query = db.query(models.Medicine)

    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(models.Medicine.name.ilike(term), models.Medicine.id.ilike(term))
        )

    if low_stock is not None:
        query = query.filter(models.Medicine.quantity <= low_stock)

    if expiry:
        normalized = expiry.strip().lower()
        today = date.today()
        if normalized == "expired":
            query = query.filter(models.Medicine.expiry_date < today)
        elif normalized == "soon":
            query = query.filter(
                models.Medicine.expiry_date >= today,
                models.Medicine.expiry_date <= today + timedelta(days=days),
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="expiry must be 'expired' or 'soon'",
            )

    sort_key = sort.lower()
    column = _SORT_COLUMNS.get(sort_key, models.Medicine.name)
    query = query.order_by(desc(column) if order.lower() == "desc" else asc(column))

    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return PaginatedMedicines(items=items, page=page, limit=limit, total=total)


@router.get("/all", response_model=list[MedicineSchema])
def get_all_medicines(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Return every medicine (compat). Prefer ``GET /inventory/`` with pagination."""
    return db.query(models.Medicine).all()


@router.delete("/delete/{med_id}")
def delete_medicine(
    med_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles(*INVENTORY_WRITE_ROLES)),
):
    """Delete a medicine from the DB and remove its Chroma embedding."""
    med = db.query(models.Medicine).filter(models.Medicine.id == med_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medicine not found")

    name = med.name
    db.delete(med)
    write_audit(
        db,
        user=user,
        action="medicine.delete",
        entity_type="medicine",
        entity_id=med_id,
        details={"name": name},
    )
    db.commit()

    remove_medicine_embedding(med_id)

    return {"detail": f"Medicine {med_id} deleted from database and vector index"}


@router.put("/update/{med_id}", response_model=MedicineSchema)
def update_medicine(
    med_id: str,
    med_update: MedicineSchema,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles(*INVENTORY_WRITE_ROLES)),
):
    """Replace medicine fields and refresh the Chroma embedding."""
    med = db.query(models.Medicine).filter(models.Medicine.id == med_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medicine not found")

    for key, value in med_update.model_dump().items():
        setattr(med, key, value)
    db.commit()
    db.refresh(med)

    summary = fetch_drug_summary(med_update.name) or ""
    sync_medicine_embedding(med_id, med_update.name, summary)

    return med


@router.get("/low-stock", response_model=list[MedicineSchema])
def get_low_stock(
    threshold: int = 10,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Return medicines whose quantity is at or below ``threshold`` (default 10)."""
    return db.query(models.Medicine).filter(models.Medicine.quantity <= threshold).all()


@router.post("/sell", response_model=SellResponse)
def sell_medicines(
    payload: SellRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Decrement stock for all lines in one transaction and return an invoice."""
    if not payload.medicines:
        raise HTTPException(status_code=400, detail="Sell request must include at least one medicine.")

    sold_items = []
    total_price = 0.0
    planned: list[tuple[models.Medicine, int, str]] = []

    try:
        for item in payload.medicines:
            name = item.name.strip()
            qty = item.quantity

            medicine = (
                db.query(models.Medicine)
                .filter(models.Medicine.name == name)
                .first()
            )

            if not medicine:
                raise HTTPException(status_code=404, detail=f"Medicine {name} not found.")
            if medicine.quantity < qty:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for {name}.",
                )

            planned.append((medicine, qty, name))

        for medicine, qty, name in planned:
            medicine.quantity -= qty
            sold_items.append({
                "name": name,
                "quantity": qty,
                "unit_price": medicine.price,
                "subtotal": medicine.price * qty,
            })
            total_price += medicine.price * qty

        sale = models.Sale(
            user_id=user.id,
            patient_name=(payload.patient or "").strip() or None,
            doctor_name=(payload.doctor or "").strip() or None,
            clinic_name=(payload.clinic or "").strip() or None,
            total=total_price,
            status="completed",
        )
        db.add(sale)
        db.flush()

        for medicine, qty, name in planned:
            db.add(
                models.SaleItem(
                    sale_id=sale.id,
                    medicine_id=medicine.id,
                    medicine_name=name,
                    quantity=qty,
                    unit_price=medicine.price,
                    subtotal=medicine.price * qty,
                )
            )

        write_audit(
            db,
            user=user,
            action="inventory.sell",
            entity_type="sale",
            entity_id=str(sale.id),
            details={"items": sold_items, "total": total_price},
        )
        db.commit()
        db.refresh(sale)
        sale_id = sale.id
        created_at = sale.created_at
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    stamp = created_at.strftime("%Y-%m-%d %H:%M") if created_at else datetime.now().strftime("%Y-%m-%d %H:%M")
    return {
        "invoice": {
            "items": sold_items,
            "total": total_price,
            "timestamp": stamp,
            "sale_id": sale_id,
        }
    }
