from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas.schemas import NotificationResponse
from app.models.user import User
from app.services.notification_service import NotificationService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["通知管理"])


@router.get("/", response_model=List[NotificationResponse])
def get_my_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return NotificationService.get_user_notifications(db, current_user.id, unread_only)


@router.post("/{notification_id}/read")
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notification = NotificationService.mark_as_read(db, notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"success": True, "message": "已标记为已读"}


@router.post("/read-all")
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    count = NotificationService.mark_all_as_read(db, current_user.id)
    return {"success": True, "marked_count": count}
