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

BASE_URL = "http://127.0.0.1:8000"  # URL Control Plane của Inh (theo Swagger: 127.0.0.1:8000/docs)
# *** LƯU Ý: TRÙNG PORT với UI của mình! ***
# uvicorn main:app (app của Nghĩa) mặc định cũng chạy ở port 8000. Nếu
# chạy cả 2 cùng lúc trên 1 máy để test ghép API thật, sẽ bị đá port. Khi
# đó chạy UI ở port khác, ví dụ:  uvicorn main:app --reload --port 8001
# rồi vào http://127.0.0.1:8001 để test (giữ BASE_URL ở trên trỏ đúng
# 127.0.0.1:8000 là Control Plane của Inh).
USE_MOCK = True  # TODO: đổi thành False khi bắt đầu ghép API thật


# ---------------------------------------------------------------------------
# Servers — path Inh xác nhận 22/07: base "/servers/"
# Lưu ý: server thật có thêm field "ip" (mock hiện tại của mình chỉ có
# name + tags, CHƯA có ip — cần bổ sung khi ghép). Backend hỗ trợ đủ CRUD
# (tạo/xóa được), dù trước đó nhóm chốt UI chỉ cho Sửa — cần hỏi lại
# leader/Inh xem UI có nên mở thêm nút Thêm/Xóa hay giữ nguyên quyết định
# cũ, chỉ dùng get_servers/update_server bên dưới.
# ---------------------------------------------------------------------------

async def get_servers() -> list[dict]:
    """GET {BASE_URL}/servers/ — trả list server, mỗi item có thêm field
    "ip" so với mock hiện tại (id, name, ip, tags)."""
    return await _request("GET", "/servers/")


async def get_server(server_id: str) -> dict:
    """GET {BASE_URL}/servers/{server_id} — chi tiết 1 server."""
    return await _request("GET", f"/servers/{server_id}")


async def update_server(server_id: str, name: str, ip: str, tags: list[str]) -> dict:
    """PATCH {BASE_URL}/servers/{server_id}
    body: {"name": name, "ip": ip, "tags": tags}
    (Có thêm "ip" so với bản mock trước đây — nhớ thêm ô nhập/hiển thị IP
    trên form Sửa server.)"""
    return await _request(
        "PATCH", f"/servers/{server_id}", json={"name": name, "ip": ip, "tags": tags}
    )


async def create_server(name: str, ip: str, tags: list[str]) -> dict:
    """POST {BASE_URL}/servers/ — backend hỗ trợ tạo mới, nhưng UI theo
    quyết định cũ của nhóm là KHÔNG cho Thêm. Chỉ dùng hàm này nếu sau này
    leader/nhóm đổi ý cho phép thêm server từ UI."""
    return await _request(
        "POST", "/servers/", json={"name": name, "ip": ip, "tags": tags}
    )


async def delete_server(server_id: str) -> None:
    """DELETE {BASE_URL}/servers/{server_id} — tương tự create_server,
    backend cho phép nhưng UI theo quyết định cũ là KHÔNG cho Xóa. Chỉ
    dùng nếu nhóm đổi quyết định."""
    await _request("DELETE", f"/servers/{server_id}")


# ---------------------------------------------------------------------------
# Groups & policy — path Inh xác nhận 22/07: base "/auth/" và "/policy/"
#
# GET  /auth/groups/                    — danh sách nhóm
# POST /auth/groups/                    — tạo nhóm mới
# POST /policy/assign-user-group/       — gán user vào nhóm
# GET  /policy/group-server/            — danh sách policy hiện có
# POST /policy/group-server/            — tạo/gán policy mới
#   body: {"group_id": UUID, "server_id": UUID,
#          "max_duration_minutes": int, "require_approval": bool}
#   *** LƯU Ý TÊN FIELD: "require_approval" (KHÔNG có "s") ***
#   Mock hiện tại của mình (GROUP_SERVER_POLICY, main.py) đang dùng
#   "requires_approval" (CÓ "s") — phải đổi tên field khi ghép thật, không
#   thì backend không nhận, dễ lỗi âm thầm.
# ---------------------------------------------------------------------------

