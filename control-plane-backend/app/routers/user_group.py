from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.schemas.user_group import UserCreate, UserResponse, GroupCreate, GroupResponse
from app.models.auth_rbac import User, Group
from app.core.database import get_db

router = APIRouter(
    prefix="/auth",
    tags=["Users & Groups Management"]
)

# 1. API Tạo User
@router.post("/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username hoặc Email đã tồn tại.")
    
    new_user = User(**user_in.model_dump())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# 2. API Lấy danh sách Users
@router.get("/users/", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

# 3. API Tạo Group
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

# 4. API Lấy danh sách Groups
@router.get("/groups/", response_model=List[GroupResponse])
def get_groups(db: Session = Depends(get_db)):
    return db.query(Group).all()