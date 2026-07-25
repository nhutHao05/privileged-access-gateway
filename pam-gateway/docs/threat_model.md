# PAM Gateway — Threat Model & Security Architecture (Bản nháp)
**Chủ sở hữu:** Vinh (Infra & Auth)

## 1. Phạm vi & Mục tiêu Bảo mật
Hệ thống Privileged Access Management (PAM) Gateway đóng vai trò làm điểm kiểm soát truy cập tập trung vào các máy chủ nội bộ.
Mục tiêu cốt lõi:
1. **Không lộ Credential thật:** Người dùng cuối không bao giờ nhìn thấy mật khẩu/SSH key thật của server target.
2. **Kiểm soát thời gian thực & JIT:** Cấp quyền ngắn hạn (Just-In-Time) và thu hồi ngay khi hết hạn.
3. **Tính toàn vẹn Audit Log:** Video ghi lại phiên truy cập phải chống chỉnh sửa (Tamper-evident hashing).

---

## 2. Phân tích Rủi ro theo Mẫu STRIDE

| Hạng mục STRIDE | Rủi ro tiềm ẩn | Biện pháp giảm thiểu (Mitigation) |
|---|---|---|
| **Spoofing** (Giả mạo) | Kẻ tấn công giả mạo danh tính user để vào server target | Bắt buộc SSO OIDC qua Keycloak + Bật Native OTP (MFA) cho mọi tài khoản. |
| **Tamper** (Chỉnh sửa) | Kẻ tấn công hoặc Admin xấu xóa/sửa file video audit log | Đặt file ghi hình ở khu vực chỉ đọc (Read-only), tự động tính SHA-256 Hash + Hash chain đẩy lên MinIO. |
| **Repudiation** (Chối bỏ) | User chối bỏ các hành động đã thực hiện trên server | Ghi video toàn bộ màn hình phiên RDP/SSH + lưu lại Audit log liên kết Keycloak ID với Guacamole Session. |
| **Information Disclosure** (Rò rỉ thông tin) | Lộ mật khẩu gốc của target server qua giao diện client | Guacamole giữ mật khẩu trong Postgres backend. Client chỉ nhận luồng stream hiển thị Canvas. Nginx bật TLS 1.3. |
| **Denial of Service** (Từ chối dịch vụ) | User giữ kết nối ngâm phiên liên tục sau khi hết thời hạn JIT | Scheduler của PAM Control Plane tự động ngắt Connection/Session chủ động qua Guacamole REST API. |
| **Elevation of Privilege** (Leo leo quyền) | User đổi thông tin kết nối để truy cập máy chủ khác | Phân quyền RBAC nghiêm ngặt, user chỉ thấy các Connection được gán hoặc cấp phép JIT tạm thời. |

---

## 3. Kiến trúc Mạng & Phân vùng Cô lập (Network Isolation)
- **Frontend Network (`pam_frontend`):** Chỉ mở port 80/443 qua Nginx Reverse Proxy.
- **Backend Network (`pam_backend`):** Chứa Keycloak, Guacamole, Postgres, Control Plane. Không expose port trực tiếp ra Internet.
- **Targets Network (`pam_targets`):** Chỉ giao tiếp duy nhất với `guacd`. Không có kết nối trực tiếp từ người dùng bên ngoài vào `pam_targets`.
