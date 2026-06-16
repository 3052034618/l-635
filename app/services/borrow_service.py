from typing import Optional, List, Tuple
from datetime import datetime, date, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.borrow import BorrowRecord, OutboundTask, Fine
from app.models.archive import Archive
from app.models.user import User
from app.config import settings
from app.utils.helpers import generate_task_code
from app.services.notification_service import NotificationService


def _to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class BorrowService:
    @staticmethod
    def check_permission(db: Session, user_id: int, archive_id: int) -> Tuple[bool, str]:
        user = db.query(User).filter(User.id == user_id).first()
        archive = db.query(Archive).filter(Archive.id == archive_id).first()
        
        if not user or not archive:
            return False, "用户或档案不存在"
        
        if not user.is_active:
            return False, "用户账号已停用"
        
        if user.permission_level < archive.security_level:
            return False, f"用户权限等级不足，档案密级为{archive.security_level}级"
        
        if archive.status != "in_storage":
            return False, "档案不在库中，当前状态: " + archive.status
        
        unpaid_fines = db.query(Fine).filter(
            Fine.user_id == user_id,
            Fine.status == "unpaid"
        ).count()
        if unpaid_fines > 0:
            return False, "存在未缴纳的罚款，请先处理后再借阅"
        
        return True, "权限校验通过"

    @staticmethod
    def validate_scheduled_time(
        scheduled_outbound_time: datetime,
        scheduled_return_date: date
    ) -> Tuple[bool, str]:
        now = datetime.utcnow()
        
        if scheduled_outbound_time is None:
            return False, "预约出库时间不能为空"
        
        scheduled_naive = _to_naive_utc(scheduled_outbound_time)
        
        if scheduled_naive <= now:
            return False, f"预约出库时间已过期，请选择未来的时间（当前服务器时间: {now.strftime('%Y-%m-%d %H:%M')}）"
        
        outbound_date = scheduled_naive.date()
        if outbound_date >= scheduled_return_date:
            return False, "预约出库时间不能晚于或等于归还日期"
        
        max_borrow_days = 90
        if (scheduled_return_date - outbound_date).days > max_borrow_days:
            return False, f"借阅期限过长，最长借阅时间为{max_borrow_days}天"
        
        return True, "预约时间校验通过"

    @staticmethod
    def calculate_fine(overdue_days: int) -> Tuple[int, float, float]:
        if overdue_days <= 0:
            return 1, 0.0, 0.0
        
        if overdue_days <= 7:
            tier = 1
            daily_rate = settings.OVERDUE_FINE_RATE_1
        elif overdue_days <= 30:
            tier = 2
            daily_rate = settings.OVERDUE_FINE_RATE_2
        else:
            tier = 3
            daily_rate = settings.OVERDUE_FINE_RATE_3
        
        total_amount = overdue_days * daily_rate
        return tier, daily_rate, total_amount

    @staticmethod
    def create_borrow_record(
        db: Session,
        user_id: int,
        borrow_data: dict
    ) -> Tuple[bool, str, Optional[BorrowRecord]]:
        archive_id = borrow_data.get("archive_id")
        is_permitted, message = BorrowService.check_permission(db, user_id, archive_id)
        if not is_permitted:
            return False, message, None
        
        scheduled_outbound_time = borrow_data.get("scheduled_outbound_time")
        scheduled_return_date = borrow_data.get("scheduled_return_date")
        
        if isinstance(scheduled_outbound_time, str):
            try:
                scheduled_outbound_time = datetime.fromisoformat(scheduled_outbound_time.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                return False, "预约出库时间格式错误，请使用标准格式: YYYY-MM-DDTHH:MM:SS", None
        
        is_valid, time_msg = BorrowService.validate_scheduled_time(scheduled_outbound_time, scheduled_return_date)
        if not is_valid:
            return False, time_msg, None
        
        scheduled_outbound_naive = _to_naive_utc(scheduled_outbound_time)
        
        record_no = generate_task_code("BR")
        
        borrow_record = BorrowRecord(
            record_no=record_no,
            user_id=user_id,
            archive_id=archive_id,
            borrow_type=borrow_data.get("borrow_type", "physical"),
            purpose=borrow_data.get("purpose"),
            scheduled_outbound_time=scheduled_outbound_naive,
            scheduled_return_date=scheduled_return_date,
            status="pending",
            approval_status="pending"
        )
        db.add(borrow_record)
        db.commit()
        db.refresh(borrow_record)
        
        NotificationService.notify_archive_admins(
            db,
            f"借阅申请待审批: {borrow_record.record_no}",
            f"用户申请借阅档案，预约出库时间: {scheduled_outbound_naive.strftime('%Y-%m-%d %H:%M')}，请及时审批",
            related_id=borrow_record.id,
            related_type="borrow"
        )
        
        return True, "借阅申请已提交，等待审批", borrow_record

    @staticmethod
    def approve_borrow(
        db: Session,
        record_id: int,
        approve: bool,
        admin_id: int,
        rejection_reason: Optional[str] = None
    ) -> Tuple[bool, str, Optional[BorrowRecord]]:
        record = db.query(BorrowRecord).filter(BorrowRecord.id == record_id).first()
        if not record:
            return False, "借阅记录不存在", None
        
        if record.approval_status != "pending":
            return False, "该借阅申请已处理", None
        
        if approve:
            now = datetime.utcnow()
            if record.scheduled_outbound_time <= now:
                return False, f"预约出库时间已过期（{record.scheduled_outbound_time.strftime('%Y-%m-%d %H:%M')}），无法审批通过，请拒绝后让用户重新申请", None
        
        record.approved_by = admin_id
        record.approval_time = datetime.utcnow()
        
        if approve:
            record.approval_status = "approved"
            record.status = "approved"
            
            BorrowService.create_outbound_task(db, record)
            
            archive = db.query(Archive).filter(Archive.id == record.archive_id).first()
            if archive:
                archive.status = "reserved"
                db.commit()
            
            NotificationService.create_notification(
                db,
                record.user_id,
                f"借阅申请已通过: {record.record_no}",
                f"您的借阅申请已审批通过，预约出库时间: {record.scheduled_outbound_time.strftime('%Y-%m-%d %H:%M')}，请按时取件",
                "borrow",
                related_id=record.id,
                related_type="borrow"
            )

            NotificationService.notify_archive_admins(
                db,
                f"借阅审批通过: {record.record_no}",
                f"借阅申请已通过审批，预约出库时间: {record.scheduled_outbound_time.strftime('%Y-%m-%d %H:%M')}",
                related_id=record.id,
                related_type="borrow"
            )
        else:
            record.approval_status = "rejected"
            record.status = "rejected"
            record.rejection_reason = rejection_reason
            
            NotificationService.create_notification(
                db,
                record.user_id,
                f"借阅申请被拒绝: {record.record_no}",
                f"拒绝原因: {rejection_reason or '未说明'}",
                "borrow",
                related_id=record.id,
                related_type="borrow"
            )

            NotificationService.notify_archive_admins(
                db,
                f"借阅审批拒绝: {record.record_no}",
                f"借阅申请已拒绝。原因: {rejection_reason or '未说明'}",
                related_id=record.id,
                related_type="borrow"
            )
        
        db.commit()
        db.refresh(record)
        return True, "处理完成", record

    @staticmethod
    def create_outbound_task(db: Session, borrow_record: BorrowRecord) -> OutboundTask:
        active_admins = db.query(User).filter(
            User.role.in_(["admin", "archivist"]),
            User.is_active == True
        ).all()
        
        admin_user = None
        min_tasks = float('inf')
        for u in active_admins:
            pending_tasks = db.query(OutboundTask).filter(
                OutboundTask.admin_user_id == u.id,
                OutboundTask.status == "pending"
            ).count()
            if pending_tasks < min_tasks:
                min_tasks = pending_tasks
                admin_user = u
        
        task_no = generate_task_code("OT")
        scheduled_time = borrow_record.scheduled_outbound_time
        
        outbound_task = OutboundTask(
            task_no=task_no,
            borrow_record_id=borrow_record.id,
            archive_id=borrow_record.archive_id,
            admin_user_id=admin_user.id if admin_user else None,
            scheduled_time=scheduled_time,
            status="pending"
        )
        db.add(outbound_task)
        db.commit()
        db.refresh(outbound_task)
        
        if admin_user:
            NotificationService.create_notification(
                db,
                admin_user.id,
                f"出库任务待处理: {task_no}",
                f"请按时完成档案出库，预约出库时间: {scheduled_time.strftime('%Y-%m-%d %H:%M')}",
                "outbound",
                related_id=outbound_task.id,
                related_type="outbound"
            )
        
        return outbound_task

    @staticmethod
    def complete_outbound(db: Session, task_id: int, admin_id: int) -> Tuple[bool, str]:
        task = db.query(OutboundTask).filter(OutboundTask.id == task_id).first()
        if not task:
            return False, "出库任务不存在"
        
        task.status = "completed"
        task.completed_time = datetime.utcnow()
        task.admin_user_id = admin_id
        
        borrow_record = db.query(BorrowRecord).filter(
            BorrowRecord.id == task.borrow_record_id
        ).first()
        if borrow_record:
            borrow_record.status = "borrowed"
        
        archive = db.query(Archive).filter(Archive.id == task.archive_id).first()
        if archive:
            archive.status = "borrowed"
            archive.last_access_date = date.today()
        
        db.commit()
        return True, "出库完成"

    @staticmethod
    def return_archive(db: Session, record_id: int) -> Tuple[bool, str]:
        record = db.query(BorrowRecord).filter(BorrowRecord.id == record_id).first()
        if not record:
            return False, "借阅记录不存在"
        
        actual_return = date.today()
        record.actual_return_date = actual_return
        record.status = "returned"
        
        scheduled_return = record.scheduled_return_date
        if actual_return > scheduled_return:
            overdue_days = (actual_return - scheduled_return).days
            record.overdue_days = overdue_days
            
            tier, daily_rate, total_amount = BorrowService.calculate_fine(overdue_days)
            record.fine_amount = total_amount
            
            fine = Fine(
                borrow_record_id=record.id,
                user_id=record.user_id,
                overdue_days=overdue_days,
                tier=tier,
                daily_rate=daily_rate,
                total_amount=total_amount,
                status="unpaid"
            )
            db.add(fine)
            
            NotificationService.create_notification(
                db,
                record.user_id,
                f"归还逾期，产生罚款",
                f"逾期{overdue_days}天，罚款金额: ¥{total_amount}",
                "fine",
                related_id=record.id,
                related_type="fine"
            )

            NotificationService.notify_archive_admins(
                db,
                f"逾期罚款已生成: {record.record_no}",
                f"用户ID:{record.user_id} 逾期{overdue_days}天，罚款金额: ¥{total_amount}",
                related_id=record.id,
                related_type="fine"
            )
        
        archive = db.query(Archive).filter(Archive.id == record.archive_id).first()
        if archive:
            archive.status = "in_storage"
            archive.last_access_date = actual_return
        
        db.commit()
        return True, "归还成功"

    @staticmethod
    def check_overdue_and_send_reminders(db: Session) -> List[BorrowRecord]:
        today = date.today()
        reminder_date = today + timedelta(days=3)
        
        due_soon_records = db.query(BorrowRecord).filter(
            BorrowRecord.status == "borrowed",
            BorrowRecord.scheduled_return_date <= reminder_date,
            BorrowRecord.scheduled_return_date > today,
            BorrowRecord.reminder_sent == False
        ).all()
        
        for record in due_soon_records:
            NotificationService.create_notification(
                db,
                record.user_id,
                f"借阅即将到期提醒",
                f"您借阅的档案将于{record.scheduled_return_date}到期，请按时归还",
                "reminder",
                related_id=record.id,
                related_type="borrow"
            )
            record.reminder_sent = True
        
        overdue_records = db.query(BorrowRecord).filter(
            BorrowRecord.status == "borrowed",
            BorrowRecord.scheduled_return_date < today
        ).all()
        
        for record in overdue_records:
            overdue_days = (today - record.scheduled_return_date).days
            record.overdue_days = overdue_days
            tier, daily_rate, total_amount = BorrowService.calculate_fine(overdue_days)
            record.fine_amount = total_amount
        
        db.commit()
        return due_soon_records + overdue_records

    @staticmethod
    def get_user_borrow_records(
        db: Session,
        user_id: int,
        status: Optional[str] = None
    ) -> List[BorrowRecord]:
        query = db.query(BorrowRecord).filter(BorrowRecord.user_id == user_id)
        if status:
            query = query.filter(BorrowRecord.status == status)
        return query.order_by(BorrowRecord.created_at.desc()).all()

    @staticmethod
    def get_pending_approvals(db: Session) -> List[BorrowRecord]:
        return db.query(BorrowRecord).filter(
            BorrowRecord.approval_status == "pending"
        ).order_by(BorrowRecord.created_at.desc()).all()
