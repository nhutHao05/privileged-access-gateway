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
 
# "DB" giả trong RAM — mất dữ liệu khi restart server, chỉ để demo UI
access_requests_db: list[dict] = []
 
 
def find_server(server_id: str) -> dict | None:
    return next((s for s in MOCK_SERVERS if s["id"] == server_id), None)
 
 
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
def index(request: Request):
    """Trang chính: form xin quyền + bảng 'Yêu cầu của tôi'."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "servers": MOCK_SERVERS,
            "access_requests": list(reversed(access_requests_db)),
        },
    )
 
 
@app.post("/access-requests", response_class=HTMLResponse)
def create_access_request(
    request: Request,
    server_id: str = Form(...),
    reason: str = Form(...),
    requested_minutes: int = Form(...),
):
    """
    Tương ứng POST /api/access-requests trong spec.
    HTMX gọi vào đây, nhận về đúng fragment HTML của bảng để swap vào trang
    (không reload cả trang).
    """
    server = find_server(server_id)
 
    new_request = {
        "id": str(uuid.uuid4())[:8],
        "server": server,
        "reason": reason,
        "requested_minutes": requested_minutes,
        "status": "pending",
        "requested_at": datetime.now(),
    }
    access_requests_db.append(new_request)
 
    return templates.TemplateResponse(
        request,
        "_requests_table.html",
        {"access_requests": list(reversed(access_requests_db))},
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
        "_requests_table.html",
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
        "_requests_table.html",
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
    name: str = Form(...),
    tags: str = Form(""),
):
    """
    Tương ứng PATCH /api/servers/{id} trong spec (khi Inh có API thật,
    chỗ này chỉ cần thay đoạn cập nhật MOCK_SERVERS bằng lệnh gọi API).
 
    - name: tên server, không được để trống.
    - tags: chuỗi các tag cách nhau bởi dấu phẩy, ví dụ "prod, db".
    """
    server = find_server(server_id)
    if server is not None:
        clean_name = name.strip()
        if clean_name:
            server["name"] = clean_name
        server["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
 
    return templates.TemplateResponse(
        request,
        "_servers_table.html",
        {"servers": MOCK_SERVERS, "editing_id": None},
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
 