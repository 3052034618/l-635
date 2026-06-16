from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class BorrowRecord(Base):
    __tablename__ = "borrow_records"

    id = Column(Integer, primary_key=True, index=True)
    record_no = Column(String(50), unique=True, nullable=False, index=True)
    archive_id = Column(Integer, ForeignKey("archives.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    borrow_type = Column(String(20), default="physical")
    purpose = Column(String(500))
    borrow_date = Column(DateTime, default=datetime.utcnow)
    scheduled_outbound_time = Column(DateTime, nullable=False)
    scheduled_return_date = Column(Date, nullable=False)
    actual_return_date = Column(Date)
    status = Column(String(20), default="pending")
    approval_status = Column(String(20), default="pending")
    approved_by = Column(Integer, ForeignKey("users.id"))
    approval_time = Column(DateTime)
    rejection_reason = Column(String(500))
    renewed_count = Column(Integer, default=0)
    overdue_days = Column(Integer, default=0)
    fine_amount = Column(Float, default=0.0)
    fine_paid = Column(Boolean, default=False)
    reminder_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    archive = relationship("Archive", back_populates="borrow_records")
    user = relationship("User", back_populates="borrow_records", foreign_keys=[user_id])
    outbound_task = relationship("OutboundTask", back_populates="borrow_record", uselist=False)
    fines = relationship("Fine", back_populates="borrow_record")


class OutboundTask(Base):
    __tablename__ = "outbound_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_no = Column(String(50), unique=True, nullable=False, index=True)
    borrow_record_id = Column(Integer, ForeignKey("borrow_records.id"))
    archive_id = Column(Integer, ForeignKey("archives.id"))
    admin_user_id = Column(Integer, ForeignKey("users.id"))
    scheduled_time = Column(DateTime, nullable=False)
    completed_time = Column(DateTime)
    status = Column(String(20), default="pending")
    remarks = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    borrow_record = relationship("BorrowRecord", back_populates="outbound_task")
    admin_user = relationship("User", back_populates="outbound_tasks")


class Fine(Base):
    __tablename__ = "fines"

    id = Column(Integer, primary_key=True, index=True)
    borrow_record_id = Column(Integer, ForeignKey("borrow_records.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    overdue_days = Column(Integer, default=0)
    tier = Column(Integer, default=1)
    daily_rate = Column(Float, default=5.0)
    total_amount = Column(Float, default=0.0)
    paid_amount = Column(Float, default=0.0)
    status = Column(String(20), default="unpaid")
    payment_time = Column(DateTime)
    remarks = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    borrow_record = relationship("BorrowRecord", back_populates="fines")
