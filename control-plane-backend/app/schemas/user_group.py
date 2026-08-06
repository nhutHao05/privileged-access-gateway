from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID  # <-- BỔ SUNG DÒNG NÀY LÊN ĐẦU FILE

# --- USER SCHEMAS ---
class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    keycloak_sub: Optional[UUID] = None

class UserResponse(UserCreate):
    id: UUID
    is_active: bool = True
    synced_at: Optional[datetime] = Field(default=None, alias="created_at")

    class Config:
        from_attributes = True
        populate_by_name = True

# --- GROUP SCHEMAS ---
class UserBrief(BaseModel):
    id: UUID
    username: str
    email: Optional[str] = None
    class Config:
        from_attributes = True

class GroupCreate(BaseModel):
    keycloak_group_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None

class GroupResponse(GroupCreate):
    id: UUID
    users: List[UserBrief] = []

    class Config:
        from_attributes = True
