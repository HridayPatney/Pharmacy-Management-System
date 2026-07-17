"""SQLAlchemy ORM models for PharmaAssist."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.db.database import Base


class Medicine(Base):
    """A single inventory item tracked in SQLite/Postgres and mirrored in Chroma."""

    __tablename__ = "medicines"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    dosage = Column(String, nullable=False)
    quantity = Column(Integer, default=0)
    price = Column(Float, nullable=False)
    expiry_date = Column(Date, nullable=False)


class User(Base):
    """Authenticated staff account with a role."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    audit_logs = relationship("AuditLog", back_populates="user")
    sales = relationship(
        "Sale",
        back_populates="cashier",
        foreign_keys="Sale.user_id",
    )


class AuditLog(Base):
    """Immutable record of sensitive inventory actions (sell, delete, …)."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(128), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")


class Sale(Base):
    """Persisted pharmacy sale / invoice header."""

    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    patient_name = Column(String(255), nullable=True)
    doctor_name = Column(String(255), nullable=True)
    clinic_name = Column(String(255), nullable=True)
    total = Column(Float, nullable=False)
    status = Column(String(32), nullable=False, default="completed", index=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancelled_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    prescription_file_key = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    cashier = relationship("User", back_populates="sales", foreign_keys=[user_id])
    items = relationship(
        "SaleItem",
        back_populates="sale",
        cascade="all, delete-orphan",
        order_by="SaleItem.id",
    )


class SaleItem(Base):
    """One line item on a persisted sale."""

    __tablename__ = "sale_items"

    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False, index=True)
    medicine_id = Column(String, nullable=True)
    medicine_name = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)

    sale = relationship("Sale", back_populates="items")
