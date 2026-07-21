from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

# Schema gán User vào Group
class UserGroupAssign(BaseModel):
    user_id: UUID
    group_id: UUID

# Schema tạo Policy kết nối Group với Server
class GroupServerPolicyCreate(BaseModel):
    group_id: UUID
    server_id: UUID

class GroupServerPolicyResponse(GroupServerPolicyCreate):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True