from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.schemas.schemas import (
    AppraisalRecordCreate, AppraisalRecordResponse,
    DestructionCreate, DestructionRecordResponse
)
from app.models.user import User
from app.services.appraisal_service import AppraisalService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/appraisal", tags=["档案鉴定与销毁"])


@router.post("/generate-suggestions")
def generate_appraisal_suggestions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    records = AppraisalService.generate_appraisal_suggestions(db)
    return {"success": True, "count": len(records), "records": records}


@router.get("/unused-archives")
def find_unused_archives(
    years: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.schemas.schemas import ArchiveResponse
    archives = AppraisalService.find_unused_archives(db, years)
    return {"total": len(archives), "archives": archives}


@router.post("/records", response_model=AppraisalRecordResponse)
def create_appraisal_record(
    data: AppraisalRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    from app.utils.helpers import generate_task_code
    from app.models.notification import AppraisalRecord
    record = AppraisalRecord(
        record_no=generate_task_code("AP"),
        **data.model_dump(),
        created_by=current_user.id
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/records", response_model=List[AppraisalRecordResponse])
def list_appraisal_records(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return AppraisalService.list_appraisals(db, status)


@router.post("/records/{record_id}/submit-review")
def submit_for_review(
    record_id: int,
    proposed_action: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    success, message, record = AppraisalService.submit_for_review(db, record_id, proposed_action, reason)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.post("/records/{record_id}/sign-off")
def expert_sign_off(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success, message, record = AppraisalService.expert_sign_off(
        db, record_id, current_user.id, current_user.full_name
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.post("/records/{record_id}/finalize")
def finalize_appraisal(
    record_id: int,
    final_decision: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="权限不足")
    success, message, record = AppraisalService.finalize_appraisal(
        db, record_id, final_decision, current_user.id
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.post("/destructions", response_model=DestructionRecordResponse)
def create_destruction(
    data: DestructionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="权限不足")
    success, message, record = AppraisalService.create_destruction_record(
        db, data.appraisal_id, data.archive_id, data.destruction_method
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return record


@router.post("/destructions/{destruction_id}/witness-sign")
def witness_sign(
    destruction_id: int,
    witness_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success, message, record = AppraisalService.witness_sign(
        db, destruction_id, current_user.id, witness_number
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.post("/destructions/{destruction_id}/complete")
def complete_destruction(
    destruction_id: int,
    evidence_file: Optional[str] = None,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="权限不足")
    success, message, record = AppraisalService.complete_destruction(
        db, destruction_id, evidence_file, remarks
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.get("/destructions", response_model=List[DestructionRecordResponse])
def list_destructions(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.notification import DestructionRecord
    query = db.query(DestructionRecord)
    if status:
        query = query.filter(DestructionRecord.status == status)
    return query.order_by(DestructionRecord.created_at.desc()).all()
