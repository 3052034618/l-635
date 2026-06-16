from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.digital import DigitalTask, QualityCheck, TrainingWorkOrder
from app.models.archive import Archive
from app.models.user import User
from app.utils.helpers import generate_task_code
from app.services.notification_service import NotificationService


class DigitalService:
    @staticmethod
    def calculate_user_score(db: Session, user_id: int) -> float:
        tasks = db.query(DigitalTask).filter(
            DigitalTask.assigned_user_id == user_id,
            DigitalTask.status == "completed"
        ).all()
        
        if not tasks:
            return 50.0
        
        total_score = 0.0
        count = 0
        for task in tasks:
            avg_quality = (task.image_clarity_score + task.metadata_complete_score) / 2
            total_score += avg_quality
            count += 1
        
        success_rate = sum(1 for t in tasks if t.quality_check_pass) / max(len(tasks), 1) * 50
        quality_score = (total_score / max(count, 1)) * 0.5
        return success_rate + quality_score

    @staticmethod
    def auto_assign_user(db: Session, task_type: str = "scan") -> Optional[User]:
        eligible_users = db.query(User).filter(
            User.role.in_(["digitizer", "admin", "archivist"]),
            User.is_active == True
        ).all()
        
        if not eligible_users:
            return None
        
        user_scores = []
        for user in eligible_users:
            active_tasks = db.query(DigitalTask).filter(
                DigitalTask.assigned_user_id == user.id,
                DigitalTask.status.in_(["pending", "in_progress"])
            ).count()
            
            score = DigitalService.calculate_user_score(db, user.id)
            load_factor = max(0, 100 - active_tasks * 10)
            final_score = score * 0.6 + load_factor * 0.4
            user_scores.append((final_score, user))
        
        user_scores.sort(key=lambda x: x[0], reverse=True)
        return user_scores[0][1] if user_scores else None

    @staticmethod
    def create_digital_task(
        db: Session,
        task_data: dict,
        auto_assign: bool = True
    ) -> DigitalTask:
        task_no = generate_task_code("DT")
        
        assigned_user_id = None
        if auto_assign:
            assigned_user = DigitalService.auto_assign_user(db, task_data.get("task_type", "scan"))
            if assigned_user:
                assigned_user_id = assigned_user.id
        
        task = DigitalTask(
            task_no=task_no,
            archive_id=task_data.get("archive_id"),
            batch_no=task_data.get("batch_no"),
            assigned_user_id=assigned_user_id,
            task_type=task_data.get("task_type", "scan"),
            priority=task_data.get("priority", 2),
            total_pages=task_data.get("total_pages", 0),
            deadline=task_data.get("deadline"),
            status="pending"
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        if assigned_user_id:
            NotificationService.create_notification(
                db,
                assigned_user_id,
                f"新的数字化任务: {task_no}",
                f"请及时处理档案数字化加工任务",
                "digital_task",
                related_id=task.id,
                related_type="digital_task"
            )
        
        return task

    @staticmethod
    def start_task(db: Session, task_id: int, user_id: int) -> Tuple[bool, str, Optional[DigitalTask]]:
        task = db.query(DigitalTask).filter(DigitalTask.id == task_id).first()
        if not task:
            return False, "任务不存在", None
        
        if task.assigned_user_id and task.assigned_user_id != user_id:
            return False, "该任务已分配给其他人员", None
        
        if task.status not in ["pending", "reassigned"]:
            return False, "任务状态不允许开始", None
        
        task.status = "in_progress"
        task.assigned_user_id = user_id
        task.started_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        return True, "任务已开始", task

    @staticmethod
    def update_progress(
        db: Session,
        task_id: int,
        completed_pages: int
    ) -> Tuple[bool, str, Optional[DigitalTask]]:
        task = db.query(DigitalTask).filter(DigitalTask.id == task_id).first()
        if not task:
            return False, "任务不存在", None
        
        if task.status != "in_progress":
            return False, "任务未开始进行", None
        
        task.completed_pages = completed_pages
        if task.total_pages > 0:
            task.progress = min(100, int(completed_pages / task.total_pages * 100))
        db.commit()
        db.refresh(task)
        return True, "进度已更新", task

    @staticmethod
    def submit_for_quality_check(
        db: Session,
        task_id: int,
        image_clarity_score: float,
        metadata_complete_score: float
    ) -> Tuple[bool, str, Optional[DigitalTask]]:
        task = db.query(DigitalTask).filter(DigitalTask.id == task_id).first()
        if not task:
            return False, "任务不存在", None
        
        task.image_clarity_score = image_clarity_score
        task.metadata_complete_score = metadata_complete_score
        task.status = "quality_checking"
        db.commit()
        db.refresh(task)
        
        NotificationService.notify_archive_admins(
            db,
            f"数字化任务待质检: {task.task_no}",
            f"任务已完成，请进行质量检查",
            related_id=task.id,
            related_type="digital_task"
        )
        
        return True, "已提交质检", task

    @staticmethod
    def quality_check(
        db: Session,
        task_id: int,
        checker_id: int,
        image_clarity_score: float,
        metadata_complete_score: float,
        is_passed: bool,
        rejection_reason: Optional[str] = None
    ) -> Tuple[bool, str, Optional[DigitalTask]]:
        task = db.query(DigitalTask).filter(DigitalTask.id == task_id).first()
        if not task:
            return False, "任务不存在", None
        
        if task.status != "quality_checking":
            return False, "任务不在质检状态", None
        
        quality_check_record = QualityCheck(
            task_id=task_id,
            archive_id=task.archive_id,
            checked_by=checker_id,
            image_clarity_score=image_clarity_score,
            metadata_complete_score=metadata_complete_score,
            is_passed=is_passed,
            rejection_reason=rejection_reason
        )
        db.add(quality_check_record)
        
        if is_passed:
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            task.quality_check_pass = True
            task.image_clarity_score = image_clarity_score
            task.metadata_complete_score = metadata_complete_score
            task.consecutive_fail_count = 0
            
            archive = db.query(Archive).filter(Archive.id == task.archive_id).first()
            if archive:
                archive.is_digitized = True
                archive.digitization_quality = (image_clarity_score + metadata_complete_score) / 2
                archive.metadata_complete = metadata_complete_score >= 80
            
            if task.assigned_user_id:
                NotificationService.create_notification(
                    db,
                    task.assigned_user_id,
                    f"数字化任务质检通过: {task.task_no}",
                    "恭喜！您的任务已通过质量检查",
                    "digital_task",
                    related_id=task.id,
                    related_type="digital_task"
                )
        else:
            task.status = "rejected"
            task.quality_check_pass = False
            task.consecutive_fail_count += 1
            task.image_clarity_score = image_clarity_score
            task.metadata_complete_score = metadata_complete_score
            
            if task.assigned_user_id:
                NotificationService.create_notification(
                    db,
                    task.assigned_user_id,
                    f"数字化任务质检不合格: {task.task_no}",
                    f"退回原因: {rejection_reason or '未说明'}，请重新加工",
                    "digital_task",
                    related_id=task.id,
                    related_type="digital_task"
                )
            
            if task.consecutive_fail_count >= 3 and task.batch_no:
                DigitalService.create_training_work_order(
                    db, task.assigned_user_id, task.batch_no, task.consecutive_fail_count,
                    f"同一批次连续{task.consecutive_fail_count}次质检不合格"
                )
        
        db.commit()
        db.refresh(task)
        return True, "质检完成", task

    @staticmethod
    def reassign_task(
        db: Session,
        task_id: int
    ) -> Tuple[bool, str, Optional[DigitalTask]]:
        task = db.query(DigitalTask).filter(DigitalTask.id == task_id).first()
        if not task:
            return False, "任务不存在", None
        
        new_user = DigitalService.auto_assign_user(db, task.task_type)
        if not new_user:
            return False, "无可用人员", None
        
        task.assigned_user_id = new_user.id
        task.status = "reassigned"
        task.consecutive_fail_count = 0
        db.commit()
        db.refresh(task)
        
        NotificationService.create_notification(
            db,
            new_user.id,
            f"数字化任务已重新分配: {task.task_no}",
            "请及时处理该任务",
            "digital_task",
            related_id=task.id,
            related_type="digital_task"
        )
        
        return True, "任务已重新分配", task

    @staticmethod
    def create_training_work_order(
        db: Session,
        user_id: Optional[int],
        batch_no: str,
        fail_count: int,
        reason: str
    ) -> TrainingWorkOrder:
        order_no = generate_task_code("TWO")
        work_order = TrainingWorkOrder(
            order_no=order_no,
            user_id=user_id,
            batch_no=batch_no,
            fail_count=fail_count,
            reason=reason,
            status="pending"
        )
        db.add(work_order)
        db.commit()
        db.refresh(work_order)
        
        NotificationService.notify_archive_admins(
            db,
            f"培训建议工单: {order_no}",
            f"批次{batch_no}连续{fail_count}次不合格，请安排培训",
            related_id=work_order.id,
            related_type="training"
        )
        
        return work_order

    @staticmethod
    def list_tasks(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        assigned_user_id: Optional[int] = None,
        batch_no: Optional[str] = None
    ) -> Tuple[int, List[DigitalTask]]:
        query = db.query(DigitalTask)
        if status:
            query = query.filter(DigitalTask.status == status)
        if assigned_user_id:
            query = query.filter(DigitalTask.assigned_user_id == assigned_user_id)
        if batch_no:
            query = query.filter(DigitalTask.batch_no == batch_no)
        
        total = query.count()
        items = query.order_by(DigitalTask.created_at.desc()).offset(skip).limit(limit).all()
        return total, items
