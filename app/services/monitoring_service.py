from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.monitoring import Sensor, SensorReading, WorkOrder
from app.models.storage import StorageZone
from app.models.user import User
from app.config import settings
from app.utils.helpers import generate_task_code
from app.services.notification_service import NotificationService


class MonitoringService:
    @staticmethod
    def check_thresholds(
        temperature: Optional[float],
        humidity: Optional[float],
        zone: Optional[StorageZone] = None
    ) -> Tuple[bool, List[str]]:
        is_warning = False
        warnings = []
        
        temp_min = zone.temperature_min if zone else settings.TEMPERATURE_MIN
        temp_max = zone.temperature_max if zone else settings.TEMPERATURE_MAX
        hum_min = zone.humidity_min if zone else settings.HUMIDITY_MIN
        hum_max = zone.humidity_max if zone else settings.HUMIDITY_MAX
        
        if temperature is not None:
            if temperature > temp_max:
                is_warning = True
                warnings.append(f"温度过高: {temperature}°C，上限: {temp_max}°C")
            elif temperature < temp_min:
                is_warning = True
                warnings.append(f"温度过低: {temperature}°C，下限: {temp_min}°C")
        
        if humidity is not None:
            if humidity > hum_max:
                is_warning = True
                warnings.append(f"湿度过高: {humidity}%，上限: {hum_max}%")
            elif humidity < hum_min:
                is_warning = True
                warnings.append(f"湿度过低: {humidity}%，下限: {hum_min}%")
        
        return is_warning, warnings

    @staticmethod
    def determine_device_status(
        temperature: Optional[float],
        humidity: Optional[float],
        zone: Optional[StorageZone] = None
    ) -> Tuple[str, str]:
        temp_min = zone.temperature_min if zone else settings.TEMPERATURE_MIN
        temp_max = zone.temperature_max if zone else settings.TEMPERATURE_MAX
        hum_min = zone.humidity_min if zone else settings.HUMIDITY_MIN
        hum_max = zone.humidity_max if zone else settings.HUMIDITY_MAX
        
        ac_status = "off"
        if temperature is not None:
            if temperature > temp_max + 1:
                ac_status = "cooling"
            elif temperature < temp_min - 1:
                ac_status = "heating"
        
        dehumidifier_status = "off"
        if humidity is not None:
            if humidity > hum_max + 3:
                dehumidifier_status = "dehumidifying"
            elif humidity < hum_min - 5:
                dehumidifier_status = "humidifying"
        
        return ac_status, dehumidifier_status

    @staticmethod
    def add_sensor_reading(
        db: Session,
        sensor_id: int,
        temperature: Optional[float] = None,
        humidity: Optional[float] = None
    ) -> Tuple[bool, str, Optional[SensorReading]]:
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            return False, "传感器不存在", None
        
        zone = None
        if sensor.zone_id:
            zone = db.query(StorageZone).filter(StorageZone.id == sensor.zone_id).first()
        
        is_warning, warnings = MonitoringService.check_thresholds(temperature, humidity, zone)
        ac_status, dehumidifier_status = MonitoringService.determine_device_status(temperature, humidity, zone)
        
        reading = SensorReading(
            sensor_id=sensor_id,
            temperature=temperature,
            humidity=humidity,
            is_warning=is_warning
        )
        db.add(reading)
        db.commit()
        db.refresh(reading)
        
        if is_warning:
            existing_pending = db.query(WorkOrder).filter(
                WorkOrder.sensor_id == sensor_id,
                WorkOrder.status.in_(["pending", "in_progress"]),
                WorkOrder.created_at >= datetime.utcnow() - timedelta(hours=1)
            ).first()
            
            if not existing_pending:
                MonitoringService.create_warning_work_order(
                    db, sensor_id, temperature, humidity, warnings, ac_status, dehumidifier_status
                )
        
        return True, "数据已上传", reading

    @staticmethod
    def create_warning_work_order(
        db: Session,
        sensor_id: int,
        temperature: Optional[float],
        humidity: Optional[float],
        warnings: List[str],
        ac_status: str,
        dehumidifier_status: str
    ) -> WorkOrder:
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        
        maintenance_user = db.query(User).filter(
            User.role.in_(["maintenance", "admin"]),
            User.is_active == True
        ).first()
        
        order_no = generate_task_code("WO")
        warning_msg = "; ".join(warnings) if warnings else "环境异常"
        
        work_order = WorkOrder(
            order_no=order_no,
            order_type="environment_warning",
            zone_id=sensor.zone_id if sensor else None,
            sensor_id=sensor_id,
            assigned_user_id=maintenance_user.id if maintenance_user else None,
            title=f"库房环境预警: {sensor.name if sensor else '未知传感器'}",
            description=warning_msg,
            priority=1,
            status="pending",
            temperature=temperature,
            humidity=humidity,
            ac_status=ac_status,
            dehumidifier_status=dehumidifier_status
        )
        db.add(work_order)
        db.commit()
        db.refresh(work_order)
        
        if maintenance_user:
            NotificationService.create_notification(
                db,
                maintenance_user.id,
                f"环境预警工单: {order_no}",
                f"{warning_msg}，请及时处理",
                "warning",
                related_id=work_order.id,
                related_type="work_order"
            )
        
        NotificationService.notify_archive_admins(
            db,
            f"库房环境预警: {order_no}",
            warning_msg,
            related_id=work_order.id,
            related_type="work_order"
        )
        
        return work_order

    @staticmethod
    def get_sensor_readings(
        db: Session,
        sensor_id: int,
        limit: int = 100
    ) -> List[SensorReading]:
        return db.query(SensorReading).filter(
            SensorReading.sensor_id == sensor_id
        ).order_by(SensorReading.reading_time.desc()).limit(limit).all()

    @staticmethod
    def get_latest_reading(db: Session, sensor_id: int) -> Optional[SensorReading]:
        return db.query(SensorReading).filter(
            SensorReading.sensor_id == sensor_id
        ).order_by(SensorReading.reading_time.desc()).first()

    @staticmethod
    def list_work_orders(
        db: Session,
        status: Optional[str] = None,
        order_type: Optional[str] = None,
        assigned_user_id: Optional[int] = None
    ) -> List[WorkOrder]:
        query = db.query(WorkOrder)
        if status:
            query = query.filter(WorkOrder.status == status)
        if order_type:
            query = query.filter(WorkOrder.order_type == order_type)
        if assigned_user_id:
            query = query.filter(WorkOrder.assigned_user_id == assigned_user_id)
        return query.order_by(WorkOrder.created_at.desc()).all()

    @staticmethod
    def complete_work_order(
        db: Session,
        order_id: int,
        user_id: int,
        remarks: Optional[str] = None
    ) -> Tuple[bool, str, Optional[WorkOrder]]:
        work_order = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
        if not work_order:
            return False, "工单不存在", None
        
        work_order.status = "completed"
        work_order.completed_at = datetime.utcnow()
        work_order.remarks = remarks
        db.commit()
        db.refresh(work_order)
        
        return True, "工单已完成", work_order
