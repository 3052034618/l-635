from sqlalchemy import Column, Integer, String, DateTime, Float, Date
from datetime import datetime

from app.database import Base


class MonthlyReport(Base):
    __tablename__ = "monthly_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_month = Column(String(7), nullable=False, index=True)
    zone_code = Column(String(20), nullable=False)
    new_archives_count = Column(Integer, default=0)
    borrow_count = Column(Integer, default=0)
    digitization_count = Column(Integer, default=0)
    digitization_rate = Column(Float, default=0.0)
    temp_warning_count = Column(Integer, default=0)
    humidity_warning_count = Column(Integer, default=0)
    total_warning_count = Column(Integer, default=0)
    generated_at = Column(DateTime, default=datetime.utcnow)


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    operation_type = Column(String(50))
    target_type = Column(String(50))
    target_id = Column(Integer)
    description = Column(String(500))
    operation_time = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(50))
