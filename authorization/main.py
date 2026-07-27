"""
PAM Gateway — Authorization & UI module

Bản chuẩn giữ nguyên biến `ip` khớp với Control Plane Backend của Inh.
"""

from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth

import api_client

app = FastAPI(title="PAM Gateway - Authorization & UI")


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
# Đăng nhập qua Keycloak (OIDC)
# ---------------------------------------------------------------------------

oauth = OAuth()
oauth.register(
    name="keycloak",
    server_metadata_url="https://localhost/auth/realms/pam-realm/.well-known/openid-configuration",
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
        "redirect_uri": "http://localhost:8001/auth/callback",
        "scope": "openid profile email",
        "state": state,
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
                "redirect_uri": "http://localhost:8001/auth/callback",
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

    # CHỈ lưu vài field nhỏ cần thiết, KHÔNG lưu nguyên payload JWT đầy đủ.
    # Lý do: session của app này lưu toàn bộ trong 1 cookie (không phải
    # server-side session), cookie trình duyệt giới hạn ~4KB. Payload JWT
    # gốc của Keycloak (đặc biệt realm_access/resource_access) có thể khá
    # nặng; cộng thêm access_token + id_token dễ vượt giới hạn, khiến
    # trình duyệt âm thầm không lưu cookie -> lặp vô hạn login.
    request.session["user"] = {
        "sub": userinfo.get("sub"),
        "preferred_username": userinfo.get("preferred_username"),
    }
    request.session["access_token"] = access_token
    request.session["id_token"] = id_token
    request.session["roles"] = _extract_pam_roles(userinfo)
    return RedirectResponse(url="/")


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
        "post_logout_redirect_uri": "http://localhost:8001/login",
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


def build_group_matrix(groups: list[dict], servers: list[dict], policies: list[dict]) -> list[dict]:
    policy_map = {(p["group_id"], p["server_id"]): p for p in policies}
    result = []
    for g in groups:
        server_policies = []
        for s in servers:
            pol = policy_map.get((g["id"], s["id"]))
            if pol is not None:
                server_policies.append({
                    "server_id": s["id"],
                    "server_name": s["name"],
                    "enabled": True,
                    "max_duration_minutes": pol.get("max_duration_minutes", 60),
                    "require_approval": pol.get("require_approval", True),
                })
            else:
                server_policies.append({
                    "server_id": s["id"],
                    "server_name": s["name"],
                    "enabled": False,
                    "max_duration_minutes": 60,
                    "require_approval": True,
                })
        result.append({
            "id": g["id"],
            "name": g["name"],
            "server_policies": server_policies,
        })
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


def attach_request_display(r: dict, servers: list[dict]) -> dict:
    server = next((s for s in servers if s["id"] == r.get("server_id")), None)
    return {
        **r,
        "server": server,
        "requested_minutes": r.get("requested_minutes") or r.get("duration_minutes") or 0,
        "requested_at": _parse_dt(r.get("created_at") or r.get("requested_at")),
    }


@app.get("/", response_class=HTMLResponse)
async def request_access_page(request: Request, group_id: str | None = None):
    load_error = None
    role_warning = None
    groups, servers, policies, requests_raw = [], [], [], []
    try:
        groups = await api_client.get_groups()
        servers = await api_client.get_servers()
        policies = await api_client.list_group_server_policies()
        requests_raw = await api_client.list_access_requests()
    except Exception as exc:
        load_error = _error_message(exc)

    user_roles = request.session.get("roles", [])
    my_groups = []

    if not load_error:
        # Chỉ tính role_warning khi Control Plane trả về dữ liệu bình thường —
        # nếu load_error đã xảy ra thì không có "groups" thật để mà so khớp,
        # nói "không khớp role" lúc đó sẽ gây hiểu lầm (như vụ /auth/groups/ 500).
        my_groups = resolve_groups_for_roles(groups, user_roles)

        if not user_roles:
            # Trường hợp B: tài khoản chưa được gán role PAM-* nào cả.
            role_warning = (
                "Tài khoản của bạn chưa được gán quyền (role) nào trong hệ thống. "
                "Liên hệ quản trị viên để được cấp role phù hợp "
                "(PAM-Admins / PAM-Support / PAM-Auditors)."
            )
        elif not my_groups:
            # Trường hợp C: có role nhưng tên không khớp nhóm nào bên Inh.
            role_display = ", ".join(user_roles)
            role_warning = (
                f"Không khớp được role Keycloak ({role_display}) với nhóm nào bên Control Plane. "
                "Liên hệ quản trị viên để kiểm tra lại cấu hình nhóm/role."
            )
            # Không còn fallback cho chọn nhóm thủ công (đã gỡ demo dropdown) —
            # nếu role không khớp thì chặn hẳn, không cho request tới khi nào
            # mapping được sửa đúng.

    selected_group = find_group(my_groups, group_id) if group_id else None
    if selected_group is None and my_groups:
        selected_group = my_groups[0]

    allowed_servers = (
        allowed_servers_for_group(servers, policies, selected_group["id"])
        if selected_group else []
    )
    access_requests = [attach_request_display(r, servers) for r in reversed(requests_raw)]

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "groups": my_groups,
            "selected_group_id": selected_group["id"] if selected_group else None,
            "allowed_servers": allowed_servers,
            "access_requests": access_requests,
            "load_error": load_error,
            "role_warning": role_warning,
        },
    )


