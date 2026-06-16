from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.schemas.schemas import (
    SensorCreate, SensorResponse,
    SensorReadingCreate, SensorReadingResponse,
    WorkOrderResponse
)
from app.models.user import User
from app.models.monitoring import Sensor
from app.services.monitoring_service import MonitoringService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/monitoring", tags=["库房监控"])


@router.post("/sensors", response_model=SensorResponse)
def create_sensor(
    sensor_data: SensorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    sensor = Sensor(**sensor_data.model_dump())
    db.add(sensor)
    db.commit()
    db.refresh(sensor)
    return sensor


@router.get("/sensors", response_model=List[SensorResponse])
def list_sensors(
    zone_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Sensor)
    if zone_id:
        query = query.filter(Sensor.zone_id == zone_id)
    return query.all()


@router.post("/sensors/readings")
def add_sensor_reading(
    reading_data: SensorReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success, message, reading = MonitoringService.add_sensor_reading(
        db,
        reading_data.sensor_id,
        reading_data.temperature,
        reading_data.humidity
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "reading": reading}


@router.get("/sensors/{sensor_id}/readings", response_model=List[SensorReadingResponse])
def get_sensor_readings(
    sensor_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return MonitoringService.get_sensor_readings(db, sensor_id, limit)


@router.get("/sensors/{sensor_id}/latest", response_model=SensorReadingResponse)
def get_latest_reading(
    sensor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    reading = MonitoringService.get_latest_reading(db, sensor_id)
    if not reading:
        raise HTTPException(status_code=404, detail="暂无读数")
    return reading


@router.get("/work-orders", response_model=List[WorkOrderResponse])
def list_work_orders(
    status: Optional[str] = None,
    order_type: Optional[str] = None,
    assigned_user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return MonitoringService.list_work_orders(db, status, order_type, assigned_user_id)


@router.get("/work-orders/my", response_model=List[WorkOrderResponse])
def get_my_work_orders(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return MonitoringService.list_work_orders(db, status, None, current_user.id)


@router.post("/work-orders/{order_id}/complete")
def complete_work_order(
    order_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success, message, work_order = MonitoringService.complete_work_order(
        db, order_id, current_user.id, remarks
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}
