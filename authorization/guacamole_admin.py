"""
guacamole_admin.py — gọi Guacamole REST API để kill session đang active
khi Admin bấm Thu hồi quyền ở tab Active Grants.
"""
import httpx
import secrets_local

GUACAMOLE_BASE_URL = "https://52.55.177.7"  # root domain, KHÔNG có /auth hay /guacamole
DATA_SOURCE = "postgresql"


async def _get_admin_token() -> str:
    async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
        resp = await client.post(
            f"{GUACAMOLE_BASE_URL}/api/tokens",
            data={
                "username": secrets_local.GUACAMOLE_ADMIN_USER,
                "password": secrets_local.GUACAMOLE_ADMIN_PASSWORD,
            },
        )
        resp.raise_for_status()
        return resp.json()["authToken"]


async def kill_active_sessions_for_connection(guacamole_connection_id: str) -> int:
    """
    Kill mọi session đang active của 1 connection cụ thể (theo connectionIdentifier).
    Trả về số session đã kill. 0 nghĩa là không ai đang connect — KHÔNG phải lỗi.
    """
    token = await _get_admin_token()
    async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
        resp = await client.get(
            f"{GUACAMOLE_BASE_URL}/api/session/data/{DATA_SOURCE}/activeConnections",
            params={"token": token},
        )
        resp.raise_for_status()
        active = resp.json()  # { "<activeConnId>": {"connectionIdentifier": "...", ...}, ... }

        to_kill = [
            active_id for active_id, info in active.items()
            if str(info.get("connectionIdentifier")) == str(guacamole_connection_id)
        ]
        if not to_kill:
            return 0

        patch_body = [{"op": "remove", "path": f"/{aid}"} for aid in to_kill]
        kill_resp = await client.patch(
            f"{GUACAMOLE_BASE_URL}/api/session/data/{DATA_SOURCE}/activeConnections",
            params={"token": token},
            json=patch_body,
        )
        kill_resp.raise_for_status()
        return len(to_kill)