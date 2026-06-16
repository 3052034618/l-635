from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.schemas.schemas import (
    DigitalTaskCreate, DigitalTaskResponse,
    QualityCheckRequest
)
from app.models.digital import TrainingWorkOrder
from app.models.user import User
from app.services.digital_service import DigitalService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/digital", tags=["数字化加工"])


@router.post("/tasks", response_model=DigitalTaskResponse)
def create_digital_task(
    task_data: DigitalTaskCreate,
    auto_assign: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    return DigitalService.create_digital_task(db, task_data.model_dump(), auto_assign)


@router.get("/tasks", response_model=List[DigitalTaskResponse])
def list_digital_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = None,
    assigned_user_id: Optional[int] = None,
    batch_no: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _, items = DigitalService.list_tasks(db, skip, limit, status, assigned_user_id, batch_no)
    return items


@router.get("/tasks/my", response_model=List[DigitalTaskResponse])
def get_my_tasks(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _, items = DigitalService.list_tasks(db, 0, 100, status, current_user.id)
    return items


@router.post("/tasks/{task_id}/start", response_model=DigitalTaskResponse)
def start_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success, message, task = DigitalService.start_task(db, task_id, current_user.id)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return task


@router.post("/tasks/{task_id}/progress", response_model=DigitalTaskResponse)
def update_task_progress(
    task_id: int,
    completed_pages: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success, message, task = DigitalService.update_progress(db, task_id, completed_pages)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return task


@router.post("/tasks/{task_id}/submit")
def submit_for_quality_check(
    task_id: int,
    image_clarity_score: float,
    metadata_complete_score: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success, message, task = DigitalService.submit_for_quality_check(
        db, task_id, image_clarity_score, metadata_complete_score
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "task": task}


@router.post("/quality-check")
def perform_quality_check(
    check_data: QualityCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
    success, message, task = DigitalService.quality_check(
        db,
        check_data.task_id,
        current_user.id,
        check_data.image_clarity_score,
        check_data.metadata_complete_score,
        check_data.is_passed,
        check_data.rejection_reason
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "task": task}


@router.post("/tasks/{task_id}/reassign", response_model=DigitalTaskResponse)
def reassign_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
    success, message, task = DigitalService.reassign_task(db, task_id)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return task


@router.get("/training-work-orders")
def list_training_work_orders(
    batch_no: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    query = db.query(TrainingWorkOrder)
    if batch_no:
        query = query.filter(TrainingWorkOrder.batch_no == batch_no)
    if status:
        query = query.filter(TrainingWorkOrder.status == status)
    orders = query.order_by(TrainingWorkOrder.created_at.desc()).all()
    return [
        {
            "id": o.id,
            "order_no": o.order_no,
            "user_id": o.user_id,
            "batch_no": o.batch_no,
            "fail_count": o.fail_count,
            "reason": o.reason,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None
        }
        for o in orders
    ]
