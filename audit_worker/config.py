import os

# MinIO Config
MINIO_URL = os.getenv("MINIO_URL", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin_pam")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "super_secret_password")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "pam-audit-logs")

# API Config (FastAPI của Inh)
# Thay URL này bằng IP/Port thật của container backend khi chạy Docker
CONTROL_PLANE_API = os.getenv("CONTROL_PLANE_API", "http://localhost:8000/api/v1/audit")

# Folder Config (Thư mục chứa file .guac sinh ra từ guacd)
GUAC_LOGS_DIR = os.getenv("GUAC_LOGS_DIR", "./logs")