async def get_groups() -> list[dict]:
    """GET {BASE_URL}/auth/groups/ — danh sách nhóm."""
    return await _request("GET", "/auth/groups/")


async def create_group(name: str) -> dict:
    """POST {BASE_URL}/auth/groups/
    body: {"name": name}"""
    return await _request("POST", "/auth/groups/", json={"name": name})


async def assign_user_to_group(user_id: str, group_id: str) -> dict:
    """POST {BASE_URL}/policy/assign-user-group/
    body: {"user_id": user_id, "group_id": group_id}"""
    return await _request(
        "POST",
        "/policy/assign-user-group/",
        json={"user_id": user_id, "group_id": group_id},
    )


async def list_group_server_policies() -> list[dict]:
    """GET {BASE_URL}/policy/group-server/ — toàn bộ policy hiện có."""
    return await _request("GET", "/policy/group-server/")


async def save_group_server_policy(
    group_id: str,
    server_id: str,
    max_duration_minutes: int,
    require_approval: bool,
) -> dict:
    """POST {BASE_URL}/policy/group-server/
    body: {"group_id": group_id, "server_id": server_id,
           "max_duration_minutes": max_duration_minutes,
           "require_approval": require_approval}
    Chú ý: field tên là "require_approval", không phải "requires_approval"
    như mock cũ."""
    return await _request(
        "POST",
        "/policy/group-server/",
        json={
            "group_id": group_id,
            "server_id": server_id,
            "max_duration_minutes": max_duration_minutes,
            "require_approval": require_approval,
        },
    )


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
# GHI CHÚ (cập nhật 22/07, sau khi Inh trả lời đầy đủ qua d.docx + tin nhắn):
#
# ĐÃ CHỐT — đủ path để ghép cả 4 màn:
# 1. group_server_policy: Backend enforce bắt buộc (400 nếu vi phạm), UI
#    vẫn giữ validate riêng cho UX — Defense in Depth, an toàn.
# 2. Approve/reject: POST /access/requests/{request_id}/review,
#    body {"status": "approved"|"rejected"}.
# 3. Active Grant tách hoàn toàn khỏi Request.
# 4. Servers: CRUD đủ ở base /servers/ — nhưng UI theo quyết định cũ của
#    nhóm CHỈ dùng get_servers() + update_server(), KHÔNG gọi
#    create_server()/delete_server() trừ khi nhóm đổi quyết định.
# 5. Groups & policy: base /auth/ (nhóm) và /policy/ (gán user, policy).
#
# CẦN LƯU Ý KHI GHÉP THẬT (dễ gây lỗi nếu bỏ qua):
# - Field tên policy là "require_approval" (không có "s") — mock cũ trong
#   main.py đang đặt tên "requires_approval" (có "s"). Không đổi tên biến
#   trong main.py/template, CHỈ đổi tên key lúc build JSON gửi đi trong
#   save_group_server_policy() ở trên (đã làm sẵn).
# - Server thật có thêm field "ip" mà mock cũ không có — cần thêm ô
#   nhập/hiển thị IP trong form Sửa server (servers.html/_servers_table.html)
#   khi ghép thật.
# - BASE_URL trùng port 8000 với UI — xem ghi chú ngay dưới BASE_URL ở đầu
#   file, nhớ đổi port UI khi chạy song song để test.
# - id thật là UUID (vd "3fa85f64-5717-4562-b3fc-2c963f66afa6"), không phải
#   chuỗi ngắn kiểu "s-001"/"g-support" như trong mock — không ảnh hưởng
#   code (đều là string) nhưng UI hiển thị id sẽ dài hơn, có thể cần rút
#   gọn khi hiển thị (vd chỉ hiện 8 ký tự đầu).
# ---------------------------------------------------------------------------
