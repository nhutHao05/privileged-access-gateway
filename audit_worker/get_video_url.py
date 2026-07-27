from minio import Minio
from datetime import timedelta
from config import MINIO_URL, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET_NAME

# Khởi tạo MinIO Client
minio_client = Minio(
    MINIO_URL,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

def generate_presigned_url(object_name, expiry_minutes=15):
    """
    Hàm sinh ra một đường link (URL) tạm thời để xem video từ MinIO.
    """
    try:
        url = minio_client.presigned_get_object(
            MINIO_BUCKET_NAME, 
            object_name, 
            expires=timedelta(minutes=expiry_minutes)
        )
        print(f"[SUCCESS] Đã tạo Presigned URL (Hiệu lực {expiry_minutes} phút) cho file {object_name}")
        return url
    except Exception as e:
        print(f"[ERROR] Lỗi khi sinh URL từ MinIO: {e}")
        return None
