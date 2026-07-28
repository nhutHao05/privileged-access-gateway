import os
import time
import subprocess
import hashlib
import requests
import re
from minio import Minio
from datetime import timedelta
from config import *

# Khởi tạo MinIO Client
minio_client = Minio(
    MINIO_URL,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

# ----------------------------------------------------------------
# BASE URL đã chốt với Inh:
#   GET  /audit/sessions/                        -> Xem danh sách phiên
#   POST /audit/sessions/{session_id}/recording  -> Gửi video + hash
# ----------------------------------------------------------------

def ensure_bucket_exists():
    try:
        found = minio_client.bucket_exists(MINIO_BUCKET_NAME)
        if not found:
            minio_client.make_bucket(MINIO_BUCKET_NAME)
            print(f"[INFO] Created MinIO bucket: {MINIO_BUCKET_NAME}")
    except Exception as e:
        print(f"[ERROR] Không kết nối được MinIO: {e}")


def convert_guac_to_mp4(guac_file_path):
    """Gọi guacenc để chuyển file .guac thành video .m4v"""
    print(f"[INFO] Bắt đầu convert {guac_file_path} sang MP4...")
    try:
        subprocess.run(
            ['guacenc', '-s', '1280x720', '-r', '24', guac_file_path],
            check=True
        )
        output_file = guac_file_path + '.m4v'
        if os.path.exists(output_file):
            print(f"[INFO] Convert thành công: {output_file}")
            return output_file
        return None
    except Exception as e:
        print(f"[ERROR] Lỗi convert guacenc: {e}")
        return None


def calculate_sha256(file_path):
    """Tính mã băm SHA-256 của file video"""
    print(f"[INFO] Đang tính mã băm SHA-256...")
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    result = sha256_hash.hexdigest()
    print(f"[INFO] SHA256 = {result}")
    return result


def upload_to_minio(video_path, object_name):
    """Upload file video lên MinIO bucket"""
    try:
        minio_client.fput_object(MINIO_BUCKET_NAME, object_name, video_path)
        # Tạo URL public nội bộ (nội bộ Docker network trỏ thẳng tới minio:9000)
        recording_url = f"http://{MINIO_URL}/{MINIO_BUCKET_NAME}/{object_name}"
        print(f"[INFO] Upload thành công: {object_name}")
        return recording_url
    except Exception as e:
        print(f"[ERROR] Lỗi upload MinIO: {e}")
        return None


def generate_presigned_url(object_name, expiry_minutes=15):
    """
    Sinh Presigned URL có thời hạn để UI của Nghĩa nhúng vào video player.
    Hàm này để Inh gọi từ API backend khi cần trả URL xem video cho Frontend.
    """
    try:
        url = minio_client.presigned_get_object(
            MINIO_BUCKET_NAME,
            object_name,
            expires=timedelta(minutes=expiry_minutes)
        )
        return url
    except Exception as e:
        print(f"[ERROR] Lỗi khi sinh Presigned URL: {e}")
        return None


def save_recording_to_backend(session_id, recording_file, recording_url, recording_hash):
    """
    Gọi API của Inh để lưu thông tin recording vào Database.
    Khớp đúng spec:
      POST /audit/sessions/{session_id}/recording
      Body: { recording_file, recording_url, recording_hash }
    """
    endpoint = f"{CONTROL_PLANE_API}/sessions/{session_id}/recording"
    payload = {
        "recording_file": recording_file,
        "recording_url": recording_url,
        "recording_hash": recording_hash
    }
    try:
        print(f"[INFO] Gửi metadata recording lên Backend: {endpoint}")
        response = requests.post(endpoint, json=payload, timeout=10)
        if response.status_code in [200, 201]:
            print(f"[INFO] ✅ Lưu DB thành công cho session: {session_id}")
            return True
        else:
            print(f"[ERROR] API Backend trả về lỗi {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[ERROR] Không thể kết nối Backend API: {e}")
    return False


def extract_session_id(filename):
    """
    Trích xuất session_id từ tên file .guac.
    Guacamole đặt tên file là: {session_id}.guac (hoặc chứa UUID ở đâu đó)
    Ví dụ: session_123.guac -> trả về "session_123"
            550e8400-e29b-41d4.guac -> trả về UUID đó
    """
    # Thử tìm UUID trước
    match = re.search(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        filename, re.IGNORECASE
    )
    if match:
        return match.group(0)
    # Nếu không có UUID, lấy tên file không có đuôi (VD: session_123)
    return os.path.splitext(filename)[0]


def process_file(guac_file_path):
    """Xử lý hoàn chỉnh một file .guac: convert -> upload -> hash -> lưu DB"""
    filename = os.path.basename(guac_file_path)
    session_id = extract_session_id(filename)
    print(f"\n{'='*50}")
    print(f"[INFO] Bắt đầu xử lý Session: {session_id}")

    # 1. Convert sang mp4
    video_path = convert_guac_to_mp4(guac_file_path)
    if not video_path:
        print(f"[ERROR] Bỏ qua session {session_id} do lỗi convert.")
        return

    # 2. Upload lên MinIO
    object_name = f"{session_id}.m4v"
    recording_url = upload_to_minio(video_path, object_name)
    if not recording_url:
        print(f"[ERROR] Bỏ qua session {session_id} do lỗi upload MinIO.")
        return

    # 3. Tính mã băm SHA-256 (Tamper-evident)
    recording_hash = calculate_sha256(video_path)

    # 4. Gửi metadata lên API của Inh (đúng theo spec mới)
    success = save_recording_to_backend(
        session_id=session_id,
        recording_file=object_name,
        recording_url=recording_url,
        recording_hash=recording_hash
    )

    if success:
        # 5. Cleanup: Xóa file tạm trên local sau khi đã an toàn lưu DB
        try:
            os.remove(guac_file_path)
            os.remove(video_path)
            print(f"[INFO] 🧹 Đã dọn file tạm cho session: {session_id}")
        except Exception as e:
            print(f"[WARNING] Không xóa được file tạm: {e}")
    else:
        print(f"[WARNING] Giữ lại file do lưu DB thất bại. Sẽ retry lần sau.")


def main():
    print("[SYSTEM] ====== PAM Audit Worker đang khởi động... ======")
    ensure_bucket_exists()
    if not os.path.exists(GUAC_LOGS_DIR):
        os.makedirs(GUAC_LOGS_DIR)
        print(f"[INFO] Tạo thư mục log: {GUAC_LOGS_DIR}")

    print(f"[SYSTEM] Đang theo dõi thư mục: {GUAC_LOGS_DIR}")
    print(f"[SYSTEM] Backend API URL: {CONTROL_PLANE_API}")
    print(f"[SYSTEM] MinIO URL: {MINIO_URL}\n")

    while True:
        try:
            for filename in os.listdir(GUAC_LOGS_DIR):
                if filename.endswith(".guac"):
                    file_path = os.path.join(GUAC_LOGS_DIR, filename)
                    process_file(file_path)
        except Exception as e:
            print(f"[ERROR] Lỗi vòng lặp chính: {e}")
        time.sleep(5)


if __name__ == "__main__":
    main()
