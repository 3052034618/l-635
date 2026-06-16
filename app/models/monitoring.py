from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    sensor_type = Column(String(20), nullable=False)
    zone_id = Column(Integer, ForeignKey("storage_zones.id"))
    location = Column(String(200))
    is_online = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    zone = relationship("StorageZone", back_populates="sensors")
    readings = relationship("SensorReading", back_populates="sensor")


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(Integer, ForeignKey("sensors.id"), nullable=False)
    temperature = Column(Float)
    humidity = Column(Float)
    reading_time = Column(DateTime, default=datetime.utcnow, index=True)
    is_warning = Column(Boolean, default=False)

    sensor = relationship("Sensor", back_populates="readings")


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(50), unique=True, nullable=False, index=True)
    order_type = Column(String(30), nullable=False)
    zone_id = Column(Integer, ForeignKey("storage_zones.id"))
    sensor_id = Column(Integer, ForeignKey("sensors.id"))
    assigned_user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(200), nullable=False)
    description = Column(Text)
    priority = Column(Integer, default=2)
    status = Column(String(20), default="pending")
    temperature = Column(Float)
    humidity = Column(Float)
    ac_status = Column(String(20), default="off")
    dehumidifier_status = Column(String(20), default="off")
    completed_at = Column(DateTime)
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_user = relationship("User", back_populates="work_orders")
