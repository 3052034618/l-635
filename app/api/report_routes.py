from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date

from app.database import get_db
from app.schemas.schemas import MonthlyReportResponse, ReportQuery
from app.models.user import User
from app.services.report_service import ReportService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/reports", tags=["运营报告"])


@router.post("/generate-monthly")
def generate_monthly_report(
    report_month: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    reports = ReportService.generate_monthly_report(db, report_month)
    return {"success": True, "count": len(reports), "reports": reports}


@router.get("/monthly", response_model=List[MonthlyReportResponse])
def get_monthly_reports(
    report_month: Optional[str] = None,
    zone_code: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return ReportService.get_monthly_reports(db, report_month, zone_code)


@router.post("/export")
def export_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    zone_code: Optional[str] = None,
    fonds_code: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "archivist"]:
        raise HTTPException(status_code=403, detail="权限不足")
    
    output = ReportService.export_report_to_excel(db, start_date, end_date, zone_code, fonds_code)
    
    filename = f"archive_report_{date.today()}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
