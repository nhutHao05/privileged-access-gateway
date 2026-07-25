# PAM Gateway — Privileged Access Management Gateway

Cổng truy cập đặc quyền có kiểm soát, phân quyền JIT & ghi hình phiên truy cập (Group 4).

## 🚀 Cấu trúc dự án
- `docker-compose.yml`: Hạ tầng container toàn bộ hệ thống.
- `nginx/`: Cấu hình Nginx Reverse Proxy (TLS/HTTPS).
- `init-db/`: Script khởi tạo các Database (Keycloak, Guacamole, PAM Control).
- `docs/`: Tài liệu kiến trúc và Threat Model.

## 🛠️ Hướng dẫn khởi chạy cho đồng đội (Inh, Nghĩa, Sang)

1. **Clone Repository về máy:**
   ```bash
   git clone https://github.com/<your-username>/pam-gateway.git
   cd pam-gateway
   ```

2. **Tạo SSL Certificate tự ký cho Nginx:**
   ```bash
   mkdir -p nginx/certs
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout nginx/certs/server.key -out nginx/certs/server.crt -subj "/CN=localhost"
   ```

3. **Khởi chạy Docker Stack:**
   ```bash
   docker-compose up -d
   ```

4. **Truy cập hệ thống:**
   - **Guacamole Web App:** `https://localhost` (User/Pass mặc định: `guacadmin` / `guacadmin`)
   - **Keycloak Auth Server:** `https://localhost/auth/` (User/Pass admin: `admin` / `admin_password`)
