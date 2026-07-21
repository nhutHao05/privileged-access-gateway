"""
PAM Gateway — Authorization & UI module
Màn "Xin quyền" (access request) + màn "Quản lý server" (chỉ Sửa tên/tag)
— bản demo dùng MOCK DATA (chưa nối API thật của Inh)

Chạy thử:
    uvicorn main:app --reload
Rồi mở trình duyệt: http://127.0.0.1:8000
"""

import uuid
from datetime import datetime, timedelta

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="PAM Gateway - Authorization & UI")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------------------------------------------------------------------
# MOCK DATA — sau này thay bằng gọi API thật của Inh (GET /api/servers,
# POST /api/access-requests, PATCH /api/servers/{id} ...). Cấu trúc field
# đặt đúng snake_case như đã chốt trong RBAC-API-Spec-Draft để lúc thay
# API thật không phải sửa template.
#
# LƯU Ý: server do Inh import từ Guacamole — UI ở đây chỉ được SỬA
# (tên, tag), KHÔNG được Thêm/Xóa. Không có route nào thêm hoặc xóa
# server trong file này.
# ---------------------------------------------------------------------------

MOCK_SERVERS = [
    {"id": "s-001", "name": "db-prod-01", "tags": ["prod", "db"]},
    {"id": "s-002", "name": "web-app-02", "tags": ["prod", "web"]},
    {"id": "s-003", "name": "staging-app-01", "tags": ["staging"]},
]

# Nhóm + thành viên — thực tế sẽ do Inh đồng bộ định kỳ từ Keycloak vào DB
# (đã chốt: UI KHÔNG gọi Keycloak trực tiếp, không có route Thêm/Xóa thành
# viên ở đây). Danh sách members chỉ để hiển thị.
MOCK_GROUPS = [
    {"id": "g-admin", "name": "Admin", "members": ["Hào", "Vinh"]},
    {"id": "g-support", "name": "Support", "members": ["Inh"]},
    {"id": "g-dev", "name": "Dev", "members": ["Nghĩa", "Sang"]},
]

# group_server_policy — đúng theo bảng trong RBAC-API-Spec-Draft.docx:
# nhóm nào được PHÉP xin quyền vào server nào, tối đa bao nhiêu phút, có
# cần duyệt hay không. Đây là chính sách của PAM Control Plane (không đồng
# bộ từ Keycloak) nên UI (mình) được sửa trực tiếp — tương ứng
# POST /api/groups/{group_id}/policies trong spec.
#
# key: group_id -> { server_id: {"max_duration_minutes": int, "requires_approval": bool} }
# Nếu server_id không có trong dict con của group -> nhóm đó KHÔNG được
# phép xin quyền vào server đó.
GROUP_SERVER_POLICY: dict[str, dict[str, dict]] = {
    "g-admin": {
        "s-001": {"max_duration_minutes": 120, "requires_approval": True},
        "s-002": {"max_duration_minutes": 120, "requires_approval": True},
        "s-003": {"max_duration_minutes": 120, "requires_approval": False},
    },
    "g-support": {
        "s-002": {"max_duration_minutes": 60, "requires_approval": True},
    },
    "g-dev": {
        "s-003": {"max_duration_minutes": 90, "requires_approval": False},
    },
}

# "DB" giả trong RAM — mất dữ liệu khi restart server, chỉ để demo UI
access_requests_db: list[dict] = []


def find_server(server_id: str) -> dict | None:
    return next((s for s in MOCK_SERVERS if s["id"] == server_id), None)


def find_group(group_id: str) -> dict | None:
    return next((g for g in MOCK_GROUPS if g["id"] == group_id), None)


def get_policy(group_id: str, server_id: str) -> dict | None:
    """Trả về policy (max_duration_minutes, requires_approval) của 1 nhóm với
    1 server, hoặc None nếu nhóm đó không được phép xin quyền vào server này."""
    return GROUP_SERVER_POLICY.get(group_id, {}).get(server_id)


def allowed_servers_for_group(group_id: str) -> list[dict]:
    """
    Danh sách server mà nhóm này ĐƯỢC PHÉP xin quyền, kèm theo policy
    (max_duration_minutes, requires_approval) để hiển thị gợi ý trên form.
    Đây chính là chỗ áp dụng group_server_policy — trước đây form "Xin
    quyền" bỏ qua bảng này, cho chọn bừa server nào cũng được.
    """
    result = []
    for s in MOCK_SERVERS:
        policy = get_policy(group_id, s["id"])
        if policy is not None:
            result.append({**s, "policy": policy})
    return result


