from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from app.schemas.access import (
    AccessRequestCreate, AccessRequestResponse, 
    AccessRequestReview, ActiveGrantResponse
)
from app.models.auth_rbac import AccessRequest, ActiveGrant, User, Server, GroupServerPolicy, Group, SessionLog, AuditLog
from app.core.database import get_db, SessionLocal
from app.core.scheduler import scheduler
from app.core.auth import get_current_user
from app.services.guacamole import guac_client # Import module Guacamole

router = APIRouter(
    prefix="/access",
    tags=["JIT Access Management"]
)

# Hàm bọc xử lý thu hồi tự động khi hết hạn (Vừa thu hồi Guacamole + vừa cập nhật DB)
async def auto_revoke_wrapper(request_id: UUID, username: str, connection_id: str):
    db = SessionLocal()
    try:
        # 1. Thu hồi quyền trên Guacamole
        success = await guac_client.revoke_connection_access(username, connection_id)
        
        # 2. Cập nhật Database
        if success:
            # Xóa ActiveGrant tương ứng
            grant = db.query(ActiveGrant).filter(ActiveGrant.request_id == request_id).first()
            if grant:
                db.delete(grant)
            
            # Đổi trạng thái request thành 'expired'
            req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
            if req:
                req.status = "expired"
            
            db.commit()
            print(f"🔴 [AUTO-REVOKE] Đã tự động thu hồi & cập nhật DB cho Request {request_id}")
    except Exception as e:
        print(f"❌ [AUTO-REVOKE] Lỗi khi thực thi thu hồi tự động: {e}")
    finally:
        db.close()


