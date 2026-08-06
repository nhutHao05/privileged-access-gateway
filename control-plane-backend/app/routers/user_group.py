from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.schemas.user_group import UserCreate, UserResponse, GroupCreate, GroupResponse
from app.models.auth_rbac import User, Group
from app.core.database import get_db
from app.core.auth import get_current_user
from sqlalchemy import and_

router = APIRouter(
    prefix="/auth",
    tags=["Users & Groups Management"]
)

# 1. Tạo User
@router.post("/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(
    (User.username == user_in.username) |
    (and_(User.email.isnot(None), User.email == user_in.email))
).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username hoặc Email đã tồn tại.")

    new_user = User(**user_in.model_dump())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# 2. Lấy danh sách Users
@router.get("/users/", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

# 3. Lấy thông tin user hiện tại (dùng cho User Portal)
@router.get("/users/me", response_model=UserResponse)
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return current_user

# 4. Tạo Group
@router.post("/groups/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(group_in: GroupCreate, db: Session = Depends(get_db)):
    existing_group = db.query(Group).filter(Group.name == group_in.name).first()
    if existing_group:
        raise HTTPException(status_code=400, detail="Tên nhóm đã tồn tại.")

    new_group = Group(**group_in.model_dump())
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    return new_group

# 5. Lấy danh sách Groups
@router.get("/groups/", response_model=List[GroupResponse])
def get_groups(db: Session = Depends(get_db)):
    return db.query(Group).all()

# 6. Gán User vào Nhóm
@router.post("/users/{user_id}/groups/{group_id}", status_code=status.HTTP_200_OK)
def assign_user_to_group(user_id: UUID, group_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User không tồn tại.")

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group không tồn tại.")

    if group not in user.groups:
        user.groups.append(group)
        db.commit()

    return {"message": f"Đã gán User '{user.username}' vào Nhóm '{group.name}' thành công."}

# 7. Xóa User khỏi Nhóm
@router.delete("/users/{user_id}/groups/{group_id}", status_code=status.HTTP_200_OK)
def remove_user_from_group(user_id: UUID, group_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User không tồn tại.")

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group không tồn tại.")

    if group in user.groups:
        user.groups.remove(group)
        db.commit()

    return {"message": f"Đã xóa User '{user.username}' khỏi Nhóm '{group.name}'."}

# 8. Xóa Group
@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: UUID, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Không tìm thấy Group.")
    if group.users:
        raise HTTPException(
            status_code=400,
            detail="Không thể xóa group còn thành viên. Gỡ hết user khỏi group trước."
        )
    db.delete(group)
    db.commit()
    return None