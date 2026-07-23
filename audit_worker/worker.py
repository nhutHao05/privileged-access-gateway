import os
import time
import subprocess
import hashlib
import requests
import re
from minio import Minio
from minio.error import S3Error
from config import *

# Khởi tạo MinIO Client
minio_client = Minio(
    MINIO_URL,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

def ensure_bucket_exists():
    try:
        found = minio_client.bucket_exists(MINIO_BUCKET_NAME)
        if not found:
            minio_client.make_bucket(MINIO_BUCKET_NAME)
            print(f"[INFO] Created bucket: {MINIO_BUCKET_NAME}")
    except Exception as e:
        print(f"[ERROR] Không kết nối được MinIO: {e}")

def convert_guac_to_mp4(guac_file_path):
    print(f"[INFO] Bắt đầu convert {guac_file_path} sang MP4...")
    try:
        subprocess.run(['guacenc', '-s', '1280x720', '-r', '24', guac_file_path], check=True)
        output_file = guac_file_path + '.m4v'
        if os.path.exists(output_file):
            return output_file
        return None
    except Exception as e:
        print(f"[ERROR] Lỗi convert guacenc: {e}")
        return None

def calculate_sha256(file_path):
    print(f"[INFO] Đang tính mã băm SHA-256 cho file...")
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_last_chained_hash():
    """Gọi API của Inh để lấy chained_hash của bản ghi trước đó để móc xích"""
    try:
        # Đã đồng bộ với convention của FastAPI (router prefix)
        response = requests.get(f"{CONTROL_PLANE_API}/last")
        if response.status_code == 200:
            data = response.json()
            return data.get("chained_hash"), data.get("id")
    except Exception as e:
        print(f"[WARNING] Lỗi gọi API lấy last hash: {e}")
    return "GENESIS_BLOCK_HASH_0000", None

def save_audit_record(payload):
    """Gửi thông tin sang Backend (Inh)"""
    try:
        response = requests.post(f"{CONTROL_PLANE_API}/", json=payload)
        if response.status_code in [200, 201]:
            print("[INFO] Đã lưu thông tin Audit vào Database thành công.")
            return True
        else:
            print(f"[ERROR] API Backend trả về lỗi: {response.text}")
    except Exception as e:
        print(f"[ERROR] Lỗi gọi API lưu DB: {e}")
    return False

def extract_grant_id(filename):
    """
    Trích xuất grant_id (UUID) từ tên file.
    Giả định Inh/Vinh cấu hình Guacamole đặt tên file log là: {grant_id}.guac
    Ví dụ: 550e8400-e29b-41d4-a716-446655440000.guac
    """
    # Dùng regex để tìm chuỗi UUID
    match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', filename, re.IGNORECASE)
    if match:
        return match.group(0)
    return None

def process_file(guac_file_path):
    filename = os.path.basename(guac_file_path)
    
    grant_id = extract_grant_id(filename)
    if not grant_id:
        print(f"[WARNING] Bỏ qua file {filename} vì không chứa Grant ID hợp lệ.")
        return
    
    # 1. Convert video
    video_path = convert_guac_to_mp4(guac_file_path)
    if not video_path:
        return
        
    # 2. Upload MinIO
    object_name = f"{grant_id}.m4v"
    try:
        minio_client.fput_object(MINIO_BUCKET_NAME, object_name, video_path)
        print(f"[INFO] Uploaded {object_name} lên MinIO thành công.")
    except Exception as e:
        print(f"[ERROR] Lỗi upload MinIO: {e}")
        return

    # 3. Tính toán Hash
    file_hash = calculate_sha256(video_path)
    
    # 4. Hash Chaining logic
    previous_chained_hash, previous_record_id = get_last_chained_hash()
    data_to_hash = file_hash + previous_chained_hash
    chained_hash = hashlib.sha256(data_to_hash.encode('utf-8')).hexdigest()
    
    # 5. Payload gửi cho Inh (Điều chỉnh khớp với schema UUID)
    payload = {
        "grant_id": grant_id,
        "video_object_name": object_name,
        "file_hash": file_hash,
        "previous_record_id": previous_record_id,
        "chained_hash": chained_hash
    }
    
    if save_audit_record(payload):
        # 6. Cleanup 
        os.remove(guac_file_path)
        os.remove(video_path)
        print(f"[INFO] Đã dọn dẹp file tạm cho grant: {grant_id}\n{'-'*40}")

def main():
    print("[SYSTEM] Audit Worker Bắt đầu chạy...")
    ensure_bucket_exists()
    if not os.path.exists(GUAC_LOGS_DIR):
        os.makedirs(GUAC_LOGS_DIR)

    while True:
        for filename in os.listdir(GUAC_LOGS_DIR):
            if filename.endswith(".guac"):
                file_path = os.path.join(GUAC_LOGS_DIR, filename)
                process_file(file_path)
        time.sleep(5)

if __name__ == "__main__":
    main()
