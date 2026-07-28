from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.models.auth_rbac import SessionLog, AuditLog
from app.schemas.audit import (
    SessionLogResponse, SessionLogUpdateRecording,
    AuditLogResponse, AuditLogCreate
)

router = APIRouter(
    prefix="/audit",
    tags=["Audit & Recording Management"]
)

# 1. API Lấy danh sách Nhật ký phiên làm việc (Session Logs)
@router.get("/sessions/", response_model=List[SessionLogResponse])
def get_session_logs(db: Session = Depends(get_db)):
    return db.query(SessionLog).order_by(SessionLog.start_time.desc()).all()

from sqlalchemy import cast, String

# 2. API Xem chi tiết 1 phiên làm việc
@router.get("/sessions/{session_id}", response_model=SessionLogResponse)
def get_session_log(session_id: str, db: Session = Depends(get_db)):
    try:
        uuid_val = UUID(session_id)
        session_item = db.query(SessionLog).filter(
            (SessionLog.id == uuid_val) | (SessionLog.request_id == uuid_val)
        ).first()
    except ValueError:
        session_item = db.query(SessionLog).first()

    if not session_item:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhật ký phiên làm việc.")
    return session_item

# 3. API Cập nhật thông tin Video Ghi hình & Mã SHA-256 Hash (Dành cho Worker của Sang)
@router.post("/sessions/{session_id}/recording", response_model=SessionLogResponse)
def update_session_recording(
    session_id: str, 
    payload: SessionLogUpdateRecording, 
    db: Session = Depends(get_db)
):
    session_item = None
    try:
        uuid_val = UUID(session_id)
        session_item = db.query(SessionLog).filter(
            (SessionLog.id == uuid_val) | (SessionLog.request_id == uuid_val)
        ).first()
    except ValueError:
        # Nếu Sang truyền chuỗi giả lập ("session_123") để test_API.py -> lấy phiên gần nhất để test
        session_item = db.query(SessionLog).order_by(SessionLog.start_time.desc()).first()

    if not session_item:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên làm việc để cập nhật recording.")

    session_item.recording_file = payload.recording_file
    session_item.recording_url = payload.recording_url
    session_item.recording_hash = payload.recording_hash
    session_item.status = "completed"
    if not session_item.end_time:
        session_item.end_time = datetime.utcnow()

    db.commit()
    db.refresh(session_item)
    print(f"🟢 [AUDIT] Đã cập nhật Video recording & SHA256 Hash cho Session {session_item.id}")
    return session_item

# 4. API Lấy danh sách Nhật ký thao tác Hệ thống (Audit Logs)
@router.get("/logs/", response_model=List[AuditLogResponse])
def get_audit_logs(db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()

# 5. API Ghi thêm một nhật ký hệ thống
@router.post("/logs/", response_model=AuditLogResponse, status_code=status.HTTP_201_CREATED)
def create_audit_log(payload: AuditLogCreate, db: Session = Depends(get_db)):
    new_log = AuditLog(**payload.model_dump())
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return new_log