def build_groups_view() -> list[dict]:
    """Ghép mỗi nhóm với dict chính sách (server_id -> policy) của nó."""
    return [
        {**g, "policies": GROUP_SERVER_POLICY.get(g["id"], {})}
        for g in MOCK_GROUPS
    ]


def compute_grant_status(r: dict) -> tuple[str | None, str | None]:
    """
    Tính trạng thái hiện tại của 1 request đã từng được duyệt (có expires_at).

    Trả về (status, remaining_text):
    - status: "active" (còn hiệu lực) | "expired" (đã hết giờ, scheduler thật
      của Inh sẽ tự thu hồi) | "revoked" (bị thu hồi tay qua nút demo) | None
      (request này chưa từng được duyệt, không có expires_at -> bỏ qua)
    - remaining_text: chuỗi hiển thị thời gian còn lại, chỉ có khi status
      là "active".
    """
    if r.get("status") == "revoked":
        return "revoked", None

    expires_at = r.get("expires_at")
    if not expires_at:
        return None, None

    now = datetime.now()
    if expires_at > now:
        remaining = expires_at - now
        total_seconds = int(remaining.total_seconds())
        minutes, seconds = divmod(total_seconds, 60)
        return "active", f"{minutes} phút {seconds} giây"

    return "expired", None


# ---------------------------------------------------------------------------
# Routes — Xin quyền (access requests)
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index(request: Request, group_id: str = MOCK_GROUPS[0]["id"]):
    """
    Trang chính: form xin quyền + bảng 'Yêu cầu của tôi'.

    LƯU Ý TẠM THỜI: chưa có đăng nhập thật (Vinh + Inh chưa xong JWT
    Keycloak), nên mình cho "đóng vai" 1 nhóm qua dropdown ở đầu trang
    (query param ?group_id=...) để có thể demo & test validation theo
    group_server_policy. Sau khi có JWT thật, group_id nên lấy từ user
    đang đăng nhập (thuộc nhóm nào) thay vì cho tự chọn như thế này —
    chỗ này chỉ cần thay input lấy group_id, phần validate bên dưới giữ
    nguyên.
    """
    selected_group = find_group(group_id) or MOCK_GROUPS[0]
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "groups": MOCK_GROUPS,
            "selected_group_id": selected_group["id"],
            "allowed_servers": allowed_servers_for_group(selected_group["id"]),
            "access_requests": list(reversed(access_requests_db)),
        },
    )


@app.post("/access-requests", response_class=HTMLResponse)
def create_access_request(
    request: Request,
    group_id: str = Form(...),
    server_id: str = Form(...),
    reason: str = Form(...),
    requested_minutes: int = Form(...),
):
    """
    Tương ứng POST /api/access-requests trong spec.
    HTMX gọi vào đây, nhận về đúng fragment HTML của bảng để swap vào trang
    (không reload cả trang).

    Validate theo group_server_policy trước khi tạo request:
    - Nhóm phải được phép xin quyền vào server đó (có policy).
    - requested_minutes không được vượt max_duration_minutes của policy.
    Nếu policy.requires_approval = False -> tự động approve luôn, không
    cần chờ duyệt tay (đúng theo spec, trước đây bản cũ luôn để "pending").
    """
    reason = reason.strip()
    policy = get_policy(group_id, server_id)
    error = None

    if policy is None:
        error = "Nhóm của bạn không được phép xin quyền vào server này."
    elif not reason:
        error = "Vui lòng nhập lý do xin quyền."
    elif requested_minutes <= 0:
        error = "Thời lượng phải lớn hơn 0 phút."
    elif requested_minutes > policy["max_duration_minutes"]:
        error = (
            f"Thời lượng vượt quá mức tối đa nhóm bạn được phép "
            f"({policy['max_duration_minutes']} phút)."
        )

    if error:
        return templates.TemplateResponse(
            request,
            "_request_response.html",
            {"access_requests": list(reversed(access_requests_db)), "error": error},
        )

    server = find_server(server_id)
    auto_approved = not policy["requires_approval"]
    now = datetime.now()

    new_request = {
        "id": str(uuid.uuid4())[:8],
        "server": server,
        "reason": reason,
        "requested_minutes": requested_minutes,
        "status": "approved" if auto_approved else "pending",
        "requested_at": now,
    }
    if auto_approved:
        new_request["expires_at"] = now + timedelta(minutes=requested_minutes)
    access_requests_db.append(new_request)

    success = "Đã tạo yêu cầu và tự động cấp quyền." if auto_approved else None
    return templates.TemplateResponse(
        request,
        "_request_response.html",
        {
            "access_requests": list(reversed(access_requests_db)),
            "success": success,
        },
    )


@app.post("/access-requests/{request_id}/approve", response_class=HTMLResponse)
def approve_request(request: Request, request_id: str):
    """Tương ứng POST /api/access-requests/{id}/approve — demo duyệt tay."""
    for r in access_requests_db:
        if r["id"] == request_id:
            r["status"] = "approved"
            r["expires_at"] = datetime.now() + timedelta(minutes=r["requested_minutes"])
    return templates.TemplateResponse(
        request,
        "_request_response.html",
        {"access_requests": list(reversed(access_requests_db))},
    )


@app.post("/access-requests/{request_id}/reject", response_class=HTMLResponse)
def reject_request(request: Request, request_id: str):
    """Tương ứng POST /api/access-requests/{id}/reject."""
    for r in access_requests_db:
        if r["id"] == request_id:
            r["status"] = "rejected"
    return templates.TemplateResponse(
        request,
        "_request_response.html",
        {"access_requests": list(reversed(access_requests_db))},
    )


# ---------------------------------------------------------------------------
# Routes — Quản lý server (CHỈ Sửa tên/tag — không Thêm, không Xóa)
# ---------------------------------------------------------------------------

@app.get("/servers", response_class=HTMLResponse)
def servers_page(request: Request):
    """Trang quản lý server: bảng danh sách server, có thể Sửa từng dòng."""
    return templates.TemplateResponse(
        request,
        "servers.html",
        {"servers": MOCK_SERVERS, "editing_id": None},
    )


@app.get("/servers/table", response_class=HTMLResponse)
def servers_table(request: Request):
    """
    Trả về fragment bảng server ở chế độ xem thường (không có dòng nào
    đang sửa). Dùng khi bấm nút 'Hủy' để thoát chế độ sửa.
    """
    return templates.TemplateResponse(
        request,
        "_servers_table.html",
        {"servers": MOCK_SERVERS, "editing_id": None},
    )


@app.get("/servers/{server_id}/edit-row", response_class=HTMLResponse)
def edit_server_row(request: Request, server_id: str):
    """
    Bấm nút 'Sửa' ở 1 dòng -> trả lại cả bảng, nhưng dòng có server_id này
    hiển thị dạng ô nhập (input) thay vì chữ thường.
    """
    return templates.TemplateResponse(
        request,
        "_servers_table.html",
        {"servers": MOCK_SERVERS, "editing_id": server_id},
    )


