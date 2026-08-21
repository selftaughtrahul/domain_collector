import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.connection import Base

class Domain(Base):
    __tablename__ = "domains"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scan_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    domain_type: Mapped[str] = mapped_column(String(50), default="primary")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    
    company = relationship("Company", back_populates="domains")
    
    website = relationship("Website", back_populates="domain", cascade="all, delete-orphan", uselist=False)
    company_profile = relationship("CompanyProfile", back_populates="domain", cascade="all, delete-orphan", uselist=False)
    contacts = relationship("Contact", back_populates="domain", cascade="all, delete-orphan")
    social_profiles = relationship("SocialProfile", back_populates="domain", cascade="all, delete-orphan")
    technologies = relationship("Technology", back_populates="domain", cascade="all, delete-orphan")
    seo = relationship("SEOData", back_populates="domain", cascade="all, delete-orphan", uselist=False)
    dns_records = relationship("DNSRecord", back_populates="domain", cascade="all, delete-orphan")
    security = relationship("SecurityData", back_populates="domain", cascade="all, delete-orphan", uselist=False)
    scans = relationship("Scan", back_populates="domain", cascade="all, delete-orphan", order_by="Scan.started_at")
