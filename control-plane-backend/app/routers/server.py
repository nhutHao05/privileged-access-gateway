from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.schemas.server import ServerCreate, ServerResponse, ServerUpdate
from app.models.auth_rbac import Server, AuditLog
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.auth_rbac import User

router = APIRouter(
    prefix="/servers",
    tags=["Servers Management"]
)

# 1. Tạo máy chủ mới
@router.post("/", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
def create_server(
    server_in: ServerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing_server = db.query(Server).filter(
        (Server.host == server_in.ip) | (Server.name == server_in.name)
    ).first()

    if existing_server:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server với Name hoặc IP này đã tồn tại trong hệ thống."
        )

    new_server = Server(
        name=server_in.name,
        host=server_in.ip,
        port=server_in.port,
        protocol=server_in.protocol,
        guacamole_connection_id=server_in.guacamole_connection_id,
        tags=server_in.tags
    )
    db.add(new_server)

    audit = AuditLog(
        user_id=current_user.id,
        action="SERVER_CREATED",
        target_type="SERVER",
        target_id=str(new_server.id) if new_server.id else None,
        details=f"Tạo máy chủ '{server_in.name}' ({server_in.protocol.upper()} {server_in.ip}:{server_in.port})"
    )
    db.add(audit)
    db.commit()
    db.refresh(new_server)
    return new_server

# 2. Lấy danh sách tất cả máy chủ
@router.get("/", response_model=List[ServerResponse])
def get_all_servers(db: Session = Depends(get_db)):
    return db.query(Server).all()

# 3. Cập nhật máy chủ
@router.patch("/{server_id}", response_model=ServerResponse)
def update_server(
    server_id: UUID,
    server_in: ServerUpdate,
    db: Session = Depends(get_db)
):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy Server."
        )

    update_data = server_in.model_dump(exclude_unset=True)
    # Xử lý alias ip -> host
    if 'ip' in update_data:
        update_data['host'] = update_data.pop('ip')
    for key, value in update_data.items():
        setattr(server, key, value)

    db.commit()
    db.refresh(server)
    return server

# 4. Xóa máy chủ
@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(
    server_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy Server."
        )

    server_name = server.name

    audit = AuditLog(
        user_id=current_user.id,
        action="SERVER_DELETED",
        target_type="SERVER",
        target_id=str(server_id),
        details=f"Xóa máy chủ '{server_name}'"
    )
    db.add(audit)
    db.delete(server)
    db.commit()
    return None