import os

# MinIO Config
MINIO_URL         = os.getenv("MINIO_URL",         "localhost:9000")
MINIO_ACCESS_KEY  = os.getenv("MINIO_ACCESS_KEY",  "admin_pam")
MINIO_SECRET_KEY  = os.getenv("MINIO_SECRET_KEY",  "super_secret_password")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "pam-audit-logs")

# Backend API của Inh - Spec đã chốt:
#   GET  {BASE_URL}/sessions/                       -> Danh sách phiên
#   POST {BASE_URL}/sessions/{session_id}/recording -> Lưu video + hash
CONTROL_PLANE_API = os.getenv("CONTROL_PLANE_API", "http://localhost:8000/audit")

# Thư mục chứa file .guac raw sinh ra từ guacd
# Mount volume chung với container guacd trong docker-compose.yml
GUAC_LOGS_DIR = os.getenv("GUAC_LOGS_DIR", "./logs")
