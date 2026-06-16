from typing import List, Optional, Set
from datetime import datetime
from sqlalchemy.orm import Session
import asyncio

from app.models.notification import Notification
from app.models.user import User

try:
    from app.utils.websocket_manager import manager
    WS_AVAILABLE = True
except Exception:
    WS_AVAILABLE = False


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(coro)
        else:
            loop.run_until_complete(coro)
    except Exception:
        try:
            new_loop = asyncio.new_event_loop()
            new_loop.run_until_complete(coro)
            new_loop.close()
        except Exception:
            pass


async def _push_to_user(user_id: int, message: dict):
    if not WS_AVAILABLE:
        return
    try:
        await manager.send_personal_message(user_id, message)
    except Exception:
        pass


async def _push_to_user_ids(user_ids: Set[int], message: dict):
    if not WS_AVAILABLE:
        return
    try:
        await manager.broadcast_to_roles(user_ids, message)
    except Exception:
        pass


def make_ws_message(
    notification_type: str,
    title: str,
    content: str,
    related_id: Optional[int] = None,
    related_type: Optional[str] = None,
    extra: Optional[dict] = None
) -> dict:
    msg = {
        "type": "notification",
        "notification_type": notification_type,
        "title": title,
        "content": content,
        "related_id": related_id,
        "related_type": related_type,
        "timestamp": datetime.utcnow().isoformat()
    }
    if extra:
        msg.update(extra)
    return msg


class NotificationService:
    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        title: str,
        content: str,
        notification_type: str,
        related_id: Optional[int] = None,
        related_type: Optional[str] = None,
        push_ws: bool = True
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
        
        if push_ws:
            ws_msg = make_ws_message(
                notification_type=notification_type,
                title=title,
                content=content,
                related_id=related_id,
                related_type=related_type,
                extra={"notification_id": notification.id, "is_read": False}
            )
            _run_async(_push_to_user(user_id, ws_msg))
        
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
    def broadcast_to_roles(
        db: Session,
        roles: List[str],
        title: str,
        content: str,
        notification_type: str,
        push_ws: bool = True,
        **kwargs
    ):
        users = db.query(User).filter(User.role.in_(roles), User.is_active == True).all()
        notifications = []
        user_ids: Set[int] = set()
        for user in users:
            notif = Notification(
                user_id=user.id,
                title=title,
                content=content,
                notification_type=notification_type,
                **{k: v for k, v in kwargs.items() if k in ["related_id", "related_type"]}
            )
            db.add(notif)
            notifications.append((user.id, notif))
            user_ids.add(user.id)
        db.commit()
        
        if push_ws and WS_AVAILABLE and notifications:
            for user_id, notif in notifications:
                db.refresh(notif)
            ws_msg = make_ws_message(
                notification_type=notification_type,
                title=title,
                content=content,
                related_id=kwargs.get("related_id"),
                related_type=kwargs.get("related_type")
            )
            ids_for_ws: Set[int] = set()
            for user_id, notif in notifications:
                ids_for_ws.add(user_id)
                msg_copy = dict(ws_msg)
                msg_copy["notification_id"] = notif.id
                msg_copy["is_read"] = False
            _run_async(_push_to_user_ids(ids_for_ws, ws_msg))
        
        return [n for _, n in notifications]

    @staticmethod
    def notify_archive_admins(
        db: Session,
        title: str,
        content: str,
        push_ws: bool = True,
        **kwargs
    ):
        return NotificationService.broadcast_to_roles(
            db, ["admin", "archivist"], title, content, "archive", push_ws=push_ws, **kwargs
        )
