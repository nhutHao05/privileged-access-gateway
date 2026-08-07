from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from app.schemas.access import (
    AccessRequestCreate, AccessRequestResponse,
    AccessRequestReview, ActiveGrantResponse
)
from app.models.auth_rbac import AccessRequest, ActiveGrant, User, Server, GroupServerPolicy, Group, SessionLog, AuditLog, ServerWhitelist
from app.core.database import get_db, SessionLocal
from app.core.scheduler import scheduler
from app.core.auth import get_current_user
from app.services.guacamole import guac_client

router = APIRouter(
    prefix="/access",
    tags=["JIT Access Management"]
)

# ─── Helper: Auto-revoke khi JIT hết hạn ────────────────────────────────────
async def auto_revoke_wrapper(request_id: UUID, username: str, connection_id: str):
    db = SessionLocal()
    try:
        success = await guac_client.revoke_connection_access(username, connection_id)
        if success:
            grant = db.query(ActiveGrant).filter(ActiveGrant.request_id == request_id).first()
            if grant:
                db.delete(grant)

            req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
            if req:
                req.status = "expired"

            # Cập nhật SessionLog khi hết hạn
            session_log = db.query(SessionLog).filter(SessionLog.request_id == request_id).first()
            if session_log:
                session_log.end_time = datetime.now(timezone.utc)
                session_log.status = "completed"

            db.commit()
            print(f"🔴 [AUTO-REVOKE] Đã tự động thu hồi & cập nhật DB cho Request {request_id}")
    except Exception as e:
        print(f"❌ [AUTO-REVOKE] Lỗi khi thực thi thu hồi tự động: {e}")
    finally:
        db.close()


# ─── 1. User gửi yêu cầu xin quyền ─────────────────────────────────────────
@router.post("/requests/", response_model=AccessRequestResponse, status_code=status.HTTP_201_CREATED)
def create_access_request(
    payload: AccessRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    server = db.query(Server).filter(Server.id == payload.server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server không tồn tại.")

    target_user_id = payload.user_id if payload.user_id else current_user.id
    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User không tồn tại trong hệ thống.")

    user_group_ids = [g.id for g in user.groups] if user.groups else []
    if payload.group_id and payload.group_id not in user_group_ids:
        user_group_ids.append(payload.group_id)

    groups = db.query(Group).filter(Group.id.in_(user_group_ids)).all() if user_group_ids else []
    is_admin = any(g.name == "PAM-Admins" for g in groups)

    if not is_admin:
        total_system_policies = db.query(GroupServerPolicy).count()
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
                    detail=f"Thời gian xin ({payload.requested_minutes} phút) vượt quá giới hạn tối đa ({max_allowed_minutes} phút)."
                )

    # ── Lớp bảo mật thứ 2: Kiểm tra SSH Whitelist ──
    whitelist_entries = db.query(ServerWhitelist).filter(
        ServerWhitelist.server_id == payload.server_id
    ).all()
    # Nếu server có whitelist (có ít nhất 1 entry) → user phải nằm trong đó
    if whitelist_entries:
        whitelisted_user_ids = [e.user_id for e in whitelist_entries]
        if target_user_id not in whitelisted_user_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User không nằm trong Whitelist SSH của server này. Liên hệ Admin để được thêm vào."
            )

    new_request = AccessRequest(
        user_id=target_user_id,
        server_id=payload.server_id,
        reason=payload.reason,
        requested_minutes=payload.requested_minutes,
        status="pending"
    )
    db.add(new_request)

    # Ghi AuditLog: user xin quyền
    audit_log = AuditLog(
        user_id=target_user_id,
        action="ACCESS_REQUESTED",
        target_type="SERVER",
        target_id=str(payload.server_id),
        details=f"Xin quyền truy cập {payload.requested_minutes} phút vào máy chủ {server.name}. Lý do: {payload.reason}"
    )
    db.add(audit_log)

    db.commit()
    db.refresh(new_request)
    return new_request


