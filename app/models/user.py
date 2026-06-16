from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100))
    phone = Column(String(20))
    department = Column(String(100))
    role = Column(String(20), nullable=False, default="user")
    permission_level = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    borrow_records = relationship("BorrowRecord", back_populates="user", foreign_keys="BorrowRecord.user_id")
    approved_borrow_records = relationship("BorrowRecord", foreign_keys="BorrowRecord.approved_by")
    notifications = relationship("Notification", back_populates="user")
    digital_tasks = relationship("DigitalTask", back_populates="assigned_user")
    outbound_tasks = relationship("OutboundTask", back_populates="admin_user")
    work_orders = relationship("WorkOrder", back_populates="assigned_user")
