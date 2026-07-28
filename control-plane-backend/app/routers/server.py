from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.schemas.server import ServerCreate, ServerResponse, ServerUpdate
from app.models.auth_rbac import Server
from app.core.database import get_db

router = APIRouter(
    prefix="/servers",
    tags=["Servers Management"]
)

# 1. API Tạo máy chủ mới (POST /servers/)
@router.post("/", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
def create_server(server_in: ServerCreate, db: Session = Depends(get_db)):
    # Kiểm tra xem IP hoặc Name đã tồn tại chưa (Đã đổi host -> ip)
    existing_server = db.query(Server).filter(
        (Server.ip == server_in.ip) | (Server.name == server_in.name)
    ).first()
    
    if existing_server:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Server với Name hoặc IP này đã tồn tại trong hệ thống."
        )
    
    new_server = Server(**server_in.model_dump())
    db.add(new_server)
    db.commit()
    db.refresh(new_server)
    return new_server

# 2. API Lấy danh sách tất cả máy chủ (GET /servers/)
@router.get("/", response_model=List[ServerResponse])
def get_all_servers(db: Session = Depends(get_db)):
    return db.query(Server).all()

# 3. API Cập nhật máy chủ (PATCH /servers/{server_id})
@router.patch("/{server_id}", response_model=ServerResponse)
def update_server(server_id: UUID, server_in: ServerUpdate, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Không tìm thấy Server."
        )
    
    update_data = server_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(server, key, value)
        
    db.commit()
    db.refresh(server)
    return server