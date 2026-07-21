from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.schemas.policy import UserGroupAssign, GroupServerPolicyCreate, GroupServerPolicyResponse
from app.models.auth_rbac import User, Group, Server, GroupServerPolicy, user_groups
from app.core.database import get_db

router = APIRouter(
    prefix="/policy",
    tags=["Policy & Assignment Management"]
)

# 1. API Gán User vào Group
@router.post("/assign-user-group/", status_code=status.HTTP_200_OK)
def assign_user_to_group(payload: UserGroupAssign, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    group = db.query(Group).filter(Group.id == payload.group_id).first()
    
    if not user or not group:
        raise HTTPException(status_code=404, detail="User hoặc Group không tồn tại.")
    
    # Kiểm tra xem user đã ở trong group chưa
    if group in user.groups:
        return {"message": "User đã nằm trong Group này từ trước rồi."}
    
    user.groups.append(group)
    db.commit()
    return {"message": f"Đã thêm User '{user.username}' vào Group '{group.name}' thành công."}


# 2. API Gán Group với Server (Tạo Policy)
@router.post("/group-server/", response_model=GroupServerPolicyResponse, status_code=status.HTTP_201_CREATED)
def create_group_server_policy(payload: GroupServerPolicyCreate, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == payload.group_id).first()
    server = db.query(Server).filter(Server.id == payload.server_id).first()
    
    if not group or not server:
        raise HTTPException(status_code=404, detail="Group hoặc Server không tồn tại.")
    
    # Kiểm tra xem Policy đã có chưa
    existing_policy = db.query(GroupServerPolicy).filter(
        GroupServerPolicy.group_id == payload.group_id,
        GroupServerPolicy.server_id == payload.server_id
    ).first()
    
    if existing_policy:
        raise HTTPException(status_code=400, detail="Chính sách cho Group và Server này đã tồn tại.")
    
    new_policy = GroupServerPolicy(
        group_id=payload.group_id,
        server_id=payload.server_id
    )
    db.add(new_policy)
    db.commit()
    db.refresh(new_policy)
    return new_policy