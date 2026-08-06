"""
api_client.py — cầu nối tới API thật của Inh (Control Plane, FastAPI + Postgres).
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

BASE_URL = "http://52.55.177.7:8000"
USE_MOCK = False  # Đang gọi API thật qua Tailscale

import contextvars

# "Hộp tạm" giữ token JWT của người đang đăng nhập, để hàm _request() phía dưới
# tự lấy ra và đính kèm vào mọi request gọi lên Control Plane. main.py sẽ đổ
# token vào đây ngay khi mỗi request tới trang web bắt đầu.
current_token: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_token", default=None
)


# ---------------------------------------------------------------------------
# DỮ LIỆU MOCK — chỉ dùng khi USE_MOCK = True.
# ---------------------------------------------------------------------------

_MOCK_SERVERS: list[dict] = [
    {"id": "s-001", "name": "db-prod-01", "ip": "10.0.1.11", "tags": ["prod", "db"]},
    {"id": "s-002", "name": "web-app-02", "ip": "10.0.1.22", "tags": ["prod", "web"]},
    {"id": "s-003", "name": "staging-app-01", "ip": "10.0.2.10", "tags": ["staging"]},
]

_MOCK_GROUPS: list[dict] = [
    {"id": "g-admin", "name": "Admin"},
    {"id": "g-support", "name": "Support"},
    {"id": "g-dev", "name": "Dev"},
]

_MOCK_POLICIES: list[dict] = [
    {"id": "p-001", "group_id": "g-admin", "server_id": "s-001", "max_duration_minutes": 120, "require_approval": False},
    {"id": "p-002", "group_id": "g-admin", "server_id": "s-002", "max_duration_minutes": 120, "require_approval": False},
    {"id": "p-003", "group_id": "g-support", "server_id": "s-002", "max_duration_minutes": 60, "require_approval": True},
]

_MOCK_REQUESTS: list[dict] = [
    {
        "id": "req-101",
        "group_id": "g-support",
        "server_id": "s-002",
        "user_email": "user1@example.com",
        "reason": "Cần fix bug gấp trên web-app-02",
        "duration_minutes": 60,
        "status": "pending",
        "created_at": "2026-07-22T08:00:00Z",
    }
]

_MOCK_GRANTS: list[dict] = [
    {
        "id": "g-901",
        "user_email": "admin@example.com",
        "server_id": "s-001",
        "server_name": "db-prod-01",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=90)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
]


# ---------------------------------------------------------------------------
# Server management
# ---------------------------------------------------------------------------

async def get_servers() -> list[dict]:
    """GET {BASE_URL}/servers/"""
    if USE_MOCK:
        return list(_MOCK_SERVERS)
    return await _request("GET", "/servers/")


async def update_server(
    server_id: str,
    name: str | None = None,
    ip: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """PUT {BASE_URL}/servers/{server_id}"""
    if USE_MOCK:
        for s in _MOCK_SERVERS:
            if s["id"] == server_id:
                if name is not None:
                    s["name"] = name
                if ip is not None:
                    s["ip"] = ip
                if tags is not None:
                    s["tags"] = tags
                return s
        raise RuntimeError("Server not found")

    payload = {}
    if name is not None:
        payload["name"] = name
    if ip is not None:
        payload["ip"] = ip
    if tags is not None:
        payload["tags"] = tags

    return await _request("PUT", f"/servers/{server_id}", json=payload)


# ---------------------------------------------------------------------------
# Group management
# ---------------------------------------------------------------------------

async def get_groups() -> list[dict]:
    """GET {BASE_URL}/groups/"""
    if USE_MOCK:
        return list(_MOCK_GROUPS)
    return await _request("GET", "/auth/groups/")  # <-- SỬA THÀNH THẾ NÀY

async def create_group_backend(
    name: str,
    keycloak_group_id: str,
    description: str | None = None,
) -> dict:
    """POST {BASE_URL}/auth/groups/ — tạo group bên Control Plane."""
    if USE_MOCK:
        new_group = {"id": f"g-{uuid.uuid4().hex[:6]}", "name": name}
        _MOCK_GROUPS.append(new_group)
        return new_group
    payload = {"name": name, "keycloak_group_id": keycloak_group_id}
    if description:
        payload["description"] = description
    return await _request("POST", "/auth/groups/", json=payload)   
# ---------------------------------------------------------------------------
# Policy management (Group-Server)
# ---------------------------------------------------------------------------

async def list_group_server_policies() -> list[dict]:
    """GET {BASE_URL}/policy/group-server/"""
    if USE_MOCK:
        return list(_MOCK_POLICIES)
    return await _request("GET", "/policy/group-server/")


async def save_group_server_policy(
    group_id: str,
    server_id: str,
    max_duration_minutes: int = 60,
    require_approval: bool = True,
) -> dict:
    """
    Tạo/cập nhật policy cho cặp (group_id, server_id).

    Backend thật CHƯA có PATCH/PUT để sửa policy, nên nếu policy đã
    tồn tại (theo group_id+server_id) thì phải XÓA đi rồi TẠO LẠI —
    nếu không sẽ bị lỗi 400 "Policy đã tồn tại".
    """
    if USE_MOCK:
        for p in _MOCK_POLICIES:
            if p["group_id"] == group_id and p["server_id"] == server_id:
                p["max_duration_minutes"] = max_duration_minutes
                p["require_approval"] = require_approval
                return p
        new_pol = {
            "id": f"p-{uuid.uuid4().hex[:6]}",
            "group_id": group_id,
            "server_id": server_id,
            "max_duration_minutes": max_duration_minutes,
            "require_approval": require_approval,
        }
        _MOCK_POLICIES.append(new_pol)
        return new_pol

    existing_policies = await list_group_server_policies()
    existing = next(
        (p for p in existing_policies if p["group_id"] == group_id and p["server_id"] == server_id),
        None,
    )

    if existing:
        await delete_group_server_policy(existing["id"])

    payload = {
        "group_id": group_id,
        "server_id": server_id,
        "max_duration_minutes": max_duration_minutes,
        "require_approval": require_approval,
    }
    return await _request("POST", "/policy/group-server/", json=payload)


async def delete_group_server_policy(policy_id: str) -> None:
    """DELETE {BASE_URL}/policy/group-server/{policy_id}"""
    if USE_MOCK:
        _MOCK_POLICIES[:] = [p for p in _MOCK_POLICIES if p["id"] != policy_id]
        return
    await _request("DELETE", f"/policy/group-server/{policy_id}")


# ---------------------------------------------------------------------------
# Access requests
# ---------------------------------------------------------------------------

async def list_access_requests() -> list[dict]:
    """GET {BASE_URL}/access/requests/"""
    if USE_MOCK:
        return list(_MOCK_REQUESTS)
    return await _request("GET", "/access/requests/")


async def create_access_request(
    group_id: Optional[str] = None,   # <-- sửa thành Optional
    server_id: str = None,
    reason: str = None,
    duration_minutes: int = 60
) -> dict:
    """
    POST {BASE_URL}/access/requests/
    """
    if USE_MOCK:
        new_req = {
            "id": f"req-{uuid.uuid4().hex[:6]}",
            "group_id": group_id,
            "server_id": server_id,
            "user_email": "user_demo@example.com",
            "reason": reason,
            "duration_minutes": duration_minutes,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }
        _MOCK_REQUESTS.append(new_req)
        return new_req

    payload = {
        "server_id": server_id,
        "reason": reason,
        "duration_minutes": duration_minutes,
    }
    if group_id:   # chỉ thêm group_id nếu có giá trị
        payload["group_id"] = group_id

    return await _request("POST", "/access/requests/", json=payload)


async def review_access_request(request_id: str, status: str) -> dict:
    """
    POST {BASE_URL}/access/requests/{request_id}/review
    """
    if USE_MOCK:
        req = next((r for r in _MOCK_REQUESTS if r["id"] == request_id), None)
        if not req:
            raise RuntimeError("Request not found")
        req["status"] = status
        if status == "approved":
            _mock_create_grant(req)
        return req
    return await _request(
        "POST", f"/access/requests/{request_id}/review", json={"status": status}
    )

async def get_my_access_requests() -> list[dict]:
    """Gọi API /access/requests/my của Control Plane, trả về request của chính user (theo token)."""
    if USE_MOCK:
        return list(_MOCK_REQUESTS)   # mock đơn giản
    return await _request("GET", "/access/requests/my")

async def get_my_user_id() -> str | None:
    """Trả về ID của user hiện tại trong DB Control Plane (dùng token)."""
    if USE_MOCK:
        # Trong mock, không có user thật, trả về None
        return None
    try:
        user = await _request("GET", "/auth/users/me")
        return user.get("id")
    except Exception:
        return None
    
async def get_my_active_grants() -> list[dict]:
    """Gọi API /access/grants/my để lấy quyền đang hoạt động của user hiện tại."""
    if USE_MOCK:
        return list(_MOCK_GRANTS)
    return await _request("GET", "/access/grants/my")

def _mock_create_grant(req: dict):
    s = next((srv for srv in _MOCK_SERVERS if srv["id"] == req["server_id"]), None)
    s_name = s["name"] if s else req["server_id"]
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=req.get("duration_minutes", 60))
    _MOCK_GRANTS.append(
        {
            "id": f"g-{uuid.uuid4().hex[:6]}",
            "user_email": req.get("user_email", "user@example.com"),
            "server_id": req["server_id"],
            "server_name": s_name,
            "expires_at": expires.isoformat(),
            "created_at": now.isoformat(),
        }
    )


# ---------------------------------------------------------------------------
# Active grants
# ---------------------------------------------------------------------------

async def list_active_grants() -> list[dict]:
    """GET {BASE_URL}/access/grants/"""
    if USE_MOCK:
        return list(_MOCK_GRANTS)
    return await _request("GET", "/access/grants/")


async def revoke_grant(grant_id: str) -> None:
    """POST {BASE_URL}/access/grants/{grant_id}/revoke"""
    if USE_MOCK:
        _MOCK_GRANTS[:] = [g for g in _MOCK_GRANTS if g["id"] != grant_id]
        return
    await _request("POST", f"/access/grants/{grant_id}/revoke")


# ---------------------------------------------------------------------------
# Helper dùng chung
# ---------------------------------------------------------------------------

async def _request(method: str, path: str, **kwargs) -> dict | list:
    """Gọi Control Plane thật với timeout vọt lên 15s tránh drop kết nối Tailscale."""
    headers = kwargs.pop("headers", {}) or {}
    token = current_token.get()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        response = await client.request(method, path, headers=headers, **kwargs)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

async def get_users() -> list[dict]:
    """Lấy danh sách tất cả users từ Control Plane."""
    if USE_MOCK:
        return []
    return await _request("GET", "/auth/users/")        

async def create_user_backend(
    username: str,
    email: str | None = None,
    full_name: str | None = None,
    keycloak_sub: str | None = None,   # THÊM DÒNG NÀY
) -> dict:
    """POST {BASE_URL}/auth/users/ — tạo user bên Control Plane."""
    if USE_MOCK:
        return {"id": f"u-{uuid.uuid4().hex[:6]}", "username": username}
    payload = {"username": username}
    if email:
        payload["email"] = email
    if full_name:
        payload["full_name"] = full_name
    if keycloak_sub:                     # THÊM KHỐI NÀY
        payload["keycloak_sub"] = keycloak_sub
    return await _request("POST", "/auth/users/", json=payload)

async def create_policy(group_id: str, server_id: str, policy: str = "allow", duration: int = 60) -> dict:
    payload = {
        "group_id": group_id,
        "server_id": server_id,
        "policy": policy,
        "duration": duration
    }
    return await _request("POST", "/policy/group-server/", json=payload)

async def delete_policy(policy_id: str) -> dict:
    return await _request("DELETE", f"/policy/group-server/{policy_id}")

async def delete_group_server_policy(policy_id: str) -> dict:
    """DELETE {BASE_URL}/policy/group-server/{policy_id}"""
    if USE_MOCK:
        return {"message": "mock ok"}
    return await _request("DELETE", f"/policy/group-server/{policy_id}")

async def delete_group_backend(group_id: str) -> None:
    """DELETE {BASE_URL}/auth/groups/{group_id}"""
    if USE_MOCK:
        return
    await _request("DELETE", f"/auth/groups/{group_id}")

async def remove_user_from_group(user_id: str, group_id: str) -> None:
    """DELETE {BASE_URL}/auth/users/{user_id}/groups/{group_id}"""
    if USE_MOCK:
        return
    await _request("DELETE", f"/auth/users/{user_id}/groups/{group_id}")

async def get_audit_sessions() -> list[dict]:
    """GET {BASE_URL}/audit/sessions/ — lịch sử session: user, server, thời gian, trạng thái."""
    if USE_MOCK:
        return []
    return await _request("GET", "/audit/sessions/")