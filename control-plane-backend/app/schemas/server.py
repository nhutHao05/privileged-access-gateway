from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

class ServerBase(BaseModel):
    name: str
    ip: str
    port: int
    protocol: str  # rdp | ssh | vnc
    guacamole_connection_id: str

class ServerCreate(ServerBase):
    tags: Optional[List[str]] = None

class ServerUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    guacamole_connection_id: Optional[str] = None
    tags: Optional[List[str]] = None

class ServerResponse(ServerBase):
    id: UUID
    tags: Optional[List[str]] = None

    class Config:
        from_attributes = True