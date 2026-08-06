import httpx
import asyncio

GUAC_BASE = "https://52.55.177.7/api"
ADMIN_USER = "guacadmin"
ADMIN_PASS = "guacadmin"  # thử mật khẩu mặc định

async def main():
    async with httpx.AsyncClient(verify=False) as client:
        # Lấy token admin
        resp = await client.post(
            f"{GUAC_BASE}/tokens",
            data={"username": ADMIN_USER, "password": ADMIN_PASS}
        )
        print("Login status:", resp.status_code)
        if resp.status_code != 200:
            print("Response:", resp.text)
            return
        data = resp.json()
        token = data["authToken"]
        data_source = data["dataSource"]
        print(f"Token: {token[:10]}... DataSource: {data_source}")

        # Tạo user demo
        create_resp = await client.post(
            f"{GUAC_BASE}/session/data/{data_source}/users?token={token}",
            json={"username": "demo", "attributes": {}}
        )
        print("Create user status:", create_resp.status_code)
        if create_resp.status_code not in (200, 201):
            print("Create user error:", create_resp.text)
            return

        # Đặt mật khẩu demo123
        pwd_resp = await client.put(
            f"{GUAC_BASE}/session/data/{data_source}/users/demo/password?token={token}",
            json={"oldPassword": "", "newPassword": "demo123"}
        )
        print("Set password status:", pwd_resp.status_code)
        if pwd_resp.status_code == 204:
            print("✅ Đã tạo user demo / demo123 thành công!")
        else:
            print("Set password error:", pwd_resp.text)

asyncio.run(main())