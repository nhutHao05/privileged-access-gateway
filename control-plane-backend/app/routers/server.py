from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.schemas.server import ServerCreate, ServerResponse
from app.models.auth_rbac import Server
from app.core.database import get_db

router = APIRouter(
    prefix="/servers",
    tags=["Servers Management"]
)

# 1. API Tạo máy chủ mới (POST /servers/)
@router.post("/", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
def create_server(server_in: ServerCreate, db: Session = Depends(get_db)):
    # Kiểm tra xem host đã tồn tại chưa
    existing_server = db.query(Server).filter(
        (Server.host == server_in.host) | (Server.name == server_in.name)
    ).first()
    
    if existing_server:
        raise HTTPException(
            status_code=400, 
            detail="Server với Name hoặc Host này đã tồn tại trong hệ thống."
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