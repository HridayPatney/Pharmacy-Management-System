"""SQLAlchemy ORM models for PharmaAssist."""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.db.database import Base


class Medicine(Base):
    """A single inventory item tracked in SQLite/Postgres (vectors in pgvector)."""

    __tablename__ = "medicines"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    dosage = Column(String, nullable=False)
    quantity = Column(Integer, default=0)
    price = Column(Float, nullable=False)
    expiry_date = Column(Date, nullable=False)


class MedicineEmbedding(Base):
    """pgvector row for similar-medicine search (Postgres only; skipped on SQLite)."""

    __tablename__ = "medicine_embeddings"

    medicine_id = Column(
        String,
        ForeignKey("medicines.id", ondelete="CASCADE"),
        primary_key=True,
    )
    name = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    # 384 = all-MiniLM-L6-v2 / Chroma DefaultEmbeddingFunction
    embedding = Column(Vector(384), nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


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
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sales = relationship(
        "Sale",
        back_populates="cashier",
        foreign_keys="Sale.user_id",
    )


class RefreshToken(Base):
    """Hashed refresh token. The raw value is sent only as an httpOnly cookie."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by_id = Column(Integer, ForeignKey("refresh_tokens.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="refresh_tokens")


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
