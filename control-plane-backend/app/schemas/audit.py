from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class SessionLogResponse(BaseModel):
    id: UUID
    request_id: Optional[UUID] = None
    user_id: UUID
    server_id: UUID
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str
    recording_file: Optional[str] = None
    recording_url: Optional[str] = None
    recording_hash: Optional[str] = None

    class Config:
        from_attributes = True

class SessionLogUpdateRecording(BaseModel):
    recording_file: str
    recording_url: str
    recording_hash: str  # Mã SHA-256 hash chống sửa đổi log

class AuditLogCreate(BaseModel):
    user_id: Optional[UUID] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    details: Optional[str] = None

class AuditLogResponse(AuditLogCreate):
    id: UUID
    timestamp: datetime

    class Config:
        from_attributes = True
