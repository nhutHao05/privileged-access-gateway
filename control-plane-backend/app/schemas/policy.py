from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

# Schema nhận dữ liệu từ Frontend gửi lên (POST body)
class GroupServerPolicyCreate(BaseModel):
    group_id: UUID
    server_id: UUID
    max_duration_minutes: int = 60
    require_approval: bool = True

# Schema trả dữ liệu về lại cho Frontend (Response body)
class GroupServerPolicyResponse(GroupServerPolicyCreate):
    id: UUID
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True