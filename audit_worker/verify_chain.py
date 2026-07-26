import hashlib
import requests
from config import CONTROL_PLANE_API

def verify_entire_chain():
    print("[SYSTEM] Bắt đầu kiểm tra toàn vẹn dữ liệu (Hash-chain Verification)...")
    try:
        # Gọi API của Inh để lấy toàn bộ log, sắp xếp theo ID tăng dần
        response = requests.get(f"{CONTROL_PLANE_API}/all-records")
        if response.status_code != 200:
            print(f"[ERROR] Không thể lấy dữ liệu từ API của Inh: {response.text}")
            return False
            
        records = response.json()
        if not records:
            print("[INFO] Database trống, chưa có bản ghi Audit nào.")
            return True

        previous_chained_hash = "GENESIS_BLOCK_HASH_0000"
        
        for record in records:
            record_id = record.get('id')
            file_hash = record.get('file_hash')
            stored_chained_hash = record.get('chained_hash')
            
            # Băm lại dữ liệu để kiểm tra (SHA256 của file_hash + previous_chained_hash)
            expected_data = file_hash + previous_chained_hash
            expected_hash = hashlib.sha256(expected_data.encode('utf-8')).hexdigest()
            
            # So sánh với Hash đang lưu trong DB
            if expected_hash != stored_chained_hash:
                print("\n=======================================================")
                print("🚨 CẢNH BÁO ĐỎ: PHÁT HIỆN SỰ CỐ GIẢ MẠO DỮ LIỆU! 🚨")
                print(f"👉 Chuỗi Hash bị đứt tại Bản ghi ID: {record_id}")
                print(f"- Mã băm lưu trong DB (Bị lỗi) : {stored_chained_hash}")
                print(f"- Mã băm thực tế cần phải có    : {expected_hash}")
                print("=======================================================\n")
                return False
                
            previous_chained_hash = stored_chained_hash
            
        print("[SUCCESS] 100% bản ghi hợp lệ. Chuỗi Hash-chain nguyên vẹn.")
        return True

    except Exception as e:
        print(f"[ERROR] Lỗi trong quá trình Verify: {e}")
        return False

if __name__ == "__main__":
    verify_entire_chain()
