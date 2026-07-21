from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID  # <-- BỔ SUNG DÒNG NÀY LÊN ĐẦU FILE

# --- USER SCHEMAS ---
class UserCreate(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None

class UserResponse(UserCreate):
    id: UUID
    is_active: bool = True
    synced_at: Optional[datetime] = Field(default=None, alias="created_at")

    class Config:
        from_attributes = True
        populate_by_name = True

# --- GROUP SCHEMAS ---
class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None

class GroupResponse(GroupCreate):
    id: UUID
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True