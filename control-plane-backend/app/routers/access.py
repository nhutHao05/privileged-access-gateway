from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
from uuid import UUID

from app.schemas.access import (
    AccessRequestCreate, AccessRequestResponse, 
    AccessRequestReview, ActiveGrantResponse
)
from app.models.auth_rbac import AccessRequest, ActiveGrant, User, Server
from app.core.database import get_db

router = APIRouter(
    prefix="/access",
    tags=["JIT Access Management"]
)

# 1. API Gửi Yêu cầu truy cập (Access Request)
@router.post("/requests/", response_model=AccessRequestResponse, status_code=status.HTTP_201_CREATED)
def create_access_request(payload: AccessRequestCreate, db: Session = Depends(get_db)):
    # Kiểm tra User và Server có tồn tại không
    user = db.query(User).filter(User.id == payload.user_id).first()
    server = db.query(Server).filter(Server.id == payload.server_id).first()
    if not user or not server:
        raise HTTPException(status_code=404, detail="User hoặc Server không tồn tại.")

    new_request = AccessRequest(
        user_id=payload.user_id,
        server_id=payload.server_id,
        reason=payload.reason,
        requested_minutes=payload.requested_minutes,
        status="pending"
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request

# 2. API Lấy danh sách các Yêu cầu xin quyền
@router.get("/requests/", response_model=List[AccessRequestResponse])
def get_access_requests(db: Session = Depends(get_db)):
    return db.query(AccessRequest).all()

# 3. API Phê duyệt / Từ chối Yêu cầu (Approve/Reject)
@router.post("/requests/{request_id}/review", response_model=AccessRequestResponse)
def review_access_request(request_id: UUID, review: AccessRequestReview, db: Session = Depends(get_db)):
    req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Yêu cầu không tồn tại.")
    
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Yêu cầu này đã được xử lý trước đó.")

    if review.status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Trạng thái chỉ có thể là 'approved' hoặc 'rejected'.")

    req.status = review.status
    
    # Nếu Approved -> Tự động sinh bản ghi ActiveGrant với thời gian hết hạn (JIT)
    if review.status == "approved":
        now = datetime.utcnow()
        expire_time = now + timedelta(minutes=req.requested_minutes)
        
        grant = ActiveGrant(
            request_id=req.id,
            user_id=req.user_id,
            server_id=req.server_id,
            granted_at=now,
            expires_at=expire_time
        )
        db.add(grant)

    db.commit()
    db.refresh(req)
    return req

# 4. API Lấy danh sách các Grant đang có hiệu lực
@router.get("/grants/", response_model=List[ActiveGrantResponse])
def get_active_grants(db: Session = Depends(get_db)):
    return db.query(ActiveGrant).all()