# 🐳 Hướng dẫn ghép Docker cho Vinh (Infra)

Vinh thêm đoạn cấu hình service này vào file `docker-compose.yml` chính của nhóm nhé:

```yaml
  control-plane-backend:
    build:
      context: ./control-plane-backend
      dockerfile: Dockerfile
    container_name: pam_control_backend
    env_file:
      - ./control-plane-backend/.env.docker
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - guacamole
      - keycloak
    restart: always
```

### 📌 Ghi chú khi khởi chạy lần đầu:
1. **Chạy Alembic Migration (tạo bảng DB):**
   ```bash
   docker exec -it pam_control_backend alembic upgrade head
   ```

2. **Chạy Seed Data (nạp 3 Group & 2 Target Server mẫu):**
   ```bash
   docker exec -it pam_control_backend python seed_data.py
   ```