# ─── 2. Admin: Lấy tất cả yêu cầu ──────────────────────────────────────────
@router.get("/requests/", response_model=List[AccessRequestResponse])
def get_access_requests(db: Session = Depends(get_db)):
    return db.query(AccessRequest).order_by(AccessRequest.requested_at.desc()).all()


# ─── 3. User: Lấy yêu cầu của chính mình ────────────────────────────────────
@router.get("/requests/my", response_model=List[AccessRequestResponse])
def get_my_access_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(AccessRequest).filter(
        AccessRequest.user_id == current_user.id
    ).order_by(AccessRequest.requested_at.desc()).all()


# ─── 4. Admin: Duyệt / Từ chối yêu cầu ─────────────────────────────────────
@router.post("/requests/{request_id}/review", response_model=AccessRequestResponse)
async def review_access_request(
    request_id: UUID,
    review: AccessRequestReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Yêu cầu không tồn tại.")

    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Yêu cầu này đã được xử lý trước đó.")

    if review.status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Trạng thái chỉ có thể là 'approved' hoặc 'rejected'.")

    req.status = review.status
    req.decided_by = current_user.id
    req.decided_at = datetime.now(timezone.utc)
    if hasattr(review, 'decision_note') and review.decision_note:
        req.decision_note = review.decision_note

    if review.status == "approved":
        now = datetime.now(timezone.utc)
        expire_time = now + timedelta(minutes=req.requested_minutes)

        user = db.query(User).filter(User.id == req.user_id).first()
        server = db.query(Server).filter(Server.id == req.server_id).first()
        username_to_grant = getattr(user, 'username', getattr(user, 'email', 'unknown'))

        # A. Cấp quyền trên Guacamole
        success = await guac_client.grant_connection_access(
            username=username_to_grant,
            connection_id=server.guacamole_connection_id
        )
        if not success:
            raise HTTPException(status_code=500, detail="Lỗi khi gọi Guacamole REST API để cấp quyền!")

        # B. Tạo ActiveGrant
        grant = ActiveGrant(
            request_id=req.id,
            user_id=req.user_id,
            server_id=req.server_id,
            granted_at=now,
            expires_at=expire_time
        )
        db.add(grant)

        # C. Tạo SessionLog
        session_log = SessionLog(
            request_id=req.id,
            user_id=req.user_id,
            server_id=req.server_id,
            start_time=now,
            status="active"
        )
        db.add(session_log)

        # D. Ghi AuditLog: admin duyệt
        audit_log = AuditLog(
            user_id=current_user.id,
            action="ACCESS_APPROVED",
            target_type="SERVER",
            target_id=str(req.server_id),
            details=f"Duyệt cấp quyền {req.requested_minutes} phút truy cập máy chủ {server.name} cho user {username_to_grant}"
        )
        db.add(audit_log)

        # E. Đặt lịch auto-revoke
        scheduler.add_job(
            auto_revoke_wrapper,
            'date',
            run_date=expire_time,
            args=[req.id, username_to_grant, server.guacamole_connection_id],
            id=f"revoke_{req.id}",
            replace_existing=True
        )
        print(f"⏰ [SCHEDULER] Đặt lịch Auto-Revoke sau {req.requested_minutes} phút (Lúc {expire_time})")

    elif review.status == "rejected":
        # Ghi AuditLog: admin từ chối
        user = db.query(User).filter(User.id == req.user_id).first()
        server = db.query(Server).filter(Server.id == req.server_id).first()
        audit_log = AuditLog(
            user_id=current_user.id,
            action="ACCESS_REJECTED",
            target_type="SERVER",
            target_id=str(req.server_id),
            details=f"Từ chối yêu cầu truy cập máy chủ {server.name if server else req.server_id} của user {user.username if user else req.user_id}"
        )
        db.add(audit_log)

    db.commit()
    db.refresh(req)
    return req


# ─── 5. Admin: Lấy tất cả grant đang hoạt động ──────────────────────────────
@router.get("/grants/", response_model=List[ActiveGrantResponse])
def get_active_grants(db: Session = Depends(get_db)):
    return db.query(ActiveGrant).all()


# ─── 6. User: Lấy grant đang hoạt động của mình ─────────────────────────────
@router.get("/grants/my", response_model=List[ActiveGrantResponse])
def get_my_active_grants(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(ActiveGrant).filter(ActiveGrant.user_id == current_user.id).all()


# ─── 7. Admin: Thu hồi quyền thủ công ───────────────────────────────────────
@router.post("/grants/{grant_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_active_grant(
    grant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    grant = db.query(ActiveGrant).filter(ActiveGrant.id == grant_id).first()
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy Active Grant để thu hồi."
        )

    job_id = f"revoke_{grant.request_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    user = db.query(User).filter(User.id == grant.user_id).first()
    server = db.query(Server).filter(Server.id == grant.server_id).first()
    username_to_revoke = getattr(user, 'username', getattr(user, 'email', 'unknown'))

    await guac_client.revoke_connection_access(
        username=username_to_revoke,
        connection_id=server.guacamole_connection_id
    )

    req = db.query(AccessRequest).filter(AccessRequest.id == grant.request_id).first()
    if req:
        req.status = "expired"

    # Cập nhật SessionLog
    session_log = db.query(SessionLog).filter(SessionLog.request_id == grant.request_id).first()
    if session_log:
        session_log.end_time = datetime.now(timezone.utc)
        session_log.status = "revoked"

    # Ghi AuditLog: admin thu hồi
    audit_log = AuditLog(
        user_id=current_user.id,
        action="ACCESS_REVOKED",
        target_type="SERVER",
        target_id=str(grant.server_id),
        details=f"Thu hồi quyền truy cập máy chủ {server.name if server else grant.server_id} của user {username_to_revoke}"
    )
    db.add(audit_log)

    db.delete(grant)
    db.commit()
    return {"message": "Đã thu hồi quyền truy cập thành công."}


# ─── 8. User: Lấy server mình được phép xin quyền ───────────────────────────
@router.get("/servers/available")
def get_available_servers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lấy danh sách server mà user hiện tại có thể xin quyền (theo GroupServerPolicy)."""
    user_group_ids = [g.id for g in current_user.groups] if current_user.groups else []

    groups = db.query(Group).filter(Group.id.in_(user_group_ids)).all() if user_group_ids else []
    is_admin = any(g.name == "PAM-Admins" for g in groups)

    if is_admin:
        # Admin thấy tất cả server
        servers = db.query(Server).all()
        result = []
        for s in servers:
            result.append({
                "id": str(s.id),
                "name": s.name,
                "host": s.host,
                "port": s.port,
                "protocol": s.protocol,
                "guacamole_connection_id": s.guacamole_connection_id,
                "tags": s.tags,
                "max_duration_minutes": 480,
                "require_approval": False
            })
        return result

    # User thường: chỉ server có policy khớp với group của mình
    if not user_group_ids:
        return []

    policies = db.query(GroupServerPolicy).filter(
        GroupServerPolicy.group_id.in_(user_group_ids)
    ).all()

    server_policy_map = {}
    for p in policies:
        sid = str(p.server_id)
        if sid not in server_policy_map or p.max_duration_minutes > server_policy_map[sid]["max_duration_minutes"]:
            server_policy_map[sid] = {
                "max_duration_minutes": p.max_duration_minutes,
                "require_approval": p.require_approval
            }

    result = []
    for sid, policy_info in server_policy_map.items():
        server = db.query(Server).filter(Server.id == sid).first()
        if server:
            result.append({
                "id": str(server.id),
                "name": server.name,
                "host": server.host,
                "port": server.port,
                "protocol": server.protocol,
                "guacamole_connection_id": server.guacamole_connection_id,
                "tags": server.tags,
                "max_duration_minutes": policy_info["max_duration_minutes"],
                "require_approval": policy_info["require_approval"]
            })
    return result


# ─── 9. Lấy tất cả server (dùng cho Admin, giữ lại tương thích) ─────────────
@router.get("/servers/")
def get_all_servers_compat(db: Session = Depends(get_db)):
    return db.query(Server).all()