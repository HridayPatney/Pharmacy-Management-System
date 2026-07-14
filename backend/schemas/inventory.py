"""Inventory and sell/invoice request and response schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class MedicineSchema(BaseModel):
    """Medicine inventory record (matches the Streamlit / OpenAPI contract)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    dosage: str
    quantity: int
    price: float
    expiry_date: date


class SellItem(BaseModel):
    """One line item in a sell request (matched by medicine name)."""

    name: str
    quantity: int = Field(gt=0)


class SellRequest(BaseModel):
    """Body for ``POST /inventory/sell``."""

    medicines: list[SellItem]
    patient: str | None = None
    doctor: str | None = None
    clinic: str | None = None


class InvoiceItem(BaseModel):
    """One line on the generated invoice."""

    name: str
    quantity: int
    unit_price: float
    subtotal: float


class Invoice(BaseModel):
    """Sell response invoice payload expected by the UI PDF generator."""

    items: list[InvoiceItem]
    total: float
    timestamp: str
    sale_id: int | None = None


class SellResponse(BaseModel):
    """Wrapper returned by ``POST /inventory/sell``."""

    invoice: Invoice


class PaginatedMedicines(BaseModel):
    """Paginated inventory list response."""

    items: list[MedicineSchema]
    page: int
    limit: int
    total: int
