"""
api_client.py — khung gọi API thật của Inh (Control Plane, FastAPI + Postgres).

CÁCH DÙNG SAU NÀY:
Khi Inh xong API, đổi USE_MOCK = False bên dưới, rồi điền phần TODO trong
từng hàm (gọi httpx tới BASE_URL, đúng path/method như trong
RBAC-API-Spec-Draft.docx). main.py sẽ gọi các hàm trong file này thay vì
thao tác trực tiếp lên MOCK_SERVERS / GROUP_SERVER_POLICY /
access_requests_db — nghĩa là lúc đó KHÔNG cần sửa route hay template,
chỉ sửa file này.

Toàn bộ hàm ở đây trả về đúng cấu trúc dict/list mà template đang dùng
(snake_case, đúng field như đã chốt) để cắm thẳng vào main.py.

Chưa dùng file này ở đâu cả — main.py hiện tại vẫn dùng mock data trong
RAM. Đây là bước chuẩn bị trước.
"""

import httpx

BASE_URL = "http://127.0.0.1:8080"  # TODO: đổi thành URL thật của Control Plane khi Inh cung cấp
USE_MOCK = True  # TODO: đổi thành False khi bắt đầu ghép API thật


# ---------------------------------------------------------------------------
# Servers — GET /api/servers, PATCH /api/servers/{server_id}
# ---------------------------------------------------------------------------

async def get_servers() -> list[dict]:
    """Trả về danh sách server. TODO: GET {BASE_URL}/api/servers"""
    raise NotImplementedError("Chưa ghép API thật — dùng MOCK_SERVERS trong main.py")


async def update_server(server_id: str, name: str, tags: list[str]) -> dict:
    """Sửa tên/tag server. TODO: PATCH {BASE_URL}/api/servers/{server_id}
    body: {"name": name, "tags": tags}"""
    raise NotImplementedError("Chưa ghép API thật — dùng MOCK_SERVERS trong main.py")


# ---------------------------------------------------------------------------
# Groups & policy — GET /api/groups, POST /api/groups,
# POST /api/groups/{group_id}/policies
# ---------------------------------------------------------------------------

async def get_groups() -> list[dict]:
    """TODO: GET {BASE_URL}/api/groups — trả về group kèm members (Inh đồng
    bộ từ Keycloak) và policies (group_server_policy)."""
    raise NotImplementedError("Chưa ghép API thật — dùng MOCK_GROUPS trong main.py")


async def save_group_server_policy(
    group_id: str,
    server_id: str,
    enabled: bool,
    max_duration_minutes: int,
    requires_approval: bool,
) -> dict:
    """TODO: POST {BASE_URL}/api/groups/{group_id}/policies
    body: {"server_id": server_id, "enabled": enabled,
           "max_duration_minutes": max_duration_minutes,
           "requires_approval": requires_approval}"""
    raise NotImplementedError("Chưa ghép API thật — dùng GROUP_SERVER_POLICY trong main.py")


# ---------------------------------------------------------------------------
# Access requests (JIT flow) — ghép chung với Inh
# ---------------------------------------------------------------------------

async def create_access_request(
    group_id: str, server_id: str, reason: str, requested_minutes: int
) -> dict:
    """TODO: POST {BASE_URL}/api/access-requests
    body: {"group_id": group_id, "server_id": server_id, "reason": reason,
           "requested_minutes": requested_minutes}
    Lưu ý: server thật có thể tự quyết định pending/approved dựa theo
    requires_approval — không cần tính lại ở phía UI như bản mock."""
    raise NotImplementedError("Chưa ghép API thật — dùng access_requests_db trong main.py")


async def list_access_requests(status: str | None = None) -> list[dict]:
    """TODO: GET {BASE_URL}/api/access-requests?status={status}"""
    raise NotImplementedError("Chưa ghép API thật — dùng access_requests_db trong main.py")


async def approve_access_request(request_id: str) -> dict:
    """TODO: POST {BASE_URL}/api/access-requests/{request_id}/approve"""
    raise NotImplementedError("Chưa ghép API thật — dùng access_requests_db trong main.py")


async def reject_access_request(request_id: str) -> dict:
    """TODO: POST {BASE_URL}/api/access-requests/{request_id}/reject"""
    raise NotImplementedError("Chưa ghép API thật — dùng access_requests_db trong main.py")


# ---------------------------------------------------------------------------
# Active grants — GET /api/grants/active, DELETE /api/grants/{id}
# ---------------------------------------------------------------------------

async def list_active_grants() -> list[dict]:
    """TODO: GET {BASE_URL}/api/grants/active"""
    raise NotImplementedError("Chưa ghép API thật — dùng access_requests_db trong main.py")


async def revoke_grant(grant_id: str, reason: str = "") -> None:
    """TODO: DELETE {BASE_URL}/api/grants/{grant_id}
    body: {"revoke_reason": reason} nếu API yêu cầu."""
    raise NotImplementedError("Chưa ghép API thật — dùng access_requests_db trong main.py")


# ---------------------------------------------------------------------------
# Helper dùng chung khi ghép thật (ví dụ mẫu, chỉnh lại theo cách Inh trả lỗi)
# ---------------------------------------------------------------------------

async def _request(method: str, path: str, **kwargs) -> dict:
    """Hàm dùng chung để gọi Control Plane, tự raise lỗi rõ ràng nếu API
    trả về mã lỗi, để main.py bắt và hiển thị banner đỏ cho người dùng."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        response = await client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()
