from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class WhitelistAdd(BaseModel):
    user_id: UUID


class WhitelistUserResponse(BaseModel):
    id: UUID
    username: str
    email: Optional[str] = None

    class Config:
        from_attributes = True


class WhitelistEntryResponse(BaseModel):
    id: UUID
    server_id: UUID
    user_id: UUID
    user: WhitelistUserResponse
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