@app.post("/access-requests", response_class=HTMLResponse)
async def submit_access_request(
    request: Request,
    group_id: str = Form(...),
    server_id: str = Form(...),
    reason: str = Form(...),
    requested_minutes: int = Form(60),
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

    servers = await api_client.get_servers()
    requests_raw = await api_client.list_access_requests()
    access_requests = [attach_request_display(r, servers) for r in reversed(requests_raw)]

    return templates.TemplateResponse(
        request,
        "_request_response.html",
        {"error": error, "success": success, "access_requests": access_requests},
    )


@app.post("/access-requests/{request_id}/approve", response_class=HTMLResponse)
async def approve_request_from_index(request: Request, request_id: str):
    error = None
    try:
        await api_client.review_access_request(request_id, status="approved")
    except Exception as exc:
        error = _error_message(exc)

    servers = await api_client.get_servers()
    requests_raw = await api_client.list_access_requests()
    access_requests = [attach_request_display(r, servers) for r in reversed(requests_raw)]

    return templates.TemplateResponse(
        request,
        "_request_response.html",
        {"error": error, "success": None if error else "Đã duyệt yêu cầu.", "access_requests": access_requests},
    )


@app.post("/access-requests/{request_id}/reject", response_class=HTMLResponse)
async def reject_request_from_index(request: Request, request_id: str):
    error = None
    try:
        await api_client.review_access_request(request_id, status="rejected")
    except Exception as exc:
        error = _error_message(exc)

    servers = await api_client.get_servers()
    requests_raw = await api_client.list_access_requests()
    access_requests = [attach_request_display(r, servers) for r in reversed(requests_raw)]

    return templates.TemplateResponse(
        request,
        "_request_response.html",
        {"error": error, "success": None if error else "Đã từ chối yêu cầu.", "access_requests": access_requests},
    )
# ---------------------------------------------------------------------------
# Tab 2: Quản lý server (Server Management — chỉ Edit)
# ---------------------------------------------------------------------------

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
        {"servers": servers, "editing_id": None, "error": error},
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
        {"servers": servers, "editing_id": None, "error": error},
    )


@app.get("/servers/{server_id}/edit-row", response_class=HTMLResponse)
async def edit_server_row(request: Request, server_id: str):
    error = None
    servers = []
    try:
        servers = await api_client.get_servers()
    except Exception as exc:
        error = _error_message(exc)

    return templates.TemplateResponse(
        request,
        "_servers_table.html",
        {"servers": servers, "editing_id": server_id, "error": error},
    )


@app.post("/servers/{server_id}/edit", response_class=HTMLResponse)
async def edit_server(
    request: Request,
    server_id: str,
    name: str = Form(None),
    ip: str = Form(None),
    tags: str = Form(None),
):
    error = None
    success = None
    tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    try:
        await api_client.update_server(server_id, name=name, ip=ip, tags=tags_list)
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
            "success": success,
        },
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
    return {
        **g,
        "server": server,
        "reason": reason,
        "grant_status": status,
        "remaining_text": _remaining_text(expires_at) if status == "active" else "",
    }


async def _load_grants_display() -> list[dict]:
    grants = await api_client.list_active_grants()
    servers = await api_client.get_servers()
    requests_raw = await api_client.list_access_requests()
    return [attach_grant_display(g, servers, requests_raw) for g in grants]


@app.get("/active-grants", response_class=HTMLResponse)
async def active_grants_page(request: Request):
    error = None
    grants_display = []
    try:
        grants_display = await _load_grants_display()
    except Exception as exc:
        error = _error_message(exc)
        print(f"=== [DEBUG active-grants] === {error}")

    return templates.TemplateResponse(
        request, "active_grants.html", {"grants": grants_display, "error": error},
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
        request, "_active_grants_table.html", {"grants": grants_display, "error": error},
    )


@app.post("/active-grants/{grant_id}/revoke", response_class=HTMLResponse)
async def revoke_grant_route(request: Request, grant_id: str):
    error = None
    try:
        await api_client.revoke_grant(grant_id)
    except Exception as exc:
        error = _error_message(exc)

    grants_display = []
    try:
        grants_display = await _load_grants_display()
    except Exception as exc2:
        error = error or _error_message(exc2)

    return templates.TemplateResponse(
        request, "_active_grants_table.html", {"grants": grants_display, "error": error},
    )

# ---------------------------------------------------------------------------
# Tab 4: Nhóm & phân quyền (Group-Server Policy Matrix)
# ---------------------------------------------------------------------------

@app.get("/groups", response_class=HTMLResponse)
async def groups_page(request: Request):
    error = None
    group_matrix = []
    try:
        groups = await api_client.get_groups()
        servers = await api_client.get_servers()
        policies = await api_client.list_group_server_policies()
        group_matrix = build_group_matrix(groups, servers, policies)
    except Exception as exc:
        error = _error_message(exc)

    return templates.TemplateResponse(
        request,
        "groups.html",
        {
            "groups": group_matrix,
            "error": error,
            "success": None,
        },
    )


@app.post("/groups/{group_id}/servers/{server_id}/policy", response_class=HTMLResponse)
async def save_group_server_policy(
    request: Request,
    group_id: str,
    server_id: str,
    enabled: str = Form(None),
    max_duration_minutes: str = Form("60"),
    requires_approval: str = Form(None),
):
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