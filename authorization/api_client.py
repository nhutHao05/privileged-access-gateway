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
# Access requests (JIT flow) — field + path Inh xác nhận ngày 21-22/07:
#
# POST /access/requests/  (payload gửi lên)
#   server_id (UUID), reason (string), requested_minutes (int)
#   -- Không có group_id: Backend tự tra user_id (qua JWT sau này) -> group
#      -> group_server_policy để enforce (400 Bad Request nếu vi phạm).
#      UI vẫn giữ validate riêng (lọc server được phép, chặn vượt max phút)
#      để UX tốt hơn — Inh xác nhận đây là mô hình chuẩn "Defense in
#      Depth", 2 bên cùng check theo đúng group_server_policy, không sợ
#      lệch nhau.
#
# GET /access/requests/  (mỗi item trả về)
#   id (UUID), user_id (UUID), server_id (UUID), reason (string),
#   requested_minutes (int),
#   status ("pending" | "approved" | "rejected" | "expired"),
#   created_at (datetime)
#
# POST /access/requests/{request_id}/review  (duyệt/từ chối)
#   body: {"status": "approved"}  hoặc  {"status": "rejected"}
# ---------------------------------------------------------------------------

async def create_access_request(
    server_id: str, reason: str, requested_minutes: int
) -> dict:
    """POST {BASE_URL}/access/requests/
    body: {"server_id": server_id, "reason": reason,
           "requested_minutes": requested_minutes}
    Không truyền group_id — backend tự xác định qua user đăng nhập (JWT).
    Trả về object với field: id, user_id, server_id, reason,
    requested_minutes, status, created_at.
    Backend có thể trả 400 nếu vi phạm group_server_policy — main.py cần
    bắt lỗi này và hiển thị lại thành banner đỏ giống lỗi validate ở UI."""
    return await _request(
        "POST",
        "/access/requests/",
        json={
            "server_id": server_id,
            "reason": reason,
            "requested_minutes": requested_minutes,
        },
    )


async def list_access_requests(status: str | None = None) -> list[dict]:
    """GET {BASE_URL}/access/requests/?status={status}
    Mỗi item: id, user_id, server_id, reason, requested_minutes, status,
    created_at."""
    params = {"status": status} if status else None
    return await _request("GET", "/access/requests/", params=params)


async def review_access_request(request_id: str, status: str) -> dict:
    """POST {BASE_URL}/access/requests/{request_id}/review
    body: {"status": "approved" | "rejected"}
    Thay cho 2 hàm approve/reject riêng trước đây — Inh gộp chung 1
    endpoint "review", truyền status tương ứng."""
    return await _request(
        "POST", f"/access/requests/{request_id}/review", json={"status": status}
    )


# ---------------------------------------------------------------------------
# Active grants — Inh xác nhận: TÁCH RIÊNG hoàn toàn khỏi request.
#   - AccessRequest = "đơn xin" (lưu lịch sử: ai xin, khi nào, ai duyệt).
#   - ActiveGrant   = "thẻ ra vào" thực tế, chỉ sinh ra khi request
#     chuyển sang approved.
#
# GET /access/grants/  (mỗi item trả về)
#   id (UUID, Grant ID), request_id (UUID, trỏ ngược đơn gốc),
#   user_id (UUID), server_id (UUID),
#   granted_at (datetime), expires_at (datetime = granted_at + requested_minutes)
#
# DELETE /access/grants/{grant_id}  — thu hồi khẩn cấp
#   (Inh ghi chú: có thể là POST /access/grants/{grant_id}/revoke tùy
#   router Inh chọn cuối cùng — cần hỏi lại lúc ghép thật nếu 2 cách đều
#   không ăn.)
#
# => Khi ghép thật, main.py build màn "Quyền active" bằng list_active_grants()
#    trực tiếp (KHÔNG lọc access_requests_db theo status=="approved" như
#    bản mock hiện tại) — join server_id với get_servers() để lấy tên/tag
#    hiển thị, dùng expires_at để tính đồng hồ đếm ngược.
# ---------------------------------------------------------------------------

async def list_active_grants() -> list[dict]:
    """GET {BASE_URL}/access/grants/
    Mỗi item: id, request_id, user_id, server_id, granted_at, expires_at."""
    return await _request("GET", "/access/grants/")


async def revoke_grant(grant_id: str, reason: str = "") -> None:
    """DELETE {BASE_URL}/access/grants/{grant_id}
    Nếu Inh dùng router khác, đổi thành:
    POST {BASE_URL}/access/grants/{grant_id}/revoke"""
    await _request("DELETE", f"/access/grants/{grant_id}", json={"reason": reason} if reason else None)


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


# ---------------------------------------------------------------------------
# GHI CHÚ (cập nhật 22/07, sau khi Inh trả lời đầy đủ qua file d.docx):
#
# ĐÃ CHỐT:
# 1. group_server_policy: Backend enforce bắt buộc (400 nếu vi phạm), UI
#    vẫn giữ validate riêng cho UX — mô hình Defense in Depth, an toàn.
# 2. Approve/reject: POST /access/requests/{request_id}/review,
#    body {"status": "approved"|"rejected"}.
# 3. Active Grant tách hoàn toàn khỏi Request, đúng như dự đoán ban đầu.
#
# CÒN CẦN HỎI THÊM (chưa thấy trong file Inh gửi):
# - Path chính xác cho GET /servers, PATCH /servers/{id} (server skill vẫn
#   đang dùng path đoán "/api/servers" — CHƯA xác nhận với Inh).
# - Path cho GET /groups, POST /groups/{id}/policies (quản lý
#   group_server_policy) — cũng chưa xác nhận.
# - revoke_grant() bên dưới Inh ghi chú 2 khả năng (DELETE hoặc POST
#   .../revoke) — cần chốt lại 1 cái khi ghép thật, thử cái nào lỗi thì
#   đổi qua cái kia.
# ---------------------------------------------------------------------------
