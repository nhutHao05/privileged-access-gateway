import os
import time
import subprocess
import hashlib
import requests
from minio import Minio
from minio.error import S3Error
from config import *

# Khởi tạo MinIO Client
minio_client = Minio(
    MINIO_URL,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False # Chuyển thành True nếu MinIO dùng HTTPS
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
        # Gọi guacenc. Tham số -s chỉnh độ phân giải, -r chỉnh frame rate
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
        # Đọc theo block để không tràn RAM với file lớn
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_last_chained_hash():
    """Gọi API của Inh để lấy chained_hash của bản ghi trước đó để móc xích"""
    try:
        response = requests.get(f"{CONTROL_PLANE_API}/last-record")
        if response.status_code == 200:
            data = response.json()
            return data.get("chained_hash"), data.get("id")
    except Exception as e:
        print(f"[WARNING] Lỗi gọi API lấy last hash (có thể do server Inh chưa chạy): {e}")
    # Nếu là bản ghi đầu tiên hoặc lỗi, dùng một hash mặc định
    return "GENESIS_BLOCK_HASH_0000", None

def save_audit_record(payload):
    """Gửi toàn bộ thông tin Hash sang FastAPI của Inh để lưu vào Database"""
    try:
        response = requests.post(f"{CONTROL_PLANE_API}/save", json=payload)
        if response.status_code == 200:
            print("[INFO] Đã lưu thông tin Audit vào Database thành công.")
            return True
    except Exception as e:
        print(f"[ERROR] Lỗi gọi API lưu DB: {e}")
    return False

def process_file(guac_file_path):
    filename = os.path.basename(guac_file_path)
    session_id = filename.replace('.guac', '')
    
    # 1. Convert video
    video_path = convert_guac_to_mp4(guac_file_path)
    if not video_path:
        return
        
    # 2. Upload MinIO
    object_name = f"{session_id}.m4v"
    try:
        minio_client.fput_object(MINIO_BUCKET_NAME, object_name, video_path)
        print(f"[INFO] Uploaded {object_name} lên MinIO thành công.")
    except Exception as e:
        print(f"[ERROR] Lỗi upload MinIO: {e}")
        return

    # 3. Tính toán Hash
    file_hash = calculate_sha256(video_path)
    print(f"[INFO] File Hash: {file_hash}")
    
    # 4. Hash Chaining logic
    previous_chained_hash, previous_record_id = get_last_chained_hash()
    data_to_hash = file_hash + previous_chained_hash
    chained_hash = hashlib.sha256(data_to_hash.encode('utf-8')).hexdigest()
    print(f"[INFO] Chained Hash: {chained_hash}")
    
    # 5. Payload gửi cho Inh
    payload = {
        "session_id": session_id,
        "video_object_name": object_name,
        "file_hash": file_hash,
        "previous_record_id": previous_record_id,
        "chained_hash": chained_hash
    }
    
    if save_audit_record(payload):
        # 6. Cleanup (Chỉ xóa file local nếu đã lưu DB an toàn)
        os.remove(guac_file_path)
        os.remove(video_path)
        print(f"[INFO] Đã dọn dẹp file tạm cho session: {session_id}\n{'-'*40}")

def main():
    print("[SYSTEM] Audit Worker Bắt đầu chạy. Đang đợi file .guac...")
    ensure_bucket_exists()
    
    # Tạo thư mục log nếu chưa có
    if not os.path.exists(GUAC_LOGS_DIR):
        os.makedirs(GUAC_LOGS_DIR)

    # Vòng lặp vĩnh cửu quét thư mục
    while True:
        for filename in os.listdir(GUAC_LOGS_DIR):
            if filename.endswith(".guac"):
                file_path = os.path.join(GUAC_LOGS_DIR, filename)
                # Chú ý: Ở thực tế cần kiểm tra xem guacd đã ghi xong file chưa (VD: lsof)
                # Demo thì tạm thời giả định file đã ghi xong.
                process_file(file_path)
                
        # Nghỉ 5 giây rồi quét lại
        time.sleep(5)

if __name__ == "__main__":
    main()
