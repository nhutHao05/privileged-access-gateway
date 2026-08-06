"""
keycloak_admin.py — Helper gọi Keycloak Admin API để quản lý
Realm Roles (dùng làm "Group" cho PAM) và User.

Lưu ý: PAM-Admins/PAM-Support/... là REALM ROLES trong Keycloak,
không phải Groups (đã xác nhận không có Groups nào được dùng).
Vì vậy "Tạo Group" ở UI PAM Gateway thực chất là tạo 1 Realm Role.
"""

import httpx

from secrets_local import KEYCLOAK_ADMIN_PASSWORD

KEYCLOAK_BASE_URL = "https://52.55.177.7/auth"
KEYCLOAK_ADMIN_REALM = "master"       # realm dùng để đăng nhập admin console
KEYCLOAK_TARGET_REALM = "pam-realm"   # realm thật của dự án
KEYCLOAK_ADMIN_USERNAME = "admin"


async def get_admin_token() -> str:
    """Lấy access token admin bằng grant_type=password, client admin-cli."""
    url = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_ADMIN_REALM}/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": KEYCLOAK_ADMIN_USERNAME,
        "password": KEYCLOAK_ADMIN_PASSWORD,
    }
    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        resp = await client.post(url, data=data)
        resp.raise_for_status()
        return resp.json()["access_token"]


async def create_realm_role(name: str, description: str = "") -> None:
    """Tạo 1 Realm Role mới trong pam-realm (vd 'PAM-DevOps')."""
    token = await get_admin_token()
    url = f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_TARGET_REALM}/roles"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"name": name, "description": description}

    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 409:
            raise RuntimeError(f"Role '{name}' đã tồn tại trong Keycloak.")
        resp.raise_for_status()


async def delete_realm_role(name: str) -> None:
    """Xóa 1 Realm Role theo tên."""
    token = await get_admin_token()
    url = f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_TARGET_REALM}/roles/{name}"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        resp = await client.delete(url, headers=headers)
        if resp.status_code != 404:
            resp.raise_for_status()


async def list_realm_roles() -> list[dict]:
    """Lấy danh sách toàn bộ Realm Roles (để hiển thị / kiểm tra trùng tên)."""
    token = await get_admin_token()
    url = f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_TARGET_REALM}/roles"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

async def get_role_id_by_name(name: str) -> str:
    """Lấy UUID nội bộ của 1 Realm Role theo tên (Keycloak tự sinh khi tạo role)."""
    token = await get_admin_token()
    url = f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_TARGET_REALM}/roles/{name}"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()["id"]

async def create_user(
    username: str,
    email: str | None,
    full_name: str | None,
    temp_password: str,
) -> str:
    """
    Tạo User mới trong Keycloak, password tạm bắt buộc đổi ở lần
    đăng nhập đầu (đúng thông lệ PAM — không dùng password cố định).
    Trả về UUID nội bộ Keycloak của user vừa tạo.
    """
    token = await get_admin_token()
    url = f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_TARGET_REALM}/users"
    headers = {"Authorization": f"Bearer {token}"}

    first_name, last_name = "", ""
    if full_name:
        parts = full_name.strip().split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

    payload = {
        "username": username,
        "email": email or None,
        "firstName": first_name or None,
        "lastName": last_name or None,
        "enabled": True,
        "credentials": [
            {"type": "password", "value": temp_password, "temporary": True}
        ],
    }

    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 409:
            raise RuntimeError(f"Username '{username}' đã tồn tại trong Keycloak.")
        resp.raise_for_status()
        # Keycloak trả UUID user mới trong header Location, không trong body
        location = resp.headers.get("Location", "")
        return location.rstrip("/").split("/")[-1]


async def assign_realm_role_to_user(keycloak_user_id: str, role_name: str) -> None:
    """Gán 1 Realm Role (vd 'PAM-Support') cho user theo UUID."""
    token = await get_admin_token()
    role_id = await get_role_id_by_name(role_name)
    url = (
        f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_TARGET_REALM}"
        f"/users/{keycloak_user_id}/role-mappings/realm"
    )
    headers = {"Authorization": f"Bearer {token}"}
    payload = [{"id": role_id, "name": role_name}]

    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()