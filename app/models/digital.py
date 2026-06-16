from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class DigitalTask(Base):
    __tablename__ = "digital_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_no = Column(String(50), unique=True, nullable=False, index=True)
    archive_id = Column(Integer, ForeignKey("archives.id"))
    batch_no = Column(String(50))
    assigned_user_id = Column(Integer, ForeignKey("users.id"))
    task_type = Column(String(20), default="scan")
    priority = Column(Integer, default=2)
    progress = Column(Integer, default=0)
    total_pages = Column(Integer, default=0)
    completed_pages = Column(Integer, default=0)
    image_clarity_score = Column(Float, default=0.0)
    metadata_complete_score = Column(Float, default=0.0)
    quality_check_pass = Column(Boolean, default=None)
    quality_check_remark = Column(String(500))
    consecutive_fail_count = Column(Integer, default=0)
    status = Column(String(20), default="pending")
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    deadline = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    archive = relationship("Archive", back_populates="digital_tasks")
    assigned_user = relationship("User", back_populates="digital_tasks")
    quality_checks = relationship("QualityCheck", back_populates="task")


class QualityCheck(Base):
    __tablename__ = "quality_checks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("digital_tasks.id"))
    archive_id = Column(Integer, ForeignKey("archives.id"))
    checked_by = Column(Integer, ForeignKey("users.id"))
    image_clarity_score = Column(Float, default=0.0)
    metadata_complete_score = Column(Float, default=0.0)
    is_passed = Column(Boolean, default=False)
    rejection_reason = Column(Text)
    checked_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("DigitalTask", back_populates="quality_checks")


class TrainingWorkOrder(Base):
    __tablename__ = "training_work_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    batch_no = Column(String(50))
    fail_count = Column(Integer, default=0)
    reason = Column(Text)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
