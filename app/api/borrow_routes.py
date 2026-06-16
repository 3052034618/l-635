from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.schemas.schemas import (
    BorrowRecordCreate, BorrowRecordResponse,
    BorrowApprovalRequest,
    OutboundTaskResponse,
    FineResponse
)
from app.models.user import User
from app.services.borrow_service import BorrowService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/borrow", tags=["借阅管理"])


@router.post("/request", response_model=BorrowRecordResponse)
def create_borrow_request(
    borrow_data: BorrowRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success, message, record = BorrowService.create_borrow_record(
        db, current_user.id, borrow_data.model_dump()
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return record


@router.post("/approve")
def approve_borrow_request(
    approval_data: BorrowApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足，只有管理员可以审批")
    
    success, message, record = BorrowService.approve_borrow(
        db,
        approval_data.record_id,
        approval_data.approve,
        current_user.id,
        approval_data.rejection_reason
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "record": record}


@router.get("/my", response_model=List[BorrowRecordResponse])
def get_my_borrow_records(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return BorrowService.get_user_borrow_records(db, current_user.id, status)


@router.get("/pending-approvals", response_model=List[BorrowRecordResponse])
def get_pending_approvals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    return BorrowService.get_pending_approvals(db)


@router.get("/outbound-tasks", response_model=List[OutboundTaskResponse])
def get_outbound_tasks(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.borrow import OutboundTask
    query = db.query(OutboundTask)
    if status:
        query = query.filter(OutboundTask.status == status)
    return query.order_by(OutboundTask.created_at.desc()).all()


@router.post("/outbound/{task_id}/complete")
def complete_outbound_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    success, message = BorrowService.complete_outbound(db, task_id, current_user.id)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.post("/return/{record_id}")
def return_archive(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    success, message = BorrowService.return_archive(db, record_id)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.get("/fines", response_model=List[FineResponse])
def get_user_fines(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.borrow import Fine
    query = db.query(Fine).filter(Fine.user_id == current_user.id)
    if status:
        query = query.filter(Fine.status == status)
    return query.order_by(Fine.created_at.desc()).all()


@router.post("/fines/{fine_id}/pay")
def pay_fine(
    fine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.borrow import Fine
    fine = db.query(Fine).filter(Fine.id == fine_id, Fine.user_id == current_user.id).first()
    if not fine:
        raise HTTPException(status_code=404, detail="罚款记录不存在")
    if fine.status == "paid":
        raise HTTPException(status_code=400, detail="该罚款已缴纳")
    
    fine.status = "paid"
    fine.paid_amount = fine.total_amount
    fine.payment_time = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "罚款缴纳成功"}


@router.post("/check-overdue")
def trigger_overdue_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    records = BorrowService.check_overdue_and_send_reminders(db)
    return {"success": True, "processed_count": len(records)}
