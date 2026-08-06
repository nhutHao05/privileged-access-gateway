import httpx
import asyncio

GUAC_BASE = "https://52.55.177.7/api"
ADMIN_USER = "guacadmin"
ADMIN_PASS = "guacadmin"

async def main():
    # Lấy admin token
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            f"{GUAC_BASE}/tokens",
            data={"username": ADMIN_USER, "password": ADMIN_PASS}
        )
        if resp.status_code != 200:
            print("❌ Không lấy được token admin Guacamole:", resp.text)
            return
        data = resp.json()
        token = data["authToken"]
        data_source = data["dataSource"]
        print(f"✅ Đã lấy admin token: {data_source}")

        # Tạo user mới (ví dụ: 'demo')
        new_user = "demo"
        new_pass = "demo123"
        create_url = f"{GUAC_BASE}/session/data/{data_source}/users?token={token}"
        create_resp = await client.post(create_url, json={
            "username": new_user,
            "attributes": {
                "disabled": "",
                "expired": "",
                "access-window-start": "",
                "access-window-end": "",
                "valid-from": "",
                "valid-until": "",
                "timezone": ""
            }
        })
        if create_resp.status_code not in (200, 201):
            print("❌ Tạo user thất bại:", create_resp.text)
            return
        print(f"✅ Đã tạo user '{new_user}'")

        # Đặt mật khẩu cho user mới
        pwd_url = f"{GUAC_BASE}/session/data/{data_source}/users/{new_user}/password?token={token}"
        pwd_resp = await client.put(pwd_url, json={
            "oldPassword": "",
            "newPassword": new_pass
        })
        if pwd_resp.status_code == 204:
            print(f"✅ Đã đặt mật khẩu '{new_pass}' cho user '{new_user}'")
        else:
            print("❌ Đặt mật khẩu thất bại:", pwd_resp.text)

asyncio.run(main())