"""
PAM Gateway — Authorization & UI module

Bản chuẩn giữ nguyên biến `ip` khớp với Control Plane Backend của Inh.
"""

from datetime import datetime, timezone

import httpx
import api_client
import keycloak_admin
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

import api_client

app = FastAPI(title="PAM Gateway - Authorization & UI")
GUACAMOLE_BASE_URL = "https://52.55.177.7"

# ---------------------------------------------------------------------------
# Bước B: đọc nhóm thật từ role Keycloak (realm_access.roles trong JWT)
# ---------------------------------------------------------------------------

def _extract_pam_roles(userinfo: dict) -> list[str]:
    """Lấy các role dạng PAM-* từ claim realm_access.roles trong JWT."""
    roles = (userinfo.get("realm_access") or {}).get("roles", [])
    return [r for r in roles if r.startswith("PAM-")]


def _normalize(name: str) -> str:
    return name.strip().lower().rstrip("s")


def resolve_groups_for_roles(groups: list[dict], roles: list[str]) -> list[dict]:
    """
    Khớp role Keycloak (vd 'PAM-Admins') với group thật của Inh.
    Đã xác nhận: tên group bên Inh giống hệt tên role Keycloak
    (vd group 'PAM-Admins' <-> role 'PAM-Admins'), nên so sánh trực tiếp.
    """
    matched = []
    for role in roles:
        role_norm = _normalize(role)
        for g in groups:
            if _normalize(g["name"]) == role_norm and g not in matched:
                matched.append(g)
    return matched

# ---------------------------------------------------------------------------
# Siết quyền thao tác theo role (RBAC ở tầng route) — theo khung lưu ý trong
# docs Chương 10: middleware trước đây chỉ check đăng nhập, chưa check role
# cho 3/4 tab. Quy định: PAM-Admins + PAM-Support được thao tác (duyệt/từ
# chối, sửa server, thu hồi quyền, sửa policy nhóm). PAM-Auditors và tài
# khoản chưa có role PAM-* nào chỉ được xem (read-only) ở các tab đó.
# ---------------------------------------------------------------------------

ADMIN_ROLES = {"PAM-Admins"}

def is_admin(request: Request) -> bool:
    """True nếu user có role PAM-Admins."""
    roles = request.session.get("roles", [])
    return any(r in ADMIN_ROLES for r in roles)

# ---------------------------------------------------------------------------
# Đăng nhập qua Keycloak (OIDC)
# ---------------------------------------------------------------------------

oauth = OAuth()
oauth.register(
    name="keycloak",
    server_metadata_url="https://52.55.177.7/auth/realms/pam-realm/.well-known/openid-configuration",
    client_id="pam-control-ui",
    client_kwargs={"scope": "openid profile email", "verify": False},
    # verify: False vì Keycloak đang chạy chứng chỉ SSL tự ký (self-signed),
    # giống Vinh phải dùng cờ -k trong lệnh curl.
)

# Các đường dẫn không cần đăng nhập mới vào được
PUBLIC_PATHS = ("/login", "/auth/callback", "/static", "/logout")


class AuthMiddleware(BaseHTTPMiddleware):
    """Chặn mọi trang, bắt đăng nhập trước, trừ các PUBLIC_PATHS ở trên."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(PUBLIC_PATHS):
            return await call_next(request)

        user = request.session.get("user")
        if not user:
            return RedirectResponse(url="/login")

        # Đổ token của người đang đăng nhập vào "hộp tạm" trong api_client
        # để mọi lệnh gọi Control Plane trong request này tự đính kèm token.
        api_client.current_token.set(request.session.get("access_token"))
        return await call_next(request)


# LƯU Ý THỨ TỰ: add_middleware sau cùng sẽ chạy TRƯỚC — nên phải thêm
# AuthMiddleware trước, SessionMiddleware sau, để session có sẵn khi
# AuthMiddleware kiểm tra request.session.
app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key="doi-chuoi-nay-thanh-ngau-nhien-truoc-khi-deploy-that")


def _redirect_uri(request: Request) -> str:
    """Tự lấy host đang truy cập, nhưng đảm bảo dùng localhost cho Keycloak."""
    base = str(request.base_url)
    # Thay thế 127.0.0.1 thành localhost để khớp với cấu hình Keycloak
    base = base.replace("127.0.0.1", "localhost")
    return f"{base}auth/callback"

@app.get("/login")
async def login(request: Request):
    metadata = await oauth.keycloak.load_server_metadata()
    auth_endpoint = metadata["authorization_endpoint"]
    from urllib.parse import urlencode
    import secrets
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    params = {
        "response_type": "code",
        "client_id": "pam-control-ui",
        "redirect_uri": _redirect_uri(request),
        "scope": "openid profile email",
        "state": state,
        "prompt": "login",          # 👈 Thêm dòng này
    }
    return RedirectResponse(url=f"{auth_endpoint}?{urlencode(params)}")


@app.get("/auth/callback")
async def auth_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return HTMLResponse(
            f"Không nhận được code. Params: {dict(request.query_params)}",
            status_code=400
        )

    metadata = await oauth.keycloak.load_server_metadata()
    token_endpoint = metadata["token_endpoint"]

    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _redirect_uri(request),
                "client_id": "pam-control-ui",
            },
        )

    if resp.status_code != 200:
        return HTMLResponse(
            f"<h3>Lỗi lấy token</h3><p>Status: {resp.status_code}</p><pre>{resp.text}</pre>",
            status_code=500,
        )

    token = resp.json()
    access_token = token.get("access_token", "")
    id_token = token.get("id_token", "")

    import base64 as b64, json as json_lib
    try:
        payload_part = access_token.split(".")[1]
        payload_part += "=" * (4 - len(payload_part) % 4)
        userinfo = json_lib.loads(b64.urlsafe_b64decode(payload_part))
    except Exception:
        userinfo = {}

    request.session["user"] = {
        "sub": userinfo.get("sub"),
        "preferred_username": userinfo.get("preferred_username"),
    }
    request.session["access_token"] = access_token
    request.session["id_token"] = id_token
    request.session["roles"] = _extract_pam_roles(userinfo)

    # Điều hướng đúng role
    if is_admin(request):
        return RedirectResponse(url="/")
    else:
        return RedirectResponse(url="/portal")


@app.get("/logout")
async def logout(request: Request):
    """
    Đăng xuất hoàn toàn: xoá session của app PAM Gateway,
    ĐỒNG THỜI redirect sang end_session_endpoint của Keycloak để xoá
    luôn phiên SSO. Nếu vì lý do gì đó không lấy được id_token
    (vd session cũ trước khi có thay đổi này), fallback về logout
    kiểu cũ (chỉ xoá session app) để không bị lỗi 500.
    """
    id_token = request.session.get("id_token")
    request.session.clear()

    if not id_token:
        return RedirectResponse(url="/login")

    try:
        metadata = await oauth.keycloak.load_server_metadata()
        end_session_endpoint = metadata.get("end_session_endpoint")
    except Exception:
        end_session_endpoint = None

    if not end_session_endpoint:
        return RedirectResponse(url="/login")

    from urllib.parse import urlencode
    params = {
        "id_token_hint": id_token,
        "client_id": "pam-control-ui",
        "post_logout_redirect_uri": f"{request.base_url}login",
    }
    return RedirectResponse(url=f"{end_session_endpoint}?{urlencode(params)}")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print("=== 422 VALIDATION ERROR ===")
    print(exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _error_message(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except Exception:
            detail = exc.response.text
        return f"Lỗi Control Plane ({status}): {detail}"
    if isinstance(exc, httpx.RequestError):
        return f"Không thể kết nối Control Plane: {exc}"
    return str(exc)


def build_group_matrix(groups, servers, policies):
    """
    groups: list of group dicts từ API /auth/groups/
    servers: list of server dicts từ API /servers/
    policies: list of policy dicts từ API /policy/group-server/
    Trả về list groups với mỗi group có key 'server_policies' chứa tất cả servers.
    """
    # Tạo map server_id -> server_name
    server_map = {s["id"]: s["name"] for s in servers}

    # Tạo map policy: key = (group_id, server_id) -> policy dict
    policy_map = {}
    for p in policies:
        key = (p["group_id"], p["server_id"])
        policy_map[key] = p

    result = []
    for g in groups:
        server_policies = []
        for s in servers:
            key = (g["id"], s["id"])
            if key in policy_map:
                p = policy_map[key]
                # Đã có policy -> lấy thông tin thực tế
                server_policies.append({
                    "server_id": s["id"],
                    "server_name": s["name"],
                    "enabled": True, 
                    "max_duration_minutes": p.get("max_duration_minutes", 60),
                    "require_approval": p.get("require_approval", True),
                    "allowed_actions": p.get("allowed_actions", ["connect"]),
                    "policy_id": p["id"],  # để xóa nếu cần
                })
            else:
                # Chưa có policy -> tạo policy mặc định (chưa enabled)
                server_policies.append({
                    "server_id": s["id"],
                    "server_name": s["name"],
                    "enabled": False,
                    "max_duration_minutes": 60,
                    "require_approval": True,
                    "allowed_actions": ["connect"],
                    "policy_id": None,  # chưa có
                })
        # Sắp xếp theo tên server cho dễ nhìn
        server_policies.sort(key=lambda x: x["server_name"])
        g["server_policies"] = server_policies
        result.append(g)
    return result


def get_policy(policies: list[dict], group_id: str, server_id: str) -> dict | None:
    for p in policies:
        if p["group_id"] == group_id and p["server_id"] == server_id:
            return p
    return None


# ---------------------------------------------------------------------------
# Tab 1: Xin quyền (Request Access)
# ---------------------------------------------------------------------------

def find_group(groups: list[dict], group_id: str) -> dict | None:
    return next((g for g in groups if g["id"] == group_id), None)


def allowed_servers_for_group(servers: list[dict], policies: list[dict], group_id: str) -> list[dict]:
    result = []
    for s in servers:
        pol = get_policy(policies, group_id, s["id"])
        if pol is not None:
            result.append({**s, "policy": pol})
    return result


def _parse_dt(value):
    dt = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def attach_request_display(r: dict, servers: list[dict], users: list[dict] | None = None) -> dict:
    server = next((s for s in servers if s["id"] == r.get("server_id")), None)
    guac_url = ""
    if server and server.get("guacamole_connection_id"):
        import base64
        token = f"{server['guacamole_connection_id']}\0c\0postgresql"
        encoded = base64.b64encode(token.encode()).decode()
        guac_url = f"{GUACAMOLE_BASE_URL}/#/client/{encoded}"
    requester = None
    if users:
        requester = next((u for u in users if str(u["id"]) == str(r.get("user_id"))), None)
    return {
        **r,
        "server": server,
        "requester": requester,
        "requested_minutes": r.get("requested_minutes") or r.get("duration_minutes") or 0,
        "requested_at": _parse_dt(r.get("created_at") or r.get("requested_at")),
        "guac_url": guac_url,
    }


@app.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    # Chỉ admin mới vào được
    if not is_admin(request):
        return RedirectResponse(url="/portal")

    load_error = None
    requests_raw = []
    servers = []
    users = []
    try:
        servers = await api_client.get_servers()
        requests_raw = await api_client.list_access_requests()
        users = await api_client.get_users()
    except Exception as exc:
        load_error = _error_message(exc)

    access_requests = [attach_request_display(r, servers, users) for r in reversed(requests_raw)]

    return templates.TemplateResponse(
        request,
        "admin_dashboard.html",   # Template mới cho Admin
        {
            "access_requests": access_requests,
            "load_error": load_error,
            "is_admin": True,
        },
    )


@app.post("/access-requests", response_class=HTMLResponse)
async def submit_access_request(
    request: Request,
    server_id: str = Form(...),
    reason: str = Form(...),
    requested_minutes: int = Form(60),
    group_id: str = Form(None),   # optional
):
    error = None
    success = None
    try:
        await api_client.create_access_request(
            group_id=group_id,
            server_id=server_id,
            reason=reason,
            duration_minutes=requested_minutes,
        )
        success = "Đã gửi yêu cầu xin quyền."
    except Exception as exc:
        error = _error_message(exc)

    # Lấy danh sách request của user hiện tại
    user = request.session.get("user")
    servers = await api_client.get_servers()
    requests_raw = await api_client.list_access_requests()
    my_requests = [r for r in requests_raw if r.get("user_id") == user.get("sub")] if user else []
    access_requests = [attach_request_display(r, servers) for r in reversed(my_requests)]

    # Trả về bảng dành cho user (có nút Kết nối khi approved)
    return templates.TemplateResponse(
        request,
        "_requests_table_user.html",
        {
            "error": error,
            "success": success,
            "access_requests": access_requests,
        },
    )



@app.post("/access-requests/{request_id}/approve", response_class=HTMLResponse)
async def approve_request_from_index(request: Request, request_id: str):
    can_manage = is_admin(request)
    error = None

    if not can_manage:
        error = "Bạn không có quyền (chỉ Admin)."
    else:
        try:
            await api_client.review_access_request(request_id, status="approved")
        except Exception as exc:
            error = _error_message(exc)

    servers = await api_client.get_servers()
    requests_raw = await api_client.list_access_requests()
    users = await api_client.get_users()
    access_requests = [attach_request_display(r, servers, users) for r in reversed(requests_raw)]

    return templates.TemplateResponse(
        request,
        "_request_response.html",
        {
            "error": error,
            "success": None if error else "Đã duyệt yêu cầu.",
            "access_requests": access_requests,
            "is_admin": can_manage,
        },
        status_code=403 if not can_manage else 200,
    )


@app.post("/access-requests/{request_id}/reject", response_class=HTMLResponse)
async def reject_request_from_index(request: Request, request_id: str):
    can_manage = is_admin(request)
    error = None

    if not can_manage:
        error = "Bạn không có quyền (chỉ Admin)."
    else:
        try:
            await api_client.review_access_request(request_id, status="rejected")
        except Exception as exc:
            error = _error_message(exc)

    servers = await api_client.get_servers()
    requests_raw = await api_client.list_access_requests()
    users = await api_client.get_users()
    access_requests = [attach_request_display(r, servers, users) for r in reversed(requests_raw)]

    return templates.TemplateResponse(
        request,
        "_request_response.html",
        {
            "error": error,
            "success": None if error else "Đã từ chối yêu cầu.",
            "access_requests": access_requests,
            "is_admin": can_manage,
        },
        status_code=403 if not can_manage else 200,
    )
# ---------------------------------------------------------------------------
# Tab 2: Quản lý server (Server Management — chỉ Edit)
# ---------------------------------------------------------------------------

@app.get("/access-requests/{request_id}/actions", response_class=HTMLResponse)
async def request_actions_partial(request: Request, request_id: str):
    requests_raw = await api_client.list_access_requests()
    r = next((x for x in requests_raw if str(x["id"]) == str(request_id)), None)
    return templates.TemplateResponse(
        request, "_request_actions.html", {"r": r, "is_admin": is_admin(request)}
    )


@app.get("/access-requests/{request_id}/assign-panel", response_class=HTMLResponse)
async def assign_panel_partial(request: Request, request_id: str):
    if not is_admin(request):
        return HTMLResponse("Bạn không có quyền (chỉ Admin).", status_code=403)
    groups = await api_client.get_groups()
    return templates.TemplateResponse(
        request, "_assign_panel.html", {"request_id": request_id, "groups": groups}
    )


@app.post("/access-requests/{request_id}/assign-and-approve", response_class=HTMLResponse)
async def assign_and_approve_route(
    request: Request, request_id: str, group_id: str = Form(...)
):
    can_manage = is_admin(request)
    error = None
    success = None

    if not can_manage:
        error = "Bạn không có quyền (chỉ Admin)."
    else:
        try:
            requests_raw = await api_client.list_access_requests()
            target = next((x for x in requests_raw if str(x["id"]) == str(request_id)), None)
            if target is None:
                error = "Không tìm thấy request."
            else:
                user_id = target["user_id"]
                server_id = target["server_id"]

                await api_client.assign_user_to_group(user_id, group_id)

                policies = await api_client.list_group_server_policies()
                enabled_server_ids = {
                    p["server_id"] for p in policies if str(p["group_id"]) == str(group_id)
                }
                if server_id in enabled_server_ids:
                    await api_client.review_access_request(request_id, status="approved")
                    success = "Đã gán vào group và tự động duyệt request."
                else:
                    success = (
                        "Đã gán vào group nhưng chưa tự duyệt được — cần cấp quyền server "
                        "tương ứng ở tab Nhóm & phân quyền."
                    )
        except Exception as exc:
            error = _error_message(exc)

    servers = await api_client.get_servers()
    requests_raw = await api_client.list_access_requests()
    users = await api_client.get_users()
    access_requests = [attach_request_display(x, servers, users) for x in reversed(requests_raw)]

    return templates.TemplateResponse(
        request,
        "_request_response.html",
        {
            "error": error,
            "success": success,
            "access_requests": access_requests,
            "is_admin": can_manage,
        },
        status_code=403 if not can_manage else 200,
    )


@app.get("/servers", response_class=HTMLResponse)
async def servers_page(request: Request):
    error = None
    servers = []
    try:
        servers = await api_client.get_servers()
    except Exception as exc:
        error = _error_message(exc)

    return templates.TemplateResponse(
        request,
        "servers.html",
        {"servers": servers, "editing_id": None, "error": error, "is_admin": is_admin(request)},
    )


@app.get("/servers/table", response_class=HTMLResponse)
async def servers_table_partial(request: Request):
    error = None
    servers = []
    try:
        servers = await api_client.get_servers()
    except Exception as exc:
        error = _error_message(exc)

    return templates.TemplateResponse(
        request,
        "_servers_table.html",
        {"servers": servers, "editing_id": None, "error": error, "is_admin": is_admin(request)},
    )


@app.get("/servers/{server_id}/edit-row", response_class=HTMLResponse)
async def edit_server_row(request: Request, server_id: str):
    can_manage = is_admin(request)
    error = None
    servers = []
    try:
        servers = await api_client.get_servers()
    except Exception as exc:
        error = _error_message(exc)

    if not can_manage:
        error = error or "Bạn không có quyền (chỉ Admin)."

    return templates.TemplateResponse(
        request,
        "_servers_table.html",
        {
            "servers": servers,
            # Không cho mở form sửa nếu không có quyền — Auditor bấm "Sửa"
            # (nút vốn đã ẩn ở UI) cũng chỉ nhận lại bảng chỉ-xem + báo lỗi.
            "editing_id": server_id if can_manage else None,
            "error": error,
            "is_admin": can_manage,
        },
        status_code=403 if not can_manage else 200,
    )


@app.post("/servers/{server_id}/edit", response_class=HTMLResponse)
async def edit_server(
    request: Request,
    server_id: str,
    name: str = Form(None),
    ip: str = Form(None),
    protocol: str = Form(None),
    tags: str = Form(None),
):
    can_manage = is_admin(request)
    error = None
    success = None
    tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    if not can_manage:
        error = "Bạn không có quyền (chỉ Admin)."
    else:
        try:
            await api_client.update_server(server_id, name=name, ip=ip, protocol=protocol, tags=tags_list)
            success = "Cập nhật server thành công!"
        except Exception as exc:
            error = _error_message(exc)

    servers = await api_client.get_servers()
    return templates.TemplateResponse(
        request,
        "_servers_table.html",
        {
            "servers": servers,
            "editing_id": None,
            "error": error,
            "is_admin": can_manage,
        },
        status_code=403 if not can_manage else 200,
    )


# ---------------------------------------------------------------------------
# Tab 2b: Whitelist user theo server (server_whitelist)
# ---------------------------------------------------------------------------

@app.get("/servers/{server_id}/whitelist-panel", response_class=HTMLResponse)
async def server_whitelist_panel(request: Request, server_id: str):
    """Trả về panel whitelist (danh sách user đã whitelist + form thêm) cho 1 server."""
    error = None
    whitelist = []
    users = []
    try:
        whitelist = await api_client.get_server_whitelist(server_id)
        users = await api_client.get_users()
    except Exception as exc:
        error = _error_message(exc)

    return templates.TemplateResponse(
        request,
        "_server_whitelist.html",
        {
            "server_id": server_id,
            "whitelist": whitelist,
            "users": users,
            "error": error,
            "is_admin": is_admin(request),
        },
    )


@app.post("/servers/{server_id}/whitelist", response_class=HTMLResponse)
async def add_to_whitelist_route(
    request: Request,
    server_id: str,
    user_id: str = Form(...),
):
    can_manage = is_admin(request)
    error = None
    success = None

    if not can_manage:
        error = "Bạn không có quyền (chỉ Admin)."
    else:
        try:
            await api_client.add_user_to_whitelist(server_id, user_id)
            success = "Đã thêm user vào whitelist."
        except Exception as exc:
            error = _error_message(exc)

    whitelist = []
    users = []
    try:
        whitelist = await api_client.get_server_whitelist(server_id)
        users = await api_client.get_users()
    except Exception as exc2:
        error = error or _error_message(exc2)

    return templates.TemplateResponse(
        request,
        "_server_whitelist.html",
        {
            "server_id": server_id,
            "whitelist": whitelist,
            "users": users,
            "error": error,
            "success": success,
            "is_admin": can_manage,
        },
        status_code=403 if not can_manage else 200,
    )


@app.delete("/servers/{server_id}/whitelist/{user_id}", response_class=HTMLResponse)
async def remove_from_whitelist_route(request: Request, server_id: str, user_id: str):
    can_manage = is_admin(request)
    error = None
    success = None

    if not can_manage:
        error = "Bạn không có quyền (chỉ Admin)."
    else:
        try:
            await api_client.remove_user_from_whitelist(server_id, user_id)
            success = "Đã gỡ user khỏi whitelist."
        except Exception as exc:
            error = _error_message(exc)

    whitelist = []
    users = []
    try:
        whitelist = await api_client.get_server_whitelist(server_id)
        users = await api_client.get_users()
    except Exception as exc2:
        error = error or _error_message(exc2)

    return templates.TemplateResponse(
        request,
        "_server_whitelist.html",
        {
            "server_id": server_id,
            "whitelist": whitelist,
            "users": users,
            "error": error,
            "success": success,
            "is_admin": can_manage,
        },
        status_code=403 if not can_manage else 200,
    )


# ---------------------------------------------------------------------------
# Tab 3: Quyền đang active (Active Grants)
# ---------------------------------------------------------------------------

def _remaining_text(expires_at) -> str:
    if not expires_at:
        return ""
    now = datetime.now(timezone.utc)
    total_seconds = int((expires_at - now).total_seconds())
    if total_seconds <= 0:
        return "Hết hạn"
    minutes = total_seconds // 60
    hours, minutes = divmod(minutes, 60)
    return f"{hours} giờ {minutes} phút" if hours else f"{minutes} phút"


def attach_grant_display(g: dict, servers: list[dict], requests_raw: list[dict]) -> dict:
    server = next((s for s in servers if s["id"] == g.get("server_id")), None)
    expires_at = _parse_dt(g.get("expires_at"))
    status = "active" if (expires_at is None or expires_at > datetime.now(timezone.utc)) else "expired"
    req = next((r for r in requests_raw if r.get("id") == g.get("request_id")), None)
    reason = (req or {}).get("reason") or g.get("reason") or "—"
    guac_url = ""
    if server and server.get("guacamole_connection_id"):
        import base64
        token = f"{server['guacamole_connection_id']}\0c\0postgresql"
        encoded = base64.b64encode(token.encode()).decode()
        guac_url = f"{GUACAMOLE_BASE_URL}/#/client/{encoded}"
    return {
        **g,
        "server": server,
        "reason": reason,
        "grant_status": status,
        "remaining_text": _remaining_text(expires_at) if status == "active" else "",
        "guac_url": guac_url,
    }


async def _get_current_user_id(request: Request) -> str | None:
    """Tra user_id (Control Plane) từ preferred_username lưu trong session.
    (Không dùng keycloak_sub vì GET /auth/users/ hiện chưa trả về field này.)
    """
    user_info = request.session.get("user") or {}
    username = user_info.get("preferred_username")
    if not username:
        return None
    try:
        users = await api_client.get_users()
    except Exception:
        return None
    for u in users:
        if str(u.get("username")) == str(username):
            return u.get("id")
    return None


async def _load_grants_display(current_user_id: str | None = None) -> list[dict]:
    grants = await api_client.list_active_grants()
    servers = await api_client.get_servers()
    requests_raw = await api_client.list_access_requests()

    if current_user_id:
        grants = [g for g in grants if str(g.get("user_id")) == str(current_user_id)]

    return [attach_grant_display(g, servers, requests_raw) for g in grants]


@app.get("/active-grants", response_class=HTMLResponse)
async def active_grants_page(request: Request):
    if not is_admin(request):
        return RedirectResponse(url="/portal")

    error = None
    grants_display = []
    try:
        grants_display = await _load_grants_display()
    except Exception as exc:
        error = _error_message(exc)
        print(f"=== [DEBUG active-grants] === {error}")

    return templates.TemplateResponse(
        request,
        "active_grants.html",
        {"grants": grants_display, "error": error, "is_admin": is_admin(request)},
    )


@app.get("/active-grants/table", response_class=HTMLResponse)
async def active_grants_table_partial(request: Request):
    error = None
    grants_display = []
    try:
        grants_display = await _load_grants_display()
    except Exception as exc:
        error = _error_message(exc)

    return templates.TemplateResponse(
        request,
        "_active_grants_table.html",
        {"grants": grants_display, "error": error, "is_admin": is_admin(request)},
    )


@app.post("/active-grants/{grant_id}/revoke", response_class=HTMLResponse)
async def revoke_grant_route(request: Request, grant_id: str):
    can_manage = is_admin(request)
    error = None

    if not can_manage:
        error = "Bạn không có quyền (chỉ Admin)."
    else:
        try:
            # revoke_grant_and_kill() tự lo cả revoke bên Control Plane
            # lẫn kill session Guacamole tương ứng (tra guacamole_connection_id
            # từ grant -> server), nên không cần lặp lại logic kill ở đây nữa.
            await api_client.revoke_grant_and_kill(grant_id)

        except Exception as exc:
            error = _error_message(exc)

    grants_display = []
    try:
        grants_display = await _load_grants_display()
    except Exception as exc2:
        error = error or _error_message(exc2)

    return templates.TemplateResponse(
        request,
        "_active_grants_table.html",
        {"grants": grants_display, "error": error, "is_admin": can_manage},
        status_code=403 if not can_manage else 200,
    )

# ---------------------------------------------------------------------------
# Tab 4: Nhóm & phân quyền (Group-Server Policy Matrix)
# ---------------------------------------------------------------------------

@app.get("/groups", response_class=HTMLResponse)
async def groups_page(request: Request, highlight_user: str | None = None):
    if not is_admin(request):
        return RedirectResponse(url="/portal")

    error = None
    group_matrix = []
    users = []
    try:
        groups = await api_client.get_groups()
        servers = await api_client.get_servers()
        policies = await api_client.list_group_server_policies()
        group_matrix = build_group_matrix(groups, servers, policies)
        users = await api_client.get_users()
    except Exception as exc:
        error = _error_message(exc)

    return templates.TemplateResponse(
        request,
        "groups.html",
        {
            "groups": group_matrix,
            "users": users,
            "error": error,
            "success": None,
            "is_admin": is_admin(request),
            "highlight_user": highlight_user,
        },
    )

@app.post("/groups/create", response_class=HTMLResponse)
async def create_group_route(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
):
    error = None
    success = None

    if not is_admin(request):
        error = "Bạn không có quyền (chỉ Admin)."
    else:
        try:
            # Tạo ở Keycloak trước, lấy UUID role vừa tạo để đồng bộ ID
            # sang Control Plane (cột keycloak_group_id yêu cầu NOT NULL).
            await keycloak_admin.create_realm_role(name, description or "")
            kc_id = await keycloak_admin.get_role_id_by_name(name)
            await api_client.create_group_backend(name, kc_id, description)
            success = f"Đã tạo group '{name}' thành công (Keycloak + Control Plane)."
        except Exception as exc:
            error = _error_message(exc)

    groups = await api_client.get_groups()
    servers = await api_client.get_servers()
    policies = await api_client.list_group_server_policies()

    return templates.TemplateResponse(
        request,
        "_groups_table.html",
        {
            "groups": build_group_matrix(groups, servers, policies),
            "error": error,
            "success": success,
        },
    )

@app.post("/users/create", response_class=HTMLResponse)
async def create_user_route(
    request: Request,
    username: str = Form(...),
    email: str = Form(None),
    full_name: str = Form(None),
    temp_password: str = Form(...),
):
    error = None
    success = None

    if not is_admin(request):
        error = "Bạn không có quyền (chỉ Admin)."
    else:
        try:
            kc_user_id = await keycloak_admin.create_user(
                username, email, full_name, temp_password
            )
            await api_client.create_user_backend(
                username, email, full_name, keycloak_sub=kc_user_id
            )
            success = f"Đã tạo user '{username}'. Xuống 'Danh sách User' để gán vào group."
        except Exception as exc:
            error = _error_message(exc)

    users = await api_client.get_users()
    groups = await api_client.get_groups()

    return templates.TemplateResponse(
        request,
        "_users_table.html",
        {
            "users": users,
            "groups": groups,
            "error": error,
            "success": success,
            "is_admin": is_admin(request),
        },
    )

@app.post("/users/{user_id}/assign-group", response_class=HTMLResponse)
async def assign_user_to_group_route(request: Request, user_id: str, group_id: str = Form(...)):
    if not is_admin(request):
        return JSONResponse(status_code=403, content={"error": "Chỉ Admin mới được gán user vào group."})

    error = None
    success = None
    try:
        await api_client.assign_user_to_group(user_id, group_id)
        success = "Đã gán user vào group."

        try:
            policies = await api_client.list_group_server_policies()
            enabled_server_ids = {
                p["server_id"] for p in policies if str(p["group_id"]) == str(group_id)
            }
            requests_raw = await api_client.list_access_requests()
            pending = [
                r for r in requests_raw
                if str(r.get("user_id")) == str(user_id)
                and r.get("status") == "pending"
                and r.get("server_id") in enabled_server_ids
            ]
            for r in pending:
                await api_client.review_access_request(r["id"], status="approved")
            if pending:
                success += f" Đã tự động duyệt {len(pending)} request đang chờ."
        except Exception:
            pass
    except Exception as exc:
        error = _error_message(exc)

    users = await api_client.get_users()
    groups = await api_client.get_groups()
    servers = await api_client.get_servers()
    policies = await api_client.list_group_server_policies()
    group_matrix = build_group_matrix(groups, servers, policies)

    users_html = templates.env.get_template("_users_table.html").render(
        {"request": request, "users": users, "groups": groups, "error": error, "success": success, "is_admin": True}
    )
    groups_html = templates.env.get_template("_groups_table.html").render(
        {"request": request, "groups": group_matrix, "error": None, "success": None, "is_admin": True}
    )
    combined = users_html + f'<div id="groups-table-wrapper" hx-swap-oob="true">{groups_html}</div>'
    return HTMLResponse(combined)

@app.post("/groups/{group_id}/servers/{server_id}/policy", response_class=HTMLResponse)
async def save_group_server_policy(
    request: Request,
    group_id: str,
    server_id: str,
    enabled: str = Form(None),
    max_duration_minutes: str = Form("60"),
    requires_approval: str = Form(None),
    allowed_actions: list[str] = Form([]),
):
    can_manage = is_admin(request)
    if not can_manage:
        groups = await api_client.get_groups()
        servers = await api_client.get_servers()
        policies = await api_client.list_group_server_policies()
        return templates.TemplateResponse(
            request,
            "_groups_table.html",
            {
                "groups": build_group_matrix(groups, servers, policies),
                "error": "Bạn không có quyền (chỉ Admin).",
                "success": None,
            },
            status_code=403,
        )

    error = None
    success = None
    
    try:
        duration_int = int(max_duration_minutes) if max_duration_minutes.strip() else 60
    except ValueError:
        duration_int = 60

    try:
        if enabled == "on":
            await api_client.save_group_server_policy(
                group_id=group_id,
                server_id=server_id,
                max_duration_minutes=duration_int,
                require_approval=requires_approval == "on",
                allowed_actions=allowed_actions or ["connect"],
            )
            success = "Đã lưu chính sách thành công!"
        else:
            policies = await api_client.list_group_server_policies()
            existing = get_policy(policies, group_id, server_id)
            if existing is not None:
                await api_client.delete_group_server_policy(existing["id"])
            success = "Đã thu hồi quyền của nhóm này."
    except Exception as exc:
        error = _error_message(exc)
        print(f"=== [DEBUG LỖI TỪ INH] === : {error}")

    groups = await api_client.get_groups()
    servers = await api_client.get_servers()
    policies = await api_client.list_group_server_policies()
    
    return templates.TemplateResponse(
        request,
        "_groups_table.html",
        {
            "groups": build_group_matrix(groups, servers, policies),
            "error": error,
            "success": success,
        },
        
    )

    # ... các route khác ở trên ...

@app.get("/portal", response_class=HTMLResponse)
async def user_portal(request: Request):
    if is_admin(request):
        return RedirectResponse(url="/")

    load_error = None
    servers = []
    grants_display = []
    access_requests = []

    try:
        current_user_id = await _get_current_user_id(request)

        servers = await api_client.get_servers()

        # Chỉ lấy grants của user đang đăng nhập
        grants_display = await _load_grants_display(current_user_id)

        # Chỉ lấy request của user đang đăng nhập
        requests_raw = await api_client.list_access_requests()
        if current_user_id:
            requests_raw = [
                r for r in requests_raw if str(r.get("user_id")) == str(current_user_id)
            ]
        access_requests = [attach_request_display(r, servers) for r in reversed(requests_raw)]
    except Exception as exc:
        load_error = _error_message(exc)

    return templates.TemplateResponse(
        request,
        "portal.html",
        {
            "servers": servers,
            "my_grants": grants_display,
            "access_requests": access_requests,
            "load_error": load_error,
        },
    )



@app.delete("/policy/{policy_id}")
async def delete_policy_route(request: Request, policy_id: str):
    if not is_admin(request):
        return JSONResponse(status_code=403, content={"error": "Chỉ Admin mới được xóa Policy."})
    try:
        await api_client.delete_group_server_policy(policy_id)
        # Sau khi xóa, trả về bảng mới (partial) để cập nhật UI
        groups = await api_client.get_groups()
        servers = await api_client.get_servers()
        policies = await api_client.list_group_server_policies()
        matrix = build_group_matrix(groups, servers, policies)
        return templates.TemplateResponse(
            request,
            "_groups_table.html",
            {"groups": matrix, "is_admin": is_admin(request)}
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": _error_message(exc)})

@app.delete("/groups/{group_id}")
async def delete_group_route(request: Request, group_id: str):
    if not is_admin(request):
        return JSONResponse(status_code=403, content={"error": "Chỉ Admin mới được xóa Group."})
    error = None
    try:
        await api_client.delete_group_backend(group_id)
    except Exception as exc:
        error = _error_message(exc)

    groups = await api_client.get_groups()
    servers = await api_client.get_servers()
    policies = await api_client.list_group_server_policies()
    return templates.TemplateResponse(
        request,
        "_groups_table.html",
        {
            "groups": build_group_matrix(groups, servers, policies),
            "error": error,
            "success": None if error else "Đã xóa group.",
            "is_admin": True,
        },
    )

@app.delete("/groups/{group_id}/users/{user_id}")
async def remove_user_from_group_route(request: Request, group_id: str, user_id: str):
    if not is_admin(request):
        return JSONResponse(status_code=403, content={"error": "Chỉ Admin mới được gỡ user."})
    error = None
    try:
        await api_client.remove_user_from_group(user_id, group_id)
    except Exception as exc:
        error = _error_message(exc)

    groups = await api_client.get_groups()
    servers = await api_client.get_servers()
    policies = await api_client.list_group_server_policies()
    return templates.TemplateResponse(
        request,
        "_groups_table.html",
        {
            "groups": build_group_matrix(groups, servers, policies),
            "error": error,
            "success": None if error else "Đã gỡ user khỏi group.",
            "is_admin": True,
        },
    )

def attach_audit_display(a: dict, servers: list[dict], users: list[dict]) -> dict:
    server = next((s for s in servers if s["id"] == a.get("server_id")), None)
    user = next((u for u in users if u["id"] == a.get("user_id")), None)
    return {
        **a,
        "server_name": server["name"] if server else a.get("server_id"),
        "username": user["username"] if user else a.get("user_id"),
        "started_at": _parse_dt(a.get("start_time")),
        "ended_at": _parse_dt(a.get("end_time")),
    }


@app.get("/audit-log", response_class=HTMLResponse)
async def audit_log_page(request: Request):
    if not is_admin(request):
        return RedirectResponse(url="/portal")

    error = None
    audit_display = []
    try:
        sessions = await api_client.get_audit_sessions()
        servers = await api_client.get_servers()
        users = await api_client.get_users()
        audit_display = [attach_audit_display(a, servers, users) for a in reversed(sessions)]
    except Exception as exc:
        error = _error_message(exc)

    return templates.TemplateResponse(
        request,
        "audit_log.html",
        {"audit_sessions": audit_display, "error": error, "is_admin": True},
    )


@app.get("/audit-log/table", response_class=HTMLResponse)
async def audit_log_table_partial(request: Request):
    error = None
    audit_display = []
    try:
        sessions = await api_client.get_audit_sessions()
        servers = await api_client.get_servers()
        users = await api_client.get_users()
        audit_display = [attach_audit_display(a, servers, users) for a in reversed(sessions)]
    except Exception as exc:
        error = _error_message(exc)

    return templates.TemplateResponse(
        request,
        "_audit_log_table.html",
        {"audit_sessions": audit_display, "error": error, "is_admin": True},
    )