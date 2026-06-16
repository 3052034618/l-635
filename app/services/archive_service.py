from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.archive import Archive, DigitalAsset
from app.models.archive_category import ArchiveCategory
from app.models.storage import StorageCabinet, StorageZone
from app.models.user import User
from app.utils.helpers import generate_archive_index
from app.services.notification_service import NotificationService


class ArchiveService:
    @staticmethod
    def auto_classify(db: Session, title: str, description: str = "", keywords: str = "") -> Optional[ArchiveCategory]:
        categories = db.query(ArchiveCategory).filter(ArchiveCategory.parent_id != None).all()
        if not categories:
            return db.query(ArchiveCategory).first()
        
        title_lower = title.lower()
        desc_lower = (description or "").lower()
        keywords_lower = (keywords or "").lower()
        combined = f"{title_lower} {desc_lower} {keywords_lower}"
        
        best_category = None
        max_matches = 0
        for cat in categories:
            cat_name_lower = cat.name.lower()
            matches = sum(1 for word in cat_name_lower.split() if word in combined)
            if matches > max_matches:
                max_matches = matches
                best_category = cat
        
        return best_category or categories[0]

    @staticmethod
    def generate_unique_index(db: Session, category_id: int, fonds_code: str, year: int) -> str:
        category = db.query(ArchiveCategory).filter(ArchiveCategory.id == category_id).first()
        category_code = category.code if category else "GEN"
        
        existing_count = db.query(Archive).filter(
            Archive.fonds_code == fonds_code
        ).count()
        
        sequence = existing_count + 1
        archive_index = generate_archive_index(category_code, fonds_code, year, sequence)
        
        while db.query(Archive).filter(Archive.archive_index == archive_index).first():
            sequence += 1
            archive_index = generate_archive_index(category_code, fonds_code, year, sequence)
        
        return archive_index

    @staticmethod
    def match_storage_cabinet(
        db: Session,
        carrier_type: str,
        temperature_min: float = 14.0,
        temperature_max: float = 24.0,
        humidity_min: float = 40.0,
        humidity_max: float = 60.0
    ) -> Optional[StorageCabinet]:
        cabinets = db.query(StorageCabinet).filter(
            StorageCabinet.is_active == True,
            StorageCabinet.used_slots < StorageCabinet.total_slots
        ).all()
        
        scored_cabinets = []
        for cabinet in cabinets:
            score = 0
            
            if cabinet.carrier_type and cabinet.carrier_type.lower() == carrier_type.lower():
                score += 50
            
            if cabinet.temperature_min <= temperature_min + 2 and cabinet.temperature_max >= temperature_max - 2:
                score += 30
            
            if cabinet.humidity_min <= humidity_min + 5 and cabinet.humidity_max >= humidity_max - 5:
                score += 20
            
            availability_ratio = 1 - (cabinet.used_slots / cabinet.total_slots)
            score += availability_ratio * 10
            
            if score > 0:
                scored_cabinets.append((score, cabinet))
        
        scored_cabinets.sort(key=lambda x: x[0], reverse=True)
        return scored_cabinets[0][1] if scored_cabinets else None

    @staticmethod
    def assign_cabinet_slot(cabinet: StorageCabinet) -> str:
        used_slots = cabinet.used_slots
        return f"{cabinet.code}-{str(used_slots + 1).zfill(4)}"

    @staticmethod
    def validate_scan_completeness(
        total_pages: int,
        scanned_pages: int,
        scanned_page_numbers: List[int]
    ) -> Tuple[bool, List[int]]:
        expected_pages = set(range(1, total_pages + 1))
        actual_pages = set(scanned_page_numbers)
        missing_pages = sorted(list(expected_pages - actual_pages))
        is_complete = len(missing_pages) == 0 and scanned_pages >= total_pages
        return is_complete, missing_pages

    @staticmethod
    def create_archive(db: Session, archive_data: dict, user_id: int) -> Archive:
        if not archive_data.get("category_id"):
            category = ArchiveService.auto_classify(
                db,
                archive_data.get("title", ""),
                archive_data.get("description", ""),
                archive_data.get("keywords", "")
            )
            if category:
                archive_data["category_id"] = category.id
        
        year = datetime.now().year
        fonds_code = archive_data.get("fonds_code") or "FONDS001"
        archive_index = ArchiveService.generate_unique_index(
            db, archive_data.get("category_id", 1), fonds_code, year
        )
        
        cabinet = ArchiveService.match_storage_cabinet(
            db,
            archive_data.get("carrier_type", "paper")
        )
        
        archive_data["archive_index"] = archive_index
        archive_data["created_by"] = user_id
        
        if cabinet:
            archive_data["cabinet_id"] = cabinet.id
            archive_data["cabinet_slot"] = ArchiveService.assign_cabinet_slot(cabinet)
            cabinet.used_slots += 1
        
        archive = Archive(**archive_data)
        db.add(archive)
        db.commit()
        db.refresh(archive)
        
        NotificationService.notify_archive_admins(
            db,
            f"新档案入库: {archive.title}",
            f"档案索引号: {archive.archive_index}, 柜位: {archive.cabinet_slot or '未分配'}",
            related_id=archive.id,
            related_type="archive"
        )
        
        return archive

    @staticmethod
    def update_scan_status(
        db: Session,
        archive_id: int,
        total_pages: int,
        scanned_pages: int,
        scanned_page_numbers: List[int]
    ) -> dict:
        archive = db.query(Archive).filter(Archive.id == archive_id).first()
        if not archive:
            return {"success": False, "message": "档案不存在"}
        
        is_complete, missing_pages = ArchiveService.validate_scan_completeness(
            total_pages, scanned_pages, scanned_page_numbers
        )
        
        archive.total_pages = total_pages
        archive.scanned_pages = scanned_pages
        archive.missing_pages = ",".join(map(str, missing_pages)) if missing_pages else None
        
        if is_complete:
            archive.is_digitized = True
        else:
            archive.is_digitized = False
            NotificationService.notify_archive_admins(
                db,
                f"档案扫描不完整: {archive.title}",
                f"缺失页码: {missing_pages}, 请补扫缺失页面",
                related_id=archive.id,
                related_type="archive"
            )
        
        db.commit()
        db.refresh(archive)
        
        return {
            "success": True,
            "is_complete": is_complete,
            "missing_pages": missing_pages,
            "requires_rescan": not is_complete,
            "archive": archive
        }

    @staticmethod
    def get_archive(db: Session, archive_id: int) -> Optional[Archive]:
        return db.query(Archive).filter(Archive.id == archive_id).first()

    @staticmethod
    def list_archives(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        category_id: Optional[int] = None,
        is_digitized: Optional[bool] = None,
        keyword: Optional[str] = None
    ) -> Tuple[int, List[Archive]]:
        query = db.query(Archive)
        
        if status:
            query = query.filter(Archive.status == status)
        if category_id:
            query = query.filter(Archive.category_id == category_id)
        if is_digitized is not None:
            query = query.filter(Archive.is_digitized == is_digitized)
        if keyword:
            query = query.filter(
                Archive.title.contains(keyword) |
                Archive.archive_index.contains(keyword) |
                Archive.keywords.contains(keyword)
            )
        
        total = query.count()
        items = query.order_by(Archive.created_at.desc()).offset(skip).limit(limit).all()
        return total, items
