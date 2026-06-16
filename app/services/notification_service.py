from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User


class NotificationService:
    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        title: str,
        content: str,
        notification_type: str,
        related_id: Optional[int] = None,
        related_type: Optional[str] = None
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            title=title,
            content=content,
            notification_type=notification_type,
            related_id=related_id,
            related_type=related_type
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def get_user_notifications(db: Session, user_id: int, unread_only: bool = False) -> List[Notification]:
        query = db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.is_read == False)
        return query.order_by(Notification.created_at.desc()).all()

    @staticmethod
    def mark_as_read(db: Session, notification_id: int, user_id: int) -> Optional[Notification]:
        notification = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        if notification:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            db.commit()
            db.refresh(notification)
        return notification

    @staticmethod
    def mark_all_as_read(db: Session, user_id: int) -> int:
        count = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).update({Notification.is_read: True, Notification.read_at: datetime.utcnow()})
        db.commit()
        return count

    @staticmethod
    def broadcast_to_roles(db: Session, roles: List[str], title: str, content: str, notification_type: str, **kwargs):
        users = db.query(User).filter(User.role.in_(roles), User.is_active == True).all()
        notifications = []
        for user in users:
            notifications.append(NotificationService.create_notification(
                db, user.id, title, content, notification_type, **kwargs
            ))
        return notifications

    @staticmethod
    def notify_archive_admins(db: Session, title: str, content: str, **kwargs):
        return NotificationService.broadcast_to_roles(
            db, ["admin", "archivist"], title, content, "archive", **kwargs
        )
