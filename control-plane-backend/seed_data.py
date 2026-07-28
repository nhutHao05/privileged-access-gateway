import uuid
import os
from app.core.database import SessionLocal  # Import SessionLocal từ DB config của ní
from app.models.auth_rbac import Group, Server  # Kiểm tra đúng đường dẫn import Model Server của ní

def seed_initial_data():
    db = SessionLocal()
    try:
        print("🌱 Đang seed dữ liệu hạ tầng từ Vinh...")

        # 1. Seed 3 Groups chuẩn từ Keycloak
        groups = ["PAM-Admins", "PAM-Support", "PAM-Auditors"]
        for g_name in groups:
            existing = db.query(Group).filter(Group.name == g_name).first()
            if not existing:
                db.add(Group(id=uuid.uuid4(), keycloak_group_id=uuid.uuid4(), name=g_name))
                print(f"  + Added Group: {g_name}")

        # 2. Seed 2 Target Servers do Vinh cung cấp
        servers = [
            {
                "name": "Linux SSH Server",
                "ip": "target_linux_ssh",
                "port": 22,
                "protocol": "ssh",
                "guacamole_connection_id": "1"
            },
            {
                "name": "Desktop GUI VNC",
                "ip": "target_vnc",
                "port": 5900,
                "protocol": "vnc",
                "guacamole_connection_id": "2"
            }
        ]
        for s in servers:
            existing = db.query(Server).filter(Server.ip == s["ip"]).first()
            if not existing:
                db.add(Server(id=uuid.uuid4(), **s))
                print(f"  + Added Server: {s['name']} ({s['ip']})")

        db.commit()
        print("✅ Seed dữ liệu thành công rực rỡ!")
    except Exception as e:
        db.rollback()
        print(f"❌ Lỗi khi seed dữ liệu: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_initial_data()