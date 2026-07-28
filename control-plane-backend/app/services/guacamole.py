import httpx
from typing import Tuple, Optional
from app.core.config import settings

class GuacamoleClient:
    async def get_admin_token(self) -> Tuple[Optional[str], str]:
        """Lấy Token đăng nhập Admin của Guacamole qua REST API và trả về (token, data_source)"""
        base_url = settings.GUACAMOLE_BASE_URL.rstrip('/')
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{base_url}/tokens",
                    data={
                        "username": settings.GUACAMOLE_ADMIN_USER,
                        "password": settings.GUACAMOLE_ADMIN_PASS
                    },
                    timeout=15.0
                )
                if response.status_code == 200:
                    data = response.json()
                    token = data.get("authToken")
                    data_source = data.get("dataSource") or getattr(settings, "GUACAMOLE_PROVIDER", "postgresql")
                    return token, data_source
                
                print(f"❌ [GUAC-API] Lấy token thất bại! Status code: {response.status_code} - Body: {response.text}")
                return None, "postgresql"
            except Exception as e:
                print(f"❌ [GUAC-API] Không thể kết nối tới Guacamole Server tại {base_url}. Lỗi [{type(e).__name__}]: {e}")
                return None, "postgresql"

    async def ensure_user_exists(self, client: httpx.AsyncClient, token: str, data_source: str, username: str) -> bool:
        """Kiểm tra xem User đã tồn tại trong Guacamole chưa. Nếu chưa -> Tự động tạo mới."""
        base_url = settings.GUACAMOLE_BASE_URL.rstrip('/')
        user_url = f"{base_url}/session/data/{data_source}/users/{username}?token={token}"
        
        try:
            res = await client.get(user_url, timeout=5.0)
            if res.status_code == 200:
                return True
            elif res.status_code == 404:
                print(f"ℹ️ [GUAC-API] User '{username}' chưa có trong Guacamole, đang tự động khởi tạo...")
                create_url = f"{base_url}/session/data/{data_source}/users?token={token}"
                create_res = await client.post(
                    create_url,
                    json={"username": username, "attributes": {}},
                    timeout=15.0
                )
                if create_res.status_code in (200, 201, 204):
                    print(f"🟢 [GUAC-API] Đã tự động tạo User '{username}' trên Guacamole DB thành công!")
                    return True
                else:
                    print(f"⚠️ [GUAC-API] Không thể tạo User '{username}' trên Guacamole: HTTP {create_res.status_code} - {create_res.text}")
                    return False
        except Exception as e:
            print(f"⚠️ [GUAC-API] Lỗi khi kiểm tra/tạo User '{username}': {e}")
        return True

    async def grant_connection_access(self, username: str, connection_id: str) -> bool:
        """Cấp quyền truy cập Connection cho User trên Guacamole thật"""
        if not str(connection_id).isdigit():
            print(f"❌ [GUAC-API] connection_id '{connection_id}' không hợp lệ! Guacamole yêu cầu Connection ID phải là dạng số (ví dụ: '1', '2').")
            return False

        token, data_source = await self.get_admin_token()
        
        if not token:
            print(f"❌ [GUAC-API] Hủy cấp quyền vì không lấy được Token Admin từ Guacamole!")
            return False

        base_url = settings.GUACAMOLE_BASE_URL.rstrip('/')
        
        async with httpx.AsyncClient() as client:
            # 1. Đảm bảo User đã tồn tại trong Guacamole
            await self.ensure_user_exists(client, token, data_source, username)

            # 2. Gọi API PATCH để thêm quyền connectionPermissions
            url = f"{base_url}/session/data/{data_source}/users/{username}/permissions?token={token}"
            patch_data = [
                {
                    "op": "add",
                    "path": f"/connectionPermissions/{str(connection_id)}",
                    "value": "READ"
                }
            ]
            
            try:
                res = await client.patch(url, json=patch_data, timeout=15.0)
                if res.status_code in (200, 204):
                    print(f"🟢 [GUAC-API] Đã cấp quyền xem máy ID '{connection_id}' cho user '{username}' thành công!")
                    return True
                
                print(f"❌ [GUAC-API] Cấp quyền thất bại! HTTP Status: {res.status_code} - Body: {res.text}")
                return False
            except Exception as e:
                print(f"❌ [GUAC-API] Lỗi kết nối khi gửi patch cấp quyền: {e}")
                return False

    async def revoke_connection_access(self, username: str, connection_id: str) -> bool:
        """Thu hồi quyền khi APScheduler quét thấy hết hạn JIT"""
        token, data_source = await self.get_admin_token()
        
        if not token:
            print(f"❌ [GUAC-API] Hủy thu hồi quyền vì không lấy được Token Admin từ Guacamole!")
            return False

        base_url = settings.GUACAMOLE_BASE_URL.rstrip('/')
        url = f"{base_url}/session/data/{data_source}/users/{username}/permissions?token={token}"
        patch_data = [
            {
                "op": "remove",
                "path": f"/connectionPermissions/{str(connection_id)}",
                "value": "READ"
            }
        ]
        
        async with httpx.AsyncClient() as client:
            try:
                res = await client.patch(url, json=patch_data, timeout=15.0)
                if res.status_code in (200, 204):
                    print(f"🔴 [AUTO-REVOKE] Đã tự động thu hồi quyền máy ID '{connection_id}' của user '{username}' thành công!")
                    return True
                
                print(f"❌ [GUAC-API] Thu hồi quyền thất bại! HTTP Status: {res.status_code} - Body: {res.text}")
                return False
            except Exception as e:
                print(f"❌ [GUAC-API] Lỗi kết nối khi gửi patch thu hồi quyền: {e}")
                return False

# Singleton instance
guac_client = GuacamoleClient()