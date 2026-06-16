from typing import Optional, List, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session

from app.models.notification import AppraisalRecord, DestructionRecord
from app.models.archive import Archive
from app.config import settings
from app.utils.helpers import generate_task_code
from app.services.notification_service import NotificationService


class AppraisalService:
    @staticmethod
    def find_unused_archives(db: Session, years: Optional[int] = None) -> List[Archive]:
        threshold_years = years or settings.NOT_UTILIZED_YEARS
        today = date.today()
        threshold_date = date(today.year - threshold_years, today.month, today.day)
        
        return db.query(Archive).filter(
            Archive.status == "in_storage",
            (Archive.last_access_date == None) | (Archive.last_access_date <= threshold_date),
            Archive.storage_start_date <= threshold_date
        ).all()

    @staticmethod
    def generate_appraisal_suggestions(db: Session) -> List[AppraisalRecord]:
        unused_archives = AppraisalService.find_unused_archives(db)
        appraisal_records = []
        
        for archive in unused_archives:
            existing = db.query(AppraisalRecord).filter(
                AppraisalRecord.archive_id == archive.id,
                AppraisalRecord.status.in_(["pending", "in_review"])
            ).first()
            if existing:
                continue
            
            record_no = generate_task_code("AP")
            appraisal = AppraisalRecord(
                record_no=record_no,
                archive_id=archive.id,
                appraisal_type="periodic",
                reason=f"档案超过{settings.NOT_UTILIZED_YEARS}年未利用",
                proposed_action="review",
                status="pending"
            )
            db.add(appraisal)
            appraisal_records.append(appraisal)
        
        db.commit()
        
        for record in appraisal_records:
            db.refresh(record)
        
        if appraisal_records:
            NotificationService.notify_archive_admins(
                db,
                f"档案鉴定建议清单已生成",
                f"共生成{len(appraisal_records)}条超期未利用档案鉴定建议，请专家委员会审核",
                related_type="appraisal"
            )
        
        return appraisal_records

    @staticmethod
    def submit_for_review(
        db: Session,
        record_id: int,
        proposed_action: str,
        reason: Optional[str] = None
    ) -> Tuple[bool, str, Optional[AppraisalRecord]]:
        record = db.query(AppraisalRecord).filter(AppraisalRecord.id == record_id).first()
        if not record:
            return False, "鉴定记录不存在", None
        
        record.status = "in_review"
        record.proposed_action = proposed_action
        if reason:
            record.reason = reason
        db.commit()
        db.refresh(record)
        
        NotificationService.notify_archive_admins(
            db,
            f"档案鉴定待会签: {record.record_no}",
            f"请专家委员会进行会签，建议动作: {proposed_action}",
            related_id=record.id,
            related_type="appraisal"
        )
        
        return True, "已提交审核", record

    @staticmethod
    def expert_sign_off(
        db: Session,
        record_id: int,
        expert_id: int,
        expert_name: str
    ) -> Tuple[bool, str, Optional[AppraisalRecord]]:
        record = db.query(AppraisalRecord).filter(AppraisalRecord.id == record_id).first()
        if not record:
            return False, "鉴定记录不存在", None
        
        signatures = record.expert_signatures or ""
        if expert_name not in signatures:
            signatures = signatures + "," + expert_name if signatures else expert_name
            record.expert_signatures = signatures
        db.commit()
        db.refresh(record)
        return True, "会签完成", record

    @staticmethod
    def finalize_appraisal(
        db: Session,
        record_id: int,
        final_decision: str,
        decision_by: int
    ) -> Tuple[bool, str, Optional[AppraisalRecord]]:
        record = db.query(AppraisalRecord).filter(AppraisalRecord.id == record_id).first()
        if not record:
            return False, "鉴定记录不存在", None
        
        record.final_decision = final_decision
        record.decision_date = date.today()
        record.status = "completed"
        record.created_by = decision_by
        db.commit()
        db.refresh(record)
        
        if final_decision == "destroy":
            archive = db.query(Archive).filter(Archive.id == record.archive_id).first()
            if archive:
                archive.status = "pending_destruction"
        
        NotificationService.notify_archive_admins(
            db,
            f"档案鉴定完成: {record.record_no}",
            f"最终决定: {final_decision}",
            related_id=record.id,
            related_type="appraisal"
        )
        
        return True, "鉴定完成", record

    @staticmethod
    def create_destruction_record(
        db: Session,
        appraisal_id: int,
        archive_id: int,
        destruction_method: Optional[str] = None
    ) -> Tuple[bool, str, Optional[DestructionRecord]]:
        record_no = generate_task_code("DS")
        destruction = DestructionRecord(
            record_no=record_no,
            appraisal_id=appraisal_id,
            archive_id=archive_id,
            destruction_method=destruction_method or "shredding",
            status="pending"
        )
        db.add(destruction)
        db.commit()
        db.refresh(destruction)
        
        NotificationService.notify_archive_admins(
            db,
            f"销毁任务待执行: {record_no}",
            "请安排双人见证并执行档案销毁",
            related_id=destruction.id,
            related_type="destruction"
        )
        
        return True, "销毁记录已创建", destruction

    @staticmethod
    def witness_sign(
        db: Session,
        destruction_id: int,
        witness_id: int,
        witness_number: int
    ) -> Tuple[bool, str, Optional[DestructionRecord]]:
        destruction = db.query(DestructionRecord).filter(DestructionRecord.id == destruction_id).first()
        if not destruction:
            return False, "销毁记录不存在", None
        
        if witness_number == 1:
            destruction.witness_1_id = witness_id
            destruction.witness_1_signature = True
        elif witness_number == 2:
            destruction.witness_2_id = witness_id
            destruction.witness_2_signature = True
        
        db.commit()
        db.refresh(destruction)
        return True, "见证签名完成", destruction

    @staticmethod
    def complete_destruction(
        db: Session,
        destruction_id: int,
        evidence_file: Optional[str] = None,
        remarks: Optional[str] = None
    ) -> Tuple[bool, str, Optional[DestructionRecord]]:
        destruction = db.query(DestructionRecord).filter(DestructionRecord.id == destruction_id).first()
        if not destruction:
            return False, "销毁记录不存在", None
        
        if not destruction.witness_1_signature or not destruction.witness_2_signature:
            return False, "需要双人见证签名", None
        
        destruction.destruction_date = datetime.utcnow()
        destruction.evidence_file = evidence_file
        destruction.remarks = remarks
        destruction.status = "completed"
        
        archive = db.query(Archive).filter(Archive.id == destruction.archive_id).first()
        if archive:
            archive.status = "destroyed"
        
        db.commit()
        db.refresh(destruction)
        return True, "销毁完成", destruction

    @staticmethod
    def list_appraisals(
        db: Session,
        status: Optional[str] = None
    ) -> List[AppraisalRecord]:
        query = db.query(AppraisalRecord)
        if status:
            query = query.filter(AppraisalRecord.status == status)
        return query.order_by(AppraisalRecord.created_at.desc()).all()
