from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Date
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    notification_type = Column(String(30), nullable=False)
    related_id = Column(Integer)
    related_type = Column(String(50))
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")


class AppraisalRecord(Base):
    __tablename__ = "appraisal_records"

    id = Column(Integer, primary_key=True, index=True)
    record_no = Column(String(50), unique=True, nullable=False, index=True)
    archive_id = Column(Integer, ForeignKey("archives.id"))
    appraisal_type = Column(String(20), default="periodic")
    reason = Column(Text)
    proposed_action = Column(String(20))
    expert_signatures = Column(String(500))
    final_decision = Column(String(20))
    decision_date = Column(Date)
    status = Column(String(20), default="pending")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    archive = relationship("Archive", back_populates="appraisal_records")
    destruction = relationship("DestructionRecord", back_populates="appraisal", uselist=False)


class DestructionRecord(Base):
    __tablename__ = "destruction_records"

    id = Column(Integer, primary_key=True, index=True)
    record_no = Column(String(50), unique=True, nullable=False, index=True)
    appraisal_id = Column(Integer, ForeignKey("appraisal_records.id"))
    archive_id = Column(Integer, ForeignKey("archives.id"))
    witness_1_id = Column(Integer, ForeignKey("users.id"))
    witness_2_id = Column(Integer, ForeignKey("users.id"))
    witness_1_signature = Column(Boolean, default=False)
    witness_2_signature = Column(Boolean, default=False)
    destruction_method = Column(String(50))
    destruction_date = Column(DateTime)
    evidence_file = Column(String(500))
    remarks = Column(Text)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    appraisal = relationship("AppraisalRecord", back_populates="destruction")
