from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

# Schema gửi yêu cầu xin truy cập
class AccessRequestCreate(BaseModel):
    user_id: UUID
    server_id: UUID
    reason: str
    requested_minutes: int = 60

# Schema trả về thông tin Yêu cầu
class AccessRequestResponse(AccessRequestCreate):
    id: UUID
    status: str
    # Dùng requested_at từ Model DB và map sang created_at nếu client cần
    requested_at: Optional[datetime] = Field(default=None, alias="created_at")

    class Config:
        from_attributes = True
        populate_by_name = True

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