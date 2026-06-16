from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.schemas.schemas import (
    ArchiveCreate, ArchiveResponse, ArchiveListResponse,
    ScanValidationRequest, ScanValidationResponse,
    ArchiveCategoryCreate, ArchiveCategoryResponse,
    StorageZoneCreate, StorageZoneResponse,
    StorageCabinetCreate, StorageCabinetResponse
)
from app.models.user import User
from app.services.archive_service import ArchiveService
from app.models.archive_category import ArchiveCategory
from app.models.storage import StorageZone, StorageCabinet
from app.utils.auth import get_current_user

router = APIRouter(prefix="/archives", tags=["档案管理"])


@router.post("/", response_model=ArchiveResponse)
def create_archive(
    archive_data: ArchiveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    archive = ArchiveService.create_archive(db, archive_data.model_dump(), current_user.id)
    return archive


@router.post("/validate-scan", response_model=ScanValidationResponse)
def validate_scan(
    request: ScanValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = ArchiveService.update_scan_status(
        db,
        request.archive_id,
        request.total_pages,
        request.scanned_pages,
        request.scanned_page_numbers
    )
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return ScanValidationResponse(
        is_complete=result["is_complete"],
        missing_pages=result["missing_pages"],
        missing_count=len(result["missing_pages"]),
        requires_rescan=result["requires_rescan"]
    )


@router.get("/", response_model=ArchiveListResponse)
def list_archives(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = None,
    category_id: Optional[int] = None,
    is_digitized: Optional[bool] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    total, items = ArchiveService.list_archives(db, skip, limit, status, category_id, is_digitized, keyword)
    return ArchiveListResponse(total=total, items=items)


@router.get("/{archive_id}", response_model=ArchiveResponse)
def get_archive(
    archive_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    archive = ArchiveService.get_archive(db, archive_id)
    if not archive:
        raise HTTPException(status_code=404, detail="档案不存在")
    return archive


@router.post("/categories", response_model=ArchiveCategoryResponse)
def create_category(
    category_data: ArchiveCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    category = ArchiveCategory(**category_data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/categories", response_model=list[ArchiveCategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(ArchiveCategory).all()


@router.post("/zones", response_model=StorageZoneResponse)
def create_zone(
    zone_data: StorageZoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    zone = StorageZone(**zone_data.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.get("/zones", response_model=list[StorageZoneResponse])
def list_zones(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(StorageZone).all()


@router.post("/cabinets", response_model=StorageCabinetResponse)
def create_cabinet(
    cabinet_data: StorageCabinetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cabinet = StorageCabinet(**cabinet_data.model_dump())
    db.add(cabinet)
    db.commit()
    db.refresh(cabinet)
    return cabinet


@router.get("/cabinets", response_model=list[StorageCabinetResponse])
def list_cabinets(
    zone_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(StorageCabinet)
    if zone_id:
        query = query.filter(StorageCabinet.zone_id == zone_id)
    return query.all()