# 1. API Gửi Yêu cầu truy cập (Access Request)
@router.post("/requests/", response_model=AccessRequestResponse, status_code=status.HTTP_201_CREATED)
def create_access_request(
    payload: AccessRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Kiểm tra Server có tồn tại không
    server = db.query(Server).filter(Server.id == payload.server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server không tồn tại.")

    # 2. Xác định user (nếu payload truyền thì dùng payload, không thì dùng token current_user)
    target_user_id = payload.user_id if payload.user_id else current_user.id
    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User không tồn tại trong hệ thống.")

    # 3. Kiểm tra RBAC Policy (GroupServerPolicy)
    user_group_ids = [g.id for g in user.groups] if user.groups else []
    if payload.group_id and payload.group_id not in user_group_ids:
        user_group_ids.append(payload.group_id)

    # Lấy thông tin các Nhóm để kiểm tra Admin
    groups = db.query(Group).filter(Group.id.in_(user_group_ids)).all() if user_group_ids else []
    is_admin = any(g.name == "PAM-Admins" for g in groups)

    # Nếu không phải Admin, kiểm tra quyền theo GroupServerPolicy
    if not is_admin:
        total_system_policies = db.query(GroupServerPolicy).count()
        # Nếu hệ thống đã thiết lập policy
        if total_system_policies > 0:
            matching_policies = db.query(GroupServerPolicy).filter(
                GroupServerPolicy.server_id == payload.server_id,
                GroupServerPolicy.group_id.in_(user_group_ids)
            ).all() if user_group_ids else []

            if not matching_policies:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền xin truy cập máy chủ này (chưa được gán Policy cho Nhóm của bạn)."
                )

            max_allowed_minutes = max(p.max_duration_minutes for p in matching_policies)
            if payload.requested_minutes > max_allowed_minutes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Thời gian xin truy cập ({payload.requested_minutes} phút) vượt quá giới hạn tối đa được phép ({max_allowed_minutes} phút)."
                )

    # 4. Tạo Request mới
    new_request = AccessRequest(
        user_id=target_user_id,
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
async def review_access_request(request_id: UUID, review: AccessRequestReview, db: Session = Depends(get_db)):
    req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Yêu cầu không tồn tại.")
    
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Yêu cầu này đã được xử lý trước đó.")

    if review.status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Trạng thái chỉ có thể là 'approved' hoặc 'rejected'.")

    req.status = review.status
    
    # Nếu Approved -> Cấp quyền trên Guacamole + Lên lịch tự động thu hồi
    if review.status == "approved":
        now = datetime.now(timezone.utc)    
        expire_time = now + timedelta(minutes=req.requested_minutes)
        
        # Lấy thông tin User & Server để tương tác với Guacamole
        user = db.query(User).filter(User.id == req.user_id).first()
        server = db.query(Server).filter(Server.id == req.server_id).first()

        username_to_grant = getattr(user, 'username', getattr(user, 'email', 'taninh'))
        
        # A. CẤP QUYỀN TRÊN GUACAMOLE NGAY LẬP TỨC
        success = await guac_client.grant_connection_access(
            username=username_to_grant,
            connection_id=server.guacamole_connection_id
        )

        if not success:
            raise HTTPException(status_code=500, detail="Lỗi khi gọi Guacamole REST API để cấp quyền!")

        # B. TẠO RECORD ACTIVE GRANT
        grant = ActiveGrant(
            request_id=req.id,
            user_id=req.user_id,
            server_id=req.server_id,
            granted_at=now,
            expires_at=expire_time
        )
        db.add(grant)

        # C. TẠO RECORD SESSION LOG CHO SPRINT 3 AUDIT TRAIL
        session_log = SessionLog(
            request_id=req.id,
            user_id=req.user_id,
            server_id=req.server_id,
            start_time=now,
            status="active"
        )
        db.add(session_log)

        # D. GHI NHẬT KÝ HỆ THỐNG (AUDIT LOG)
        audit_log = AuditLog(
            user_id=req.user_id,
            action="ACCESS_APPROVED",
            target_type="SERVER",
            target_id=str(req.server_id),
            details=f"Duyệt cấp quyền {req.requested_minutes} phút truy cập máy chủ {server.name}"
        )
        db.add(audit_log)

        # E. ĐẶT LỊCH APSCHEDULER TỰ ĐỘNG THU HỒI QUYỀN KHI HẾT HẠN JIT
        scheduler.add_job(
            auto_revoke_wrapper,
            'date',
            run_date=expire_time,
            args=[req.id, username_to_grant, server.guacamole_connection_id],
            id=f"revoke_{req.id}",
            replace_existing=True
        )
        print(f"⏰ [SCHEDULER] Đã đặt lịch Auto-Revoke sau {req.requested_minutes} phút (Lúc {expire_time})")

    db.commit()
    db.refresh(req)
    return req

# 4. API Lấy danh sách các Grant đang có hiệu lực
@router.get("/grants/", response_model=List[ActiveGrantResponse])
def get_active_grants(db: Session = Depends(get_db)):
    return db.query(ActiveGrant).all()

# 5. API Thu hồi quyền Active Grant khẩn cấp (Revoke thủ công bởi Admin)
@router.post("/grants/{grant_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_active_grant(grant_id: UUID, db: Session = Depends(get_db)):
    grant = db.query(ActiveGrant).filter(ActiveGrant.id == grant_id).first()
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Không tìm thấy Active Grant để thu hồi."
        )
    
    # Hủy job đếm ngược tự động nếu Admin bấm Revoke thủ công sớm hơn
    job_id = f"revoke_{grant.request_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    # Lấy user & server tương ứng để xóa quyền ngay lập tức trên Guacamole
    user = db.query(User).filter(User.id == grant.user_id).first()
    server = db.query(Server).filter(Server.id == grant.server_id).first()
    username_to_revoke = getattr(user, 'username', getattr(user, 'email', 'taninh'))

    # Gọi API Guacamole Thu hồi quyền lập tức
    await guac_client.revoke_connection_access(
        username=username_to_revoke,
        connection_id=server.guacamole_connection_id
    )

    # Cập nhật trạng thái Request sang expired
    req = db.query(AccessRequest).filter(AccessRequest.id == grant.request_id).first()
    if req:
        req.status = "expired"

    db.delete(grant)
    db.commit()
    return {"message": "Đã thu hồi quyền truy cập thành công."}

# API phụ: Lấy danh sách Server để lấy ID test trên Swagger UI
@router.get("/servers/")
def get_all_servers(db: Session = Depends(get_db)):
    return db.query(Server).all()