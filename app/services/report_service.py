from typing import Optional, List, Tuple
from datetime import datetime, date
from io import BytesIO
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.report import MonthlyReport, OperationLog
from app.models.archive import Archive
from app.models.borrow import BorrowRecord
from app.models.digital import DigitalTask
from app.models.monitoring import SensorReading, WorkOrder
from app.models.storage import StorageZone, StorageCabinet
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment


class ReportService:
    @staticmethod
    def generate_monthly_report(db: Session, report_month: Optional[str] = None) -> List[MonthlyReport]:
        if report_month is None:
            today = date.today()
            report_month = f"{today.year}-{str(today.month).zfill(2)}"
        
        year, month = map(int, report_month.split("-"))
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        zones = db.query(StorageZone).all()
        reports = []
        
        for zone in zones:
            cabinets = db.query(StorageCabinet).filter(StorageCabinet.zone_id == zone.id).all()
            cabinet_ids = [c.id for c in cabinets]
            
            new_archives = db.query(Archive).filter(
                Archive.cabinet_id.in_(cabinet_ids),
                func.date(Archive.created_at) >= start_date,
                func.date(Archive.created_at) < end_date
            ).count()
            
            borrow_count = db.query(BorrowRecord).filter(
                BorrowRecord.archive_id.in_(
                    db.query(Archive.id).filter(Archive.cabinet_id.in_(cabinet_ids))
                ),
                func.date(BorrowRecord.borrow_date) >= start_date,
                func.date(BorrowRecord.borrow_date) < end_date
            ).count()
            
            digitization_count = db.query(DigitalTask).filter(
                DigitalTask.status == "completed",
                DigitalTask.archive_id.in_(
                    db.query(Archive.id).filter(Archive.cabinet_id.in_(cabinet_ids))
                ),
                func.date(DigitalTask.completed_at) >= start_date,
                func.date(DigitalTask.completed_at) < end_date
            ).count()
            
            total_archives_in_zone = db.query(Archive).filter(
                Archive.cabinet_id.in_(cabinet_ids)
            ).count()
            digitized_count = db.query(Archive).filter(
                Archive.cabinet_id.in_(cabinet_ids),
                Archive.is_digitized == True
            ).count()
            digitization_rate = (digitized_count / total_archives_in_zone * 100) if total_archives_in_zone > 0 else 0.0
            
            sensor_ids = db.query(Sensor.id).filter(Sensor.zone_id == zone.id).subquery()
            temp_warnings = db.query(SensorReading).filter(
                SensorReading.sensor_id.in_(sensor_ids),
                SensorReading.is_warning == True,
                SensorReading.temperature != None,
                func.date(SensorReading.reading_time) >= start_date,
                func.date(SensorReading.reading_time) < end_date
            ).count()
            
            humidity_warnings = db.query(SensorReading).filter(
                SensorReading.sensor_id.in_(sensor_ids),
                SensorReading.is_warning == True,
                SensorReading.humidity != None,
                func.date(SensorReading.reading_time) >= start_date,
                func.date(SensorReading.reading_time) < end_date
            ).count()
            
            total_warnings = db.query(WorkOrder).filter(
                WorkOrder.zone_id == zone.id,
                func.date(WorkOrder.created_at) >= start_date,
                func.date(WorkOrder.created_at) < end_date
            ).count()
            
            existing = db.query(MonthlyReport).filter(
                MonthlyReport.report_month == report_month,
                MonthlyReport.zone_code == zone.code
            ).first()
            
            if existing:
                existing.new_archives_count = new_archives
                existing.borrow_count = borrow_count
                existing.digitization_count = digitization_count
                existing.digitization_rate = round(digitization_rate, 2)
                existing.temp_warning_count = temp_warnings
                existing.humidity_warning_count = humidity_warnings
                existing.total_warning_count = total_warnings
                existing.generated_at = datetime.utcnow()
                report = existing
            else:
                report = MonthlyReport(
                    report_month=report_month,
                    zone_code=zone.code,
                    new_archives_count=new_archives,
                    borrow_count=borrow_count,
                    digitization_count=digitization_count,
                    digitization_rate=round(digitization_rate, 2),
                    temp_warning_count=temp_warnings,
                    humidity_warning_count=humidity_warnings,
                    total_warning_count=total_warnings
                )
                db.add(report)
            
            reports.append(report)
        
        db.commit()
        return reports

    @staticmethod
    def get_monthly_reports(
        db: Session,
        report_month: Optional[str] = None,
        zone_code: Optional[str] = None
    ) -> List[MonthlyReport]:
        query = db.query(MonthlyReport)
        if report_month:
            query = query.filter(MonthlyReport.report_month == report_month)
        if zone_code:
            query = query.filter(MonthlyReport.zone_code == zone_code)
        return query.order_by(MonthlyReport.report_month.desc()).all()

    @staticmethod
    def export_report_to_excel(
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        zone_code: Optional[str] = None,
        fonds_code: Optional[str] = None
    ) -> BytesIO:
        wb = Workbook()
        
        ws1 = wb.active
        ws1.title = "运营总览"
        headers = ["库区", "新增归档量", "借阅次数", "数字化数量", "数字化转化率(%)", "温度超标次数", "湿度超标次数", "总预警次数"]
        ws1.append(headers)
        for cell in ws1[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        
        reports = ReportService.get_monthly_reports(db, None, zone_code)
        for r in reports:
            ws1.append([
                r.zone_code, r.new_archives_count, r.borrow_count,
                r.digitization_count, r.digitization_rate,
                r.temp_warning_count, r.humidity_warning_count, r.total_warning_count
            ])
        
        ws2 = wb.create_sheet("档案明细")
        ws2.append(["索引号", "题名", "全宗号", "载体类型", "密级", "是否数字化", "入库日期", "状态"])
        for cell in ws2[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        
        archive_query = db.query(Archive)
        if fonds_code:
            archive_query = archive_query.filter(Archive.fonds_code == fonds_code)
        if start_date:
            archive_query = archive_query.filter(func.date(Archive.created_at) >= start_date)
        if end_date:
            archive_query = archive_query.filter(func.date(Archive.created_at) <= end_date)
        
        for a in archive_query.all():
            ws2.append([
                a.archive_index, a.title, a.fonds_code, a.carrier_type,
                a.security_level, "是" if a.is_digitized else "否",
                str(a.storage_start_date), a.status
            ])
        
        ws3 = wb.create_sheet("借阅记录")
        ws3.append(["借阅编号", "档案索引号", "申请人", "借阅日期", "应还日期", "实还日期", "状态", "逾期天数", "罚款金额"])
        for cell in ws3[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        
        borrow_query = db.query(BorrowRecord)
        if start_date:
            borrow_query = borrow_query.filter(func.date(BorrowRecord.borrow_date) >= start_date)
        if end_date:
            borrow_query = borrow_query.filter(func.date(BorrowRecord.borrow_date) <= end_date)
        
        for br in borrow_query.all():
            archive = db.query(Archive).filter(Archive.id == br.archive_id).first()
            ws3.append([
                br.record_no, archive.archive_index if archive else "",
                br.user_id, str(br.borrow_date), str(br.scheduled_return_date),
                str(br.actual_return_date) if br.actual_return_date else "",
                br.status, br.overdue_days, br.fine_amount
            ])
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @staticmethod
    def add_operation_log(
        db: Session,
        user_id: int,
        operation_type: str,
        target_type: str,
        target_id: int,
        description: str,
        ip_address: Optional[str] = None
    ):
        log = OperationLog(
            user_id=user_id,
            operation_type=operation_type,
            target_type=target_type,
            target_id=target_id,
            description=description,
            ip_address=ip_address
        )
        db.add(log)
        db.commit()
