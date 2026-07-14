"""SQLAlchemy ORM models for PharmaAssist."""

from sqlalchemy import Column, Date, Float, Integer, String

from backend.db.database import Base


class Medicine(Base):
    """A single inventory item tracked in SQLite and mirrored in Chroma."""

    __tablename__ = "medicines"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    dosage = Column(String, nullable=False)
    quantity = Column(Integer, default=0)
    price = Column(Float, nullable=False)
    expiry_date = Column(Date, nullable=False)
