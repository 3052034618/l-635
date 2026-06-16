from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.utils.websocket_manager import manager

from app.api.auth_routes import router as auth_router
from app.api.archive_routes import router as archive_router
from app.api.borrow_routes import router as borrow_router
from app.api.digital_routes import router as digital_router
from app.api.monitoring_routes import router as monitoring_router
from app.api.appraisal_routes import router as appraisal_router
from app.api.report_routes import router as report_router
from app.api.notification_routes import router as notification_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="智慧档案馆档案数字化管理与借阅调度系统后端API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(archive_router, prefix="/api")
app.include_router(borrow_router, prefix="/api")
app.include_router(digital_router, prefix="/api")
app.include_router(monitoring_router, prefix="/api")
app.include_router(appraisal_router, prefix="/api")
app.include_router(report_router, prefix="/api")
app.include_router(notification_router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = ".".join(str(l) for l in err.get("loc", []))
        ctx = err.get("ctx", {})
        if ctx and "error" in ctx:
            detail = str(ctx["error"])
        else:
            detail = err.get("msg", "")
        input_val = err.get("input", "")
        errors.append({"field": loc, "detail": detail, "input": str(input_val)[:100]})
    return JSONResponse(status_code=422, content={"success": False, "detail": "请求参数校验失败", "errors": errors})


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"success": False, "detail": str(exc)}
    )


@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.websocket("/ws/notifications/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(user_id, {
                "type": "echo",
                "message": data,
                "timestamp": datetime.utcnow().isoformat()
            })
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)


scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def scheduled_tasks():
    from app.services.borrow_service import BorrowService
    from app.services.report_service import ReportService
    from datetime import date
    
    db = SessionLocal()
    try:
        BorrowService.check_overdue_and_send_reminders(db)
        
        today = date.today()
        if today.day == 1:
            ReportService.generate_monthly_report(db)
    finally:
        db.close()


scheduler.add_job(scheduled_tasks, "cron", hour=8, minute=0, id="daily_tasks")
scheduler.start()


@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()


def init_db_data():
    from app.models.user import User
    from app.models.archive_category import ArchiveCategory
    from app.models.storage import StorageZone, StorageCabinet
    from app.utils.auth import hash_password
    
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                full_name="系统管理员",
                email="admin@archive.com",
                role="admin",
                permission_level=5
            )
            db.add(admin)
        
        if not db.query(User).filter(User.username == "archivist").first():
            archivist = User(
                username="archivist",
                password_hash=hash_password("archivist123"),
                full_name="档案管理员",
                email="archivist@archive.com",
                role="archivist",
                permission_level=4
            )
            db.add(archivist)
        
        if not db.query(User).filter(User.username == "user").first():
            user = User(
                username="user",
                password_hash=hash_password("user123"),
                full_name="普通用户",
                email="user@archive.com",
                role="user",
                permission_level=1
            )
            db.add(user)
        
        if not db.query(User).filter(User.username == "digitizer").first():
            digitizer = User(
                username="digitizer",
                password_hash=hash_password("digitizer123"),
                full_name="数字化专员",
                email="digitizer@archive.com",
                role="digitizer",
                permission_level=2
            )
            db.add(digitizer)
        
        if not db.query(User).filter(User.username == "maintenance").first():
            maintenance = User(
                username="maintenance",
                password_hash=hash_password("maintenance123"),
                full_name="维护人员",
                email="maintenance@archive.com",
                role="maintenance",
                permission_level=2
            )
            db.add(maintenance)
        
        if not db.query(ArchiveCategory).first():
            categories = [
                ArchiveCategory(code="DOC", name="文书档案", retention_period=30),
                ArchiveCategory(code="SCI", name="科技档案", retention_period=30),
                ArchiveCategory(code="FIN", name="会计档案", retention_period=15),
                ArchiveCategory(code="PER", name="人事档案", retention_period=50),
                ArchiveCategory(code="SPE", name="特殊载体档案", retention_period=30),
            ]
            db.add_all(categories)
        
        if not db.query(StorageZone).first():
            zone1 = StorageZone(
                code="ZONE-A", name="A库区-纸质档案库",
                temperature_min=14.0, temperature_max=24.0,
                humidity_min=45.0, humidity_max=55.0,
                description="常规纸质档案存放区"
            )
            zone2 = StorageZone(
                code="ZONE-B", name="B库区-特殊载体库",
                temperature_min=15.0, temperature_max=20.0,
                humidity_min=40.0, humidity_max=50.0,
                description="照片、胶片、磁带等特殊载体存放区"
            )
            zone3 = StorageZone(
                code="ZONE-C", name="C库区-密集档案库",
                temperature_min=14.0, temperature_max=24.0,
                humidity_min=40.0, humidity_max=60.0,
                description="长期保管档案存放区"
            )
            db.add_all([zone1, zone2, zone3])
            db.commit()
            
            if not db.query(StorageCabinet).first():
                cabinets = []
                for i in range(1, 11):
                    cabinets.append(StorageCabinet(
                        code=f"A-{str(i).zfill(3)}",
                        name=f"A区第{i}号柜",
                        location=f"A区第{i}排",
                        zone_id=zone1.id,
                        carrier_type="paper",
                        total_slots=100
                    ))
                for i in range(1, 6):
                    cabinets.append(StorageCabinet(
                        code=f"B-{str(i).zfill(3)}",
                        name=f"B区第{i}号柜",
                        location=f"B区第{i}排",
                        zone_id=zone2.id,
                        carrier_type="special",
                        temperature_min=15.0, temperature_max=20.0,
                        humidity_min=40.0, humidity_max=50.0,
                        total_slots=80
                    ))
                for i in range(1, 11):
                    cabinets.append(StorageCabinet(
                        code=f"C-{str(i).zfill(3)}",
                        name=f"C区第{i}号柜",
                        location=f"C区第{i}排",
                        zone_id=zone3.id,
                        carrier_type="paper",
                        total_slots=200
                    ))
                db.add_all(cabinets)
        
        db.commit()
    finally:
        db.close()


init_db_data()
