"""
Script test API của Inh dành cho Sang.
Chạy: python test_api.py

Mục đích: Kiểm tra xem API của Inh có hoạt động đúng không trước khi
          chạy toàn bộ Worker thật.

Yêu cầu: pip install requests
"""

import requests
import hashlib

# ============================================================
# ⚙️ CẤU HÌNH: Thay địa chỉ Backend của Inh vào đây
# ============================================================
BACKEND_URL = "http://localhost:8000"  # Đổi thành IP/Port backend của Inh
SESSION_ID  = "session_123"           # ID phiên giả lập để test

# ============================================================
# TEST 1: GET /audit/sessions/ — Lấy danh sách phiên
# ============================================================
def test_get_sessions():
    print("\n" + "="*55)
    print("TEST 1: GET /audit/sessions/ (Lấy danh sách phiên)")
    print("="*55)
    try:
        response = requests.get(f"{BACKEND_URL}/audit/sessions/", timeout=5)
        print(f"Status Code : {response.status_code}")
        print(f"Response    : {response.json()}")
        if response.status_code == 200:
            print("✅ PASS: API GET sessions hoạt động tốt!")
        else:
            print("❌ FAIL: API trả về lỗi, báo Inh kiểm tra lại.")
    except Exception as e:
        print(f"❌ FAIL: Không kết nối được Backend. Lỗi: {e}")
        print("👉 Gợi ý: Kiểm tra Backend của Inh đang chạy chưa?")


# ============================================================
# TEST 2: POST /audit/sessions/{session_id}/recording
#         Gửi thông tin video + hash giả lập
# ============================================================
def test_post_recording():
    print("\n" + "="*55)
    print(f"TEST 2: POST /audit/sessions/{SESSION_ID}/recording")
    print("="*55)

    # Tạo hash giả lập (đúng format SHA-256 thật)
    fake_hash = hashlib.sha256(b"fake_video_content_for_testing").hexdigest()

    payload = {
        "recording_file": f"{SESSION_ID}.mp4",
        "recording_url" : f"http://localhost:9000/pam-audit-logs/{SESSION_ID}.mp4",
        "recording_hash": fake_hash
    }

    print(f"Payload gửi đi: {payload}")

    try:
        url = f"{BACKEND_URL}/audit/sessions/{SESSION_ID}/recording"
        response = requests.post(url, json=payload, timeout=5)
        print(f"Status Code : {response.status_code}")
        print(f"Response    : {response.json()}")
        if response.status_code in [200, 201]:
            print("✅ PASS: API POST recording hoạt động tốt!")
            print("👉 Worker của Sang sẽ gọi đúng API này khi xử lý file thật.")
        else:
            print("❌ FAIL: API trả về lỗi.")
            print("👉 Báo Inh kiểm tra lại schema DB và router /audit/sessions/{id}/recording")
    except Exception as e:
        print(f"❌ FAIL: Không kết nối được Backend. Lỗi: {e}")


# ============================================================
# CHẠY TOÀN BỘ TEST
# ============================================================
if __name__ == "__main__":
    print("🚀 Bắt đầu test API Backend của Inh...")
    print(f"   Backend URL : {BACKEND_URL}")
    print(f"   Session ID  : {SESSION_ID}")
    test_get_sessions()
    test_post_recording()
    print("\n" + "="*55)
    print("✅ Hoàn thành test. Kiểm tra kết quả bên trên.")
    print("="*55)
