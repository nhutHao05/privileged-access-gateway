from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

# Schema gửi yêu cầu xin truy cập
class AccessRequestCreate(BaseModel):
    user_id: Optional[UUID] = None  # Nếu không truyền, tự động lấy từ Keycloak Token
    group_id: Optional[UUID] = None  # Nhóm của user / nhóm xin quyền từ UI Nghĩa
    server_id: UUID
    reason: str
    requested_minutes: int = Field(default=60, ge=1, le=480, description="Số phút cần truy cập")

# Schema trả về thông tin Yêu cầu
class AccessRequestResponse(BaseModel):
    id: UUID
    user_id: UUID
    server_id: UUID
    reason: str
    requested_minutes: int
    status: str
    requested_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schema duyệt/từ chối Yêu cầu
class AccessRequestReview(BaseModel):
    status: str

# Schema trả về Quyền đang hoạt động (Active Grant)
class ActiveGrantResponse(BaseModel):
    id: UUID
    request_id: UUID
    user_id: UUID
    server_id: UUID
    granted_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True