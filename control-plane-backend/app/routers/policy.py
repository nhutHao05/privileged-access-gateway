from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.models.auth_rbac import GroupServerPolicy
from app.schemas.policy import GroupServerPolicyCreate, GroupServerPolicyResponse, GroupServerPolicyUpdate

router = APIRouter(prefix="/policy", tags=["Policies"])

# 1. GET danh sách tất cả Policy
@router.get("/group-server/", response_model=List[GroupServerPolicyResponse])
def get_group_server_policies(db: Session = Depends(get_db)):
    return db.query(GroupServerPolicy).all()

# 2. POST tạo Policy mới (Gán Nhóm - Server)
@router.post("/group-server/", response_model=GroupServerPolicyResponse, status_code=status.HTTP_201_CREATED)
def create_group_server_policy(policy_in: GroupServerPolicyCreate, db: Session = Depends(get_db)):
    existing = db.query(GroupServerPolicy).filter(
        GroupServerPolicy.group_id == policy_in.group_id,
        GroupServerPolicy.server_id == policy_in.server_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Policy cho Group và Server này đã tồn tại."
        )
        
    new_policy = GroupServerPolicy(**policy_in.model_dump())
    db.add(new_policy)
    db.commit()
    db.refresh(new_policy)
    return new_policy

# 3. PUT cập nhật Policy (sửa thời lượng, approval, allowed_actions)
@router.put("/group-server/{policy_id}", response_model=GroupServerPolicyResponse)
def update_group_server_policy(policy_id: UUID, policy_in: GroupServerPolicyUpdate, db: Session = Depends(get_db)):
    policy = db.query(GroupServerPolicy).filter(GroupServerPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy Policy."
        )

    update_data = policy_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(policy, field, value)

    db.commit()
    db.refresh(policy)
    return policy

# 4. DELETE xóa Policy (Khi bỏ tick "Được phép" ở UI)
@router.delete("/group-server/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group_server_policy(policy_id: UUID, db: Session = Depends(get_db)):
    policy = db.query(GroupServerPolicy).filter(GroupServerPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Không tìm thấy Policy."
        )
    db.delete(policy)
    db.commit()
    return None