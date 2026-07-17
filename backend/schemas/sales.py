"""Sales history and summary schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SaleItemOut(BaseModel):
    """One line on a persisted sale."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    medicine_id: str | None
    medicine_name: str
    quantity: int
    unit_price: float
    subtotal: float


class SaleOut(BaseModel):
    """Sale header with line items."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    patient_name: str | None
    doctor_name: str | None
    clinic_name: str | None
    total: float
    status: str = "completed"
    cancelled_at: datetime | None = None
    cancelled_by_user_id: int | None = None
    prescription_file_key: str | None = None
    created_at: datetime
    items: list[SaleItemOut] = Field(default_factory=list)


class SaleSummary(BaseModel):
    """Aggregate sales metrics for dashboard / billing (completed only)."""

    sale_count: int
    total_revenue: float
    today_sale_count: int
    today_revenue: float


class PaginatedSales(BaseModel):
    """Paginated sales history."""

    items: list[SaleOut]
    page: int
    limit: int
    total: int
