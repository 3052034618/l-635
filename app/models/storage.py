from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class StorageCabinet(Base):
    __tablename__ = "storage_cabinets"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=False)
    zone_id = Column(Integer, ForeignKey("storage_zones.id"))
    carrier_type = Column(String(50))
    temperature_min = Column(Float, default=14.0)
    temperature_max = Column(Float, default=24.0)
    humidity_min = Column(Float, default=40.0)
    humidity_max = Column(Float, default=60.0)
    total_slots = Column(Integer, default=100)
    used_slots = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    zone = relationship("StorageZone", back_populates="cabinets")
    archives = relationship("Archive", back_populates="cabinet")


class StorageZone(Base):
    __tablename__ = "storage_zones"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    temperature_min = Column(Float, default=14.0)
    temperature_max = Column(Float, default=24.0)
    humidity_min = Column(Float, default=40.0)
    humidity_max = Column(Float, default=60.0)

    cabinets = relationship("StorageCabinet", back_populates="zone")
    sensors = relationship("Sensor", back_populates="zone")