@app.post("/servers/{server_id}/edit", response_class=HTMLResponse)
def save_server_edit(
    request: Request,
    server_id: str,
    name: str = Form(""),
    tags: str = Form(""),
):
    """
    Tương ứng PATCH /api/servers/{id} trong spec (khi Inh có API thật,
    chỗ này chỉ cần thay đoạn cập nhật MOCK_SERVERS bằng lệnh gọi API).

    - name: tên server, không được để trống.
    - tags: chuỗi các tag cách nhau bởi dấu phẩy, ví dụ "prod, db".
    """
    server = find_server(server_id)
    clean_name = name.strip()

    if server is None:
        error = "Không tìm thấy server này (có thể đã bị Inh xóa/đổi bên Guacamole)."
    elif not clean_name:
        error = "Tên server không được để trống."
    else:
        error = None

    if error:
        # Giữ nguyên dòng đang ở chế độ sửa để người dùng sửa lại, kèm banner lỗi.
        return templates.TemplateResponse(
            request,
            "_servers_table.html",
            {"servers": MOCK_SERVERS, "editing_id": server_id, "error": error},
        )

    server["name"] = clean_name
    server["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

    return templates.TemplateResponse(
        request,
        "_servers_table.html",
        {"servers": MOCK_SERVERS, "editing_id": None, "success": "Đã lưu thay đổi."},
    )


# ---------------------------------------------------------------------------
# Routes — Quyền đang active (theo Sprint 2 trong kế hoạch: "UI xin quyền /
# duyệt / xem quyền đang active"). Sau này khi Inh xong scheduler thật, việc
# tự động chuyển "active" -> "expired" sẽ do backend thật làm; nút "Thu hồi
# ngay" ở đây chỉ là demo tạm, không thay thế scheduler.
# ---------------------------------------------------------------------------

def build_active_grants() -> list[dict]:
    """Lọc ra các request đã từng được duyệt, kèm trạng thái/thời gian còn lại."""
    grants = []
    for r in access_requests_db:
        status, remaining_text = compute_grant_status(r)
        if status is None:
            continue  # request này chưa từng được duyệt -> bỏ qua
        grants.append({**r, "grant_status": status, "remaining_text": remaining_text})

    # Sắp xếp: active lên trước, rồi tới expired/revoked
    order = {"active": 0, "expired": 1, "revoked": 1}
    grants.sort(key=lambda g: order.get(g["grant_status"], 2))
    return grants


@app.get("/active-grants", response_class=HTMLResponse)
def active_grants_page(request: Request):
    """Trang xem các quyền đã duyệt: còn hiệu lực bao lâu, đã hết hạn chưa."""
    return templates.TemplateResponse(
        request,
        "active_grants.html",
        {"grants": build_active_grants()},
    )


@app.get("/active-grants/table", response_class=HTMLResponse)
def active_grants_table(request: Request):
    """
    Fragment bảng, được gọi lại tự động mỗi vài giây (HTMX polling) để
    đồng hồ đếm ngược tự cập nhật mà không cần reload cả trang.
    """
    return templates.TemplateResponse(
        request,
        "_active_grants_table.html",
        {"grants": build_active_grants()},
    )


@app.post("/active-grants/{request_id}/revoke", response_class=HTMLResponse)
def revoke_grant(request: Request, request_id: str):
    """
    Demo 'Thu hồi ngay' — sau này khi có API thật của Inh, chỗ này gọi
    API thu hồi quyền trên Guacamole thay vì chỉ đổi status trong mock data.
    """
    for r in access_requests_db:
        if r["id"] == request_id:
            r["status"] = "revoked"
    return templates.TemplateResponse(
        request,
        "_active_grants_table.html",
        {"grants": build_active_grants()},
    )


# ---------------------------------------------------------------------------
# Routes — Nhóm & phân quyền (RBAC). Thành viên chỉ XEM (do Inh đồng bộ từ
# Keycloak). Chính sách "nhóm nào được vào server nào, tối đa bao lâu, có
# cần duyệt không" (group_server_policy) thì UI được chỉnh trực tiếp —
# đúng theo POST /api/groups/{group_id}/policies trong RBAC-API-Spec-Draft.
# ---------------------------------------------------------------------------

@app.get("/groups", response_class=HTMLResponse)
def groups_page(request: Request):
    """Trang Nhóm & phân quyền."""
    return templates.TemplateResponse(
        request,
        "groups.html",
        {"groups": build_groups_view(), "servers": MOCK_SERVERS},
    )


@app.post("/groups/{group_id}/servers/{server_id}/policy", response_class=HTMLResponse)
def save_group_server_policy(
    request: Request,
    group_id: str,
    server_id: str,
    enabled: str | None = Form(None),
    max_duration_minutes: int = Form(60),
    requires_approval: str | None = Form(None),
):
    """
    Tương ứng POST /api/groups/{group_id}/policies trong spec (khi Inh có
    API thật, chỗ này chỉ cần thay đoạn cập nhật GROUP_SERVER_POLICY bằng
    lệnh gọi API — request/response body giữ nguyên cấu trúc).

    - enabled: checkbox "Được phép" có tick hay không. Bỏ tick -> xóa
      chính sách (nhóm không còn được xin quyền vào server này nữa).
    - max_duration_minutes: thời lượng JIT tối đa nhóm được xin.
    - requires_approval: có cần admin duyệt hay tự động cấp.
    """
    group_policies = GROUP_SERVER_POLICY.setdefault(group_id, {})

    if enabled == "on":
        group_policies[server_id] = {
            "max_duration_minutes": max_duration_minutes,
            "requires_approval": requires_approval == "on",
        }
    else:
        group_policies.pop(server_id, None)

    return templates.TemplateResponse(
        request,
        "_groups_table.html",
        {"groups": build_groups_view(), "servers": MOCK_SERVERS},
    )
