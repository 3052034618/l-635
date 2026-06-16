from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Date, Float
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Archive(Base):
    __tablename__ = "archives"

    id = Column(Integer, primary_key=True, index=True)
    archive_index = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    category_id = Column(Integer, ForeignKey("archive_categories.id"))
    fonds_code = Column(String(50))
    carrier_type = Column(String(50), nullable=False)
    security_level = Column(Integer, default=1)
    total_pages = Column(Integer, default=0)
    scanned_pages = Column(Integer, default=0)
    missing_pages = Column(String(500))
    is_digitized = Column(Boolean, default=False)
    digitization_quality = Column(Float, default=0.0)
    metadata_complete = Column(Boolean, default=False)
    creation_date = Column(Date)
    storage_start_date = Column(Date, default=datetime.utcnow)
    last_access_date = Column(Date)
    cabinet_id = Column(Integer, ForeignKey("storage_cabinets.id"))
    cabinet_slot = Column(String(50))
    description = Column(Text)
    keywords = Column(String(500))
    retention_period = Column(Integer, default=30)
    status = Column(String(20), default="in_storage")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("ArchiveCategory", back_populates="archives")
    cabinet = relationship("StorageCabinet", back_populates="archives")
    borrow_records = relationship("BorrowRecord", back_populates="archive")
    digital_tasks = relationship("DigitalTask", back_populates="archive")
    appraisal_records = relationship("AppraisalRecord", back_populates="archive")
    digital_assets = relationship("DigitalAsset", back_populates="archive")


class DigitalAsset(Base):
    __tablename__ = "digital_assets"

    id = Column(Integer, primary_key=True, index=True)
    archive_id = Column(Integer, ForeignKey("archives.id"))
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(200), nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer)
    page_number = Column(Integer)
    resolution = Column(String(50))
    image_clarity = Column(Float, default=0.0)
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    archive = relationship("Archive", back_populates="digital_assets")
