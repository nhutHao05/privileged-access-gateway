from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

# Schema nhận dữ liệu từ Swagger UI
class ServerCreate(BaseModel):
    name: str
    host: str
    port: int = 22
    protocol: str = "ssh"  # rdp | ssh | vnc
    guacamole_connection_id: str
    tags: Optional[List[str]] = None

# Schema trả về dữ liệu cho Client
class ServerResponse(ServerCreate):
    id: UUID

    class Config:
        from_attributes = True