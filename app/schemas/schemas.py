from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date


class UserBase(BaseModel):
    username: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    role: str = "user"
    permission_level: int = 1


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class ArchiveCategoryBase(BaseModel):
    code: str
    name: str
    parent_id: Optional[int] = None
    description: Optional[str] = None
    retention_period: int = 30


class ArchiveCategoryCreate(ArchiveCategoryBase):
    pass


class ArchiveCategoryResponse(ArchiveCategoryBase):
    id: int

    class Config:
        from_attributes = True


class StorageZoneBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    temperature_min: float = 14.0
    temperature_max: float = 24.0
    humidity_min: float = 40.0
    humidity_max: float = 60.0


class StorageZoneCreate(StorageZoneBase):
    pass


class StorageZoneResponse(StorageZoneBase):
    id: int

    class Config:
        from_attributes = True


class StorageCabinetBase(BaseModel):
    code: str
    name: str
    location: str
    zone_id: int
    carrier_type: Optional[str] = None
    temperature_min: float = 14.0
    temperature_max: float = 24.0
    humidity_min: float = 40.0
    humidity_max: float = 60.0
    total_slots: int = 100


class StorageCabinetCreate(StorageCabinetBase):
    pass


class StorageCabinetResponse(StorageCabinetBase):
    id: int
    used_slots: int
    is_active: bool

    class Config:
        from_attributes = True


class ArchiveBase(BaseModel):
    title: str
    category_id: Optional[int] = None
    fonds_code: Optional[str] = None
    carrier_type: str
    security_level: int = 1
    total_pages: int = 0
    scanned_pages: int = 0
    creation_date: Optional[date] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    retention_period: int = 30


class ArchiveCreate(ArchiveBase):
    pass


class ScanValidationRequest(BaseModel):
    archive_id: int
    total_pages: int
    scanned_pages: int
    scanned_page_numbers: List[int]


class ScanValidationResponse(BaseModel):
    is_complete: bool
    missing_pages: List[int]
    missing_count: int
    requires_rescan: bool


class ArchiveResponse(ArchiveBase):
    id: int
    archive_index: str
    missing_pages: Optional[str] = None
    is_digitized: bool
    digitization_quality: float
    metadata_complete: bool
    storage_start_date: Optional[date] = None
    last_access_date: Optional[date] = None
    cabinet_id: Optional[int] = None
    cabinet_slot: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ArchiveListResponse(BaseModel):
    total: int
    items: List[ArchiveResponse]


class BorrowRecordBase(BaseModel):
    archive_id: int
    borrow_type: str = "physical"
    purpose: Optional[str] = None
    scheduled_outbound_time: datetime
    scheduled_return_date: date


class BorrowRecordCreate(BorrowRecordBase):
    pass


class BorrowRecordResponse(BorrowRecordBase):
    id: int
    record_no: str
    user_id: int
    borrow_date: datetime
    actual_return_date: Optional[date] = None
    status: str
    approval_status: str
    overdue_days: int
    fine_amount: float
    created_at: datetime

    class Config:
        from_attributes = True


class BorrowApprovalRequest(BaseModel):
    record_id: int
    approve: bool
    rejection_reason: Optional[str] = None


class OutboundTaskBase(BaseModel):
    borrow_record_id: int
    archive_id: int
    scheduled_time: datetime


class OutboundTaskCreate(OutboundTaskBase):
    pass


class OutboundTaskResponse(OutboundTaskBase):
    id: int
    task_no: str
    admin_user_id: Optional[int] = None
    completed_time: Optional[datetime] = None
    status: str
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


class FineResponse(BaseModel):
    id: int
    borrow_record_id: int
    user_id: int
    overdue_days: int
    tier: int
    daily_rate: float
    total_amount: float
    paid_amount: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class DigitalTaskBase(BaseModel):
    archive_id: int
    batch_no: Optional[str] = None
    task_type: str = "scan"
    priority: int = 2
    total_pages: int = 0
    deadline: Optional[datetime] = None


class DigitalTaskCreate(DigitalTaskBase):
    pass


class DigitalTaskResponse(DigitalTaskBase):
    id: int
    task_no: str
    assigned_user_id: Optional[int] = None
    progress: int
    completed_pages: int
    image_clarity_score: float
    metadata_complete_score: float
    quality_check_pass: Optional[bool] = None
    consecutive_fail_count: int
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class QualityCheckRequest(BaseModel):
    task_id: int
    image_clarity_score: float
    metadata_complete_score: float
    is_passed: bool
    rejection_reason: Optional[str] = None


class SensorBase(BaseModel):
    code: str
    name: str
    sensor_type: str
    zone_id: Optional[int] = None
    location: Optional[str] = None


class SensorCreate(SensorBase):
    pass


class SensorResponse(SensorBase):
    id: int
    is_online: bool

    class Config:
        from_attributes = True


class SensorReadingCreate(BaseModel):
    sensor_id: int
    temperature: Optional[float] = None
    humidity: Optional[float] = None


class SensorReadingResponse(BaseModel):
    id: int
    sensor_id: int
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    reading_time: datetime
    is_warning: bool

    class Config:
        from_attributes = True


class WorkOrderResponse(BaseModel):
    id: int
    order_no: str
    order_type: str
    zone_id: Optional[int] = None
    sensor_id: Optional[int] = None
    assigned_user_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    priority: int
    status: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    ac_status: str
    dehumidifier_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    content: str
    notification_type: str
    related_id: Optional[int] = None
    related_type: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AppraisalRecordBase(BaseModel):
    archive_id: int
    appraisal_type: str = "periodic"
    reason: Optional[str] = None
    proposed_action: Optional[str] = None


class AppraisalRecordCreate(AppraisalRecordBase):
    pass


class AppraisalRecordResponse(AppraisalRecordBase):
    id: int
    record_no: str
    expert_signatures: Optional[str] = None
    final_decision: Optional[str] = None
    decision_date: Optional[date] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class DestructionRecordBase(BaseModel):
    appraisal_id: int
    archive_id: int
    destruction_method: Optional[str] = None


class DestructionCreate(DestructionRecordBase):
    pass


class DestructionRecordResponse(DestructionRecordBase):
    id: int
    record_no: str
    witness_1_id: Optional[int] = None
    witness_2_id: Optional[int] = None
    witness_1_signature: bool
    witness_2_signature: bool
    destruction_date: Optional[datetime] = None
    evidence_file: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MonthlyReportResponse(BaseModel):
    id: int
    report_month: str
    zone_code: str
    new_archives_count: int
    borrow_count: int
    digitization_count: int
    digitization_rate: float
    temp_warning_count: int
    humidity_warning_count: int
    total_warning_count: int
    generated_at: datetime

    class Config:
        from_attributes = True


class ReportQuery(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    zone_code: Optional[str] = None
    fonds_code: Optional[str] = None
