"""Inventory CRUD, low-stock, and sell/invoice HTTP routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.deps import require_roles
from backend.core.roles import INVENTORY_WRITE_ROLES, STAFF_ROLES
from backend.db import models
from backend.db.database import get_db
from backend.schemas.inventory import MedicineSchema, SellRequest, SellResponse
from backend.services.audit import write_audit
from backend.services.drug_api import fetch_drug_summary
from backend.services.vector_sync import remove_medicine_embedding, sync_medicine_embedding

router = APIRouter()


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


@router.get("/all", response_model=list[MedicineSchema])
def get_all_medicines(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Return every medicine currently in inventory."""
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
    """Decrement stock for all lines in one transaction and return an invoice.

    Validates every line before mutating. On any failure the whole sell is rolled back
    so earlier lines are not partially committed. Audits the successful sale.
    """
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

        write_audit(
            db,
            user=user,
            action="inventory.sell",
            entity_type="invoice",
            entity_id=None,
            details={"items": sold_items, "total": total_price},
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return {
        "invoice": {
            "items": sold_items,
            "total": total_price,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    }
