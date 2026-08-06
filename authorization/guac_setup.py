import httpx
import asyncio

GUAC_BASE = "http://localhost:8080/guacamole/api"   # gọi từ bên trong container

async def main():
    async with httpx.AsyncClient() as client:
        # 1. Lấy token admin (dùng guacadmin/guacadmin mặc định)
        resp = await client.post(
            f"{GUAC_BASE}/tokens",
            data={"username": "guacadmin", "password": "guacadmin"}
        )
        if resp.status_code != 200:
            print("❌ Không lấy được token:", resp.text)
            return
        data = resp.json()
        token = data["authToken"]
        ds = data["dataSource"]
        print(f"✅ Token: {token[:10]}... | DataSource: {ds}")

        # 2. Tạo user mới tên 'admin' (hoặc tên khác bạn muốn)
        user_name = "admin"
        user_pass = "admin123"
        create_resp = await client.post(
            f"{GUAC_BASE}/session/data/{ds}/users?token={token}",
            json={"username": user_name, "attributes": {}}
        )
        if create_resp.status_code not in (200, 201):
            print("❌ Tạo user thất bại:", create_resp.text)
            return

        # 3. Đặt mật khẩu
        pwd_resp = await client.put(
            f"{GUAC_BASE}/session/data/{ds}/users/{user_name}/password?token={token}",
            json={"oldPassword": "", "newPassword": user_pass}
        )
        if pwd_resp.status_code == 204:
            print(f"✅ Đã tạo user '{user_name}' với mật khẩu '{user_pass}'")
        else:
            print("❌ Đặt mật khẩu thất bại:", pwd_resp.text)

asyncio.run(main())