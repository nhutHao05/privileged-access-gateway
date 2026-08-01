**TÀI LIỆU KỸ THUẬT\
HỆ THỐNG PAM GATEWAY**

*Privileged Access Management\
Just-In-Time (JIT) Access Control*

Phiên bản: 1.0\
Ngày cập nhật: 30/07/2026

**Nhóm thực hiện:**

-   Bùi Tấn Inh --- Control Plane Backend (FastAPI, Database, Keycloak
    OIDC, Guacamole REST API)

-   Phạm Quốc Vinh --- Hạ tầng & Xác thực (Docker Compose, Nginx/TLS,
    Keycloak, Guacamole)

-   Khưu Đoàn Nghĩa --- Phân quyền & Giao diện (RBAC, Request/Approval
    UI, Admin Dashboard)

-   Lê Võ Phước Sang --- Kiểm toán & Ghi hình (guacenc → mp4, MinIO
    Storage, SHA-256 Hash Chain)

# MỤC LỤC

> Chương 1: Giới thiệu & Bối cảnh
>
> Chương 2: Kiến trúc Hệ thống
>
> Chương 3: Control Plane Backend (FastAPI)
>
> Chương 4: Thiết kế Cơ sở Dữ liệu
>
> Chương 5: Tích hợp Keycloak OIDC
>
> Chương 6: Tích hợp Apache Guacamole REST API
>
> Chương 7: Luồng JIT Access & Tự động Thu hồi
>
> Chương 8: Hệ thống Kiểm toán & Ghi hình (Audit Trail)
>
> Chương 9: Hạ tầng & Docker Compose
>
> Chương 10: Giao diện Người dùng & RBAC UI
>
> Chương 11: Hướng dẫn Triển khai & Vận hành
>
> Chương 12: Kịch bản Demo Nghiệm thu
>
> Phụ lục: API Reference

# Chương 1: Giới thiệu & Bối cảnh

## 1.1. Đặt vấn đề

Trong môi trường doanh nghiệp, việc quản lý truy cập vào các máy chủ nội
bộ (Server Linux SSH, Desktop VNC, Windows RDP) đang gặp nhiều rủi ro
nghiêm trọng:

-   Lộ mật khẩu gốc (Credential Exposure): Nhân viên vận hành phải biết
    và nhập trực tiếp mật khẩu root/admin để SSH hoặc VNC vào server,
    dẫn đến nguy cơ rò rỉ credential.

-   Quyền truy cập vĩnh viễn (Standing Privileges): Một khi được cấp
    quyền SSH, nhân viên giữ quyền đó mãi mãi cho đến khi bị thu hồi thủ
    công --- vi phạm nguyên tắc Least Privilege.

-   Không có nhật ký kiểm toán (Audit Gap): Không ghi lại ai đã làm gì
    trên server, khi nào, trong bao lâu.

## 1.2. Giải pháp: PAM Gateway

Hệ thống PAM Gateway được thiết kế theo mô hình Zero Trust và
Just-In-Time (JIT) Access Control nhằm giải quyết triệt để các rủi ro
trên:

  -----------------------------------------------------------------------
  **Rủi ro**                          **Giải pháp PAM Gateway**
  ----------------------------------- -----------------------------------
  Lộ mật khẩu gốc                     Người dùng kết nối qua Web
                                      (Guacamole) mà không bao giờ thấy
                                      credential thật của server

  Quyền vĩnh viễn                     Quyền truy cập chỉ tồn tại trong
                                      thời lượng cụ thể (VD: 30 phút) rồi
                                      tự động bị thu hồi

  Thiếu kiểm toán                     Ghi lại toàn bộ video phiên làm
                                      việc, lưu trữ trên MinIO kèm
                                      SHA-256 Hash chống sửa đổi
  -----------------------------------------------------------------------

## 1.3. Phạm vi Đề tài

  -----------------------------------------------------------------------
  **Sprint**              **Nội dung**            **Trạng thái**
  ----------------------- ----------------------- -----------------------
  Sprint 0                Dựng hạ tầng Docker     Hoàn thành
                          Compose (Guacamole,     
                          Keycloak, Postgres,     
                          Nginx)                  

  Sprint 1                Xây dựng Control Plane  Hoàn thành
                          Backend, RBAC, Keycloak 
                          OIDC Integration        

  Sprint 2                JIT Access Workflow     Hoàn thành
                          (Request → Approve →    
                          Auto-Revoke), Frontend  
                          UI                      

  Sprint 3                Audit Trail, Session    Hoàn thành
                          Recording (guacenc →    
                          mp4 → MinIO → SHA-256)  

  Sprint 4                Hardening, Demo         Đang thực hiện
                          End-to-End, Báo cáo     
  -----------------------------------------------------------------------

# Chương 2: Kiến trúc Hệ thống

## 2.1. Bảng Tổng hợp Thành phần

  -----------------------------------------------------------------------
  **Thành phần**    **Công nghệ**     **Chức năng**     **Phụ trách**
  ----------------- ----------------- ----------------- -----------------
  Reverse Proxy     Nginx Alpine      TLS Termination,  Vinh
                                      điều hướng        
                                      request           

  Identity Provider Keycloak 23.0     SSO, OIDC Token,  Vinh
                                      OTP xác thực 2    
                                      lớp               

  Remote Gateway    Guacamole 1.5.4   Hiển thị          Vinh
                                      SSH/VNC/RDP trên  
                                      trình duyệt Web   

  Control Plane     FastAPI 0.139     Logic JIT Access, Inh
                                      RBAC Policy,      
                                      Scheduler         
                                      Auto-Revoke       

  Database          PostgreSQL 15     Lưu trữ Users,    Inh
                                      Groups, Policies, 
                                      Requests, Grants, 
                                      Sessions          

  Frontend UI       Flask + Jinja2    Giao diện Admin   Nghĩa
                                      Dashboard, Xin    
                                      quyền, Duyệt      

  Audit Worker      Python + guacenc  Convert video     Sang
                                      .guac → .mp4, đẩy 
                                      MinIO, tính       
                                      SHA-256           

  Object Storage    MinIO             Lưu trữ file      Sang
                                      video ghi hình    
                                      phiên làm việc    
  -----------------------------------------------------------------------

## 2.2. Tech Stack Chi tiết

  -----------------------------------------------------------------------
  **Layer**               **Technology**          **Version**
  ----------------------- ----------------------- -----------------------
  Backend Framework       FastAPI                 0.139.2

  ORM                     SQLAlchemy              2.0.51

  DB Migration            Alembic                 1.18.5

  Background Scheduler    APScheduler             3.11.0

  HTTP Client             HTTPX                   0.28.1

  JWT Authentication      PyJWT + Cryptography    2.10.1 / 44.0.1

  ASGI Server             Uvicorn                 0.51.0

  Database                PostgreSQL              15-alpine

  Identity & Access       Keycloak                23.0.0

  Remote Desktop Gateway  Apache Guacamole        1.5.4

  Containerization        Docker Compose          3.8
  -----------------------------------------------------------------------

# Chương 3: Control Plane Backend (FastAPI)

## 3.1. Cấu trúc Thư mục Mã nguồn

control-plane-backend/\
├── app/\
│ ├── main.py --- Khởi tạo FastAPI App, CORS, Lifespan Scheduler\
│ ├── core/\
│ │ ├── config.py --- Cấu hình Settings (DB URL, Keycloak, Guacamole)\
│ │ ├── database.py --- Engine, SessionLocal, Base, get_db()\
│ │ ├── auth.py --- Keycloak JWT Verify & Auto-Sync User\
│ │ └── scheduler.py --- APScheduler AsyncIOScheduler Instance\
│ ├── models/\
│ │ └── auth_rbac.py --- 8 ORM Models (User, Group, Server, Policy,
\...)\
│ ├── schemas/ --- Pydantic Schemas (access, server, user_group, policy,
audit)\
│ ├── routers/ --- 5 Router Modules (access, server, user_group, policy,
audit)\
│ └── services/\
│ └── guacamole.py --- GuacamoleClient
(grant/revoke/ensure_user_exists)\
├── migrations/versions/ --- Alembic Migration Files\
├── seed_data.py --- Script nạp dữ liệu khởi tạo\
├── requirements.txt\
├── Dockerfile\
└── alembic.ini

## 3.2. Cấu hình Hệ thống (app/core/config.py)

  ---------------------------------------------------------------------------------------------------------------
  **Biến**                 **Mô tả**               **Giá trị mặc định (Docker)**
  ------------------------ ----------------------- --------------------------------------------------------------
  DATABASE_URL             Chuỗi kết nối           postgresql://pam_user:pam_password@postgres:5432/pam_control
                           PostgreSQL              

  GUACAMOLE_BASE_URL       URL gốc REST API của    http://guacamole:8080/guacamole/api
                           Guacamole               

  GUACAMOLE_ADMIN_USER     Tài khoản Admin         guacadmin
                           Guacamole               

  KEYCLOAK_SERVER_URL      URL gốc của Keycloak    http://keycloak:8080
                           Server                  

  KEYCLOAK_REALM           Tên Realm trên Keycloak pam-realm

  KEYCLOAK_CLIENT_ID       Client ID đăng ký cho   fastapi-backend
                           Backend                 

  KEYCLOAK_CLIENT_SECRET   Client Secret tương ứng 98a1c5d3-8b4e-4f12-\...
  ---------------------------------------------------------------------------------------------------------------

## 3.3. Khởi tạo Ứng dụng (app/main.py)

Ứng dụng FastAPI sử dụng các thành phần chính:

-   Lifespan Events: Khởi động APScheduler khi ứng dụng bắt đầu và tắt
    sạch khi ứng dụng dừng.

-   CORS Middleware: Cho phép Frontend UI gọi API cross-origin không bị
    trình duyệt chặn.

-   5 Router Modules: server, user_group, policy, access, audit.

# Chương 4: Thiết kế Cơ sở Dữ liệu

## 4.1. Tổng quan

Hệ thống database PostgreSQL của Control Plane gồm 8 bảng chính và 1
bảng trung gian (user_groups) quản lý mối quan hệ Nhiều-Nhiều.

## 4.2. Bảng users

Lưu trữ thông tin người dùng, tự động đồng bộ từ Keycloak khi lần đầu
đăng nhập.

  ----------------------------------------------------------------------------
  **Cột**           **Kiểu**          **Ràng buộc**     **Mô tả**
  ----------------- ----------------- ----------------- ----------------------
  id                UUID              PK, auto-gen      Định danh duy nhất

  keycloak_sub      UUID              Unique, Nullable  Subject ID từ Keycloak
                                                        JWT Token

  username          String            Not Null          Tên đăng nhập
                                                        (preferred_username)

  email             String            Nullable          Địa chỉ email

  full_name         String            Nullable          Họ tên đầy đủ

  is_active         Boolean           Default True      Trạng thái hoạt động

  synced_at         DateTime          Default now()     Thời điểm đồng bộ gần
                                                        nhất
  ----------------------------------------------------------------------------

## 4.3. Bảng groups

Quản lý nhóm người dùng theo mô hình RBAC.

  -------------------------------------------------------------------------
  **Cột**             **Kiểu**          **Ràng buộc**     **Mô tả**
  ------------------- ----------------- ----------------- -----------------
  id                  UUID              PK                Định danh nhóm

  keycloak_group_id   UUID              Unique, Nullable  ID nhóm trên
                                                          Keycloak

  name                String            Unique, Not Null  Tên nhóm
                                                          (PAM-Admins,
                                                          PAM-Support,
                                                          PAM-Auditors)

  description         String            Nullable          Mô tả nhóm
  -------------------------------------------------------------------------

## 4.4. Bảng servers

Danh sách máy chủ mục tiêu mà người dùng có thể xin truy cập.

  -------------------------------------------------------------------------------
  **Cột**                   **Kiểu**          **Ràng buộc**     **Mô tả**
  ------------------------- ----------------- ----------------- -----------------
  id                        UUID              PK                Định danh máy chủ

  name                      String            Not Null          Tên hiển thị (VD:
                                                                Linux SSH Server)

  host                      String            Not Null          IP hoặc Hostname
                                                                nội bộ Docker

  port                      Integer           Not Null          Cổng dịch vụ (22,
                                                                5900, 3389)

  protocol                  String            Not Null          Loại kết nối:
                                                                ssh, vnc, rdp

  guacamole_connection_id   String            Not Null          ID kết nối số
                                                                trên Guacamole DB
                                                                (\"1\", \"2\")

  tags                      ARRAY(String)     Nullable          Nhãn phân loại
                                                                (production,
                                                                staging)
  -------------------------------------------------------------------------------

## 4.5. Bảng group_server_policy

Chính sách phân quyền: Nhóm nào được phép truy cập Server nào, tối đa
bao lâu.

  ----------------------------------------------------------------------------
  **Cột**                **Kiểu**          **Ràng buộc**     **Mô tả**
  ---------------------- ----------------- ----------------- -----------------
  id                     UUID              PK                Định danh chính
                                                             sách

  group_id               UUID              FK → groups.id    Nhóm áp dụng

  server_id              UUID              FK → servers.id   Server áp dụng

  max_duration_minutes   Integer           Default 60        Thời lượng JIT
                                                             tối đa cho phép
                                                             (phút)

  require_approval       Boolean           Default True, Not Bắt buộc Admin
                                           Null              duyệt hay không

  created_at             DateTime          Nullable          Thời điểm tạo
                                                             chính sách
  ----------------------------------------------------------------------------

## 4.6. Bảng access_requests

Lưu trữ toàn bộ yêu cầu xin quyền truy cập JIT từ người dùng.

  -------------------------------------------------------------------------
  **Cột**             **Kiểu**          **Ràng buộc**     **Mô tả**
  ------------------- ----------------- ----------------- -----------------
  id                  UUID              PK                Định danh yêu cầu

  user_id             UUID              FK → users.id     Người gửi yêu cầu

  server_id           UUID              FK → servers.id   Máy chủ cần truy
                                                          cập

  reason              String            Not Null          Lý do xin truy
                                                          cập

  requested_minutes   Integer           Not Null          Thời lượng mong
                                                          muốn (phút)

  status              String            Default           pending /
                                        \"pending\"       approved /
                                                          rejected /
                                                          expired

  requested_at        DateTime          Default now()     Thời điểm gửi yêu
                                                          cầu

  decided_by          UUID              FK → users.id,    Admin đã duyệt/từ
                                        Nullable          chối

  decided_at          DateTime          Nullable          Thời điểm quyết
                                                          định

  decision_note       String            Nullable          Ghi chú của Admin
  -------------------------------------------------------------------------

## 4.7. Bảng active_grants

Theo dõi quyền JIT đang có hiệu lực trong thời gian thực.

  --------------------------------------------------------------------------
  **Cột**           **Kiểu**          **Ràng buộc**        **Mô tả**
  ----------------- ----------------- -------------------- -----------------
  id                UUID              PK                   Định danh grant

  request_id        UUID              FK →                 Yêu cầu gốc
                                      access_requests.id   

  user_id           UUID              FK → users.id        Người được cấp
                                                           quyền

  server_id         UUID              FK → servers.id      Máy chủ được truy
                                                           cập

  granted_at        DateTime          Default now()        Thời điểm bắt đầu

  expires_at        DateTime          Not Null             Thời điểm hết hạn
                                                           (APScheduler
                                                           quét)

  revoked_at        DateTime          Nullable             Thời điểm bị thu
                                                           hồi sớm

  revoked_by        UUID              Nullable             Admin thu hồi thủ
                                                           công

  revoke_reason     String            Nullable             Lý do thu hồi sớm
  --------------------------------------------------------------------------

## 4.8. Bảng session_logs

Ghi lại lịch sử từng phiên làm việc và liên kết với video ghi hình.

  --------------------------------------------------------------------------
  **Cột**           **Kiểu**          **Ràng buộc**        **Mô tả**
  ----------------- ----------------- -------------------- -----------------
  id                UUID              PK                   Định danh phiên

  request_id        UUID              FK →                 Yêu cầu tạo ra
                                      access_requests.id   phiên này

  user_id           UUID              FK → users.id        Người thực hiện
                                                           phiên

  server_id         UUID              FK → servers.id      Máy chủ được kết
                                                           nối

  start_time        DateTime          Default now()        Thời điểm bắt đầu

  end_time          DateTime          Nullable             Thời điểm kết
                                                           thúc

  status            String            Default \"active\"   active /
                                                           completed /
                                                           revoked

  recording_file    String            Nullable             Tên file video
                                                           .mp4

  recording_url     String            Nullable             Đường dẫn MinIO
                                                           để phát lại

  recording_hash    String            Nullable             Mã SHA-256 Hash
                                                           chống sửa đổi
  --------------------------------------------------------------------------

## 4.9. Bảng audit_logs

Nhật ký thao tác toàn hệ thống phục vụ mục đích kiểm toán.

  ------------------------------------------------------------------------
  **Cột**           **Kiểu**          **Ràng buộc**     **Mô tả**
  ----------------- ----------------- ----------------- ------------------
  id                UUID              PK                Định danh log

  user_id           UUID              FK → users.id     Người thực hiện
                                                        thao tác

  action            String            Not Null          ACCESS_APPROVED,
                                                        ACCESS_REVOKED,
                                                        \...

  target_type       String            Nullable          Đối tượng (SERVER,
                                                        POLICY, USER)

  target_id         String            Nullable          ID của đối tượng

  details           String            Nullable          Mô tả chi tiết

  timestamp         DateTime          Default now()     Thời điểm ghi log
  ------------------------------------------------------------------------

# Chương 5: Tích hợp Keycloak OIDC

## 5.1. Cấu hình Keycloak

  ---------------------------------------------------------------------------------------------------------
  **Thông số**                        **Giá trị**
  ----------------------------------- ---------------------------------------------------------------------
  Realm                               pam-realm

  Client ID                           fastapi-backend

  Client Type                         Confidential

  Client Secret                       98a1c5d3-8b4e-4f12-9c31-7e8b2a14d5f6

  JWKS Certs                          http://keycloak:8080/realms/pam-realm/protocol/openid-connect/certs
  ---------------------------------------------------------------------------------------------------------

## 5.2. Cơ chế Xác thực JWT Bearer Token (app/core/auth.py)

Khi Frontend gửi request với header Authorization: Bearer \<JWT_TOKEN\>,
Control Plane Backend xử lý qua 4 bước:

-   Bước 1 --- Lấy Public Key từ Keycloak JWKS: Gọi JWKS endpoint, cache
    key trong bộ nhớ (\_jwks_cache).

-   Bước 2 --- Xác minh Chữ ký (Verify Signature): Trích xuất kid từ JWT
    Header, tìm RSA Public Key, verify bằng RS256.

-   Bước 3 --- Giải mã Claims: Trích xuất sub, preferred_username,
    email, given_name, family_name.

-   Bước 4 --- Tự động Đồng bộ User (Auto-Sync): Nếu user chưa tồn tại
    trong DB → tự động tạo record mới từ JWT Token.

# Chương 6: Tích hợp Apache Guacamole REST API

## 6.1. Module GuacamoleClient (app/services/guacamole.py)

Control Plane Backend giao tiếp với Guacamole thông qua REST API để thực
hiện 3 chức năng cốt lõi:

### 6.1.1. Lấy Token Admin (get_admin_token)

Gọi POST /api/tokens với tài khoản guacadmin. Trả về authToken và
dataSource. Timeout: 15 giây.

### 6.1.2. Tự động Khởi tạo User (ensure_user_exists)

Kiểm tra user đã tồn tại trong Guacamole chưa (GET /users/{username}).
Nếu HTTP 404 → tự động gọi POST /users để tạo user mới. Lý do: User mới
đăng ký trên Keycloak nhưng chưa đăng nhập Guacamole Web UI sẽ bị lỗi
404 khi PATCH permissions.

### 6.1.3. Cấp / Thu hồi Quyền Kết nối

Gọi PATCH /users/{username}/permissions với payload:

-   Cấp quyền: {\"op\": \"add\", \"path\":
    \"/connectionPermissions/{id}\", \"value\": \"READ\"}

-   Thu hồi: {\"op\": \"remove\", \"path\":
    \"/connectionPermissions/{id}\", \"value\": \"READ\"}

-   Ràng buộc: connection_id phải là dạng số nguyên (\"1\", \"2\"),
    không được truyền chuỗi tự do.

# Chương 7: Luồng JIT Access & Tự động Thu hồi

## 7.1. Luồng xử lý khi Admin Approve

Khi Admin gọi POST /access/requests/{id}/review với status:
\"approved\", backend thực thi 5 bước tuần tự trong cùng 1 transaction:

-   Bước A --- Cấp quyền trên Guacamole: Gọi
    guac_client.grant_connection_access(). Tự động provision user nếu
    chưa có.

-   Bước B --- Tạo ActiveGrant: Ghi nhận granted_at và expires_at =
    now + requested_minutes.

-   Bước C --- Tạo SessionLog: Ghi nhật ký phiên làm việc (Sprint 3
    Audit Trail).

-   Bước D --- Tạo AuditLog: Ghi nhật ký hành động ACCESS_APPROVED.

-   Bước E --- Đặt lịch APScheduler:
    scheduler.add_job(auto_revoke_wrapper, \"date\",
    run_date=expire_time).

## 7.2. Hàm Tự động Thu hồi (auto_revoke_wrapper)

Khi APScheduler trigger nổ (hết thời gian JIT), hệ thống thực hiện:

> Gọi guac_client.revoke_connection_access() → PATCH remove READ trên
> Guacamole.
>
> Xóa record ActiveGrant tương ứng khỏi Database.
>
> Cập nhật AccessRequest.status = \"expired\".
>
> Commit transaction và đóng DB session.

## 7.3. Thu hồi Thủ công bởi Admin

Admin có thể bấm nút Revoke trước khi hết hạn JIT (POST
/access/grants/{grant_id}/revoke):

> Hủy job APScheduler đang chờ (scheduler.remove_job()).
>
> Gọi Guacamole REST API thu hồi ngay lập tức.
>
> Xóa ActiveGrant và cập nhật status = expired.

# Chương 8: Hệ thống Kiểm toán & Ghi hình (Audit Trail)

(Phần này do Sang triển khai chính)

## 8.1. API Audit do Control Plane cung cấp

  ----------------------------------------------------------------------------------------
  **Method**              **Endpoint**                             **Mô tả**
  ----------------------- ---------------------------------------- -----------------------
  GET                     /audit/sessions/                         Lấy danh sách tất cả
                                                                   phiên làm việc

  GET                     /audit/sessions/{session_id}             Xem chi tiết 1 phiên

  POST                    /audit/sessions/{session_id}/recording   Worker gửi video URL +
                                                                   SHA-256 Hash

  GET                     /audit/logs/                             Lấy nhật ký thao tác hệ
                                                                   thống

  POST                    /audit/logs/                             Ghi thêm 1 nhật ký hệ
                                                                   thống
  ----------------------------------------------------------------------------------------

## 8.2. Quy trình Xử lý Video Ghi hình

> Quá trình xử lý và lưu trữ video phiên làm việc (session) diễn ra tự
> động và khép kín qua các bước chi tiết như sau:
>
> Ghi nhận dữ liệu thô: Trong suốt quá trình người dùng thao tác qua
> giao thức SSH/VNC, guacd daemon sẽ liên tục ghi lại luồng dữ liệu (raw
> data) và xuất ra dưới dạng file .guac.
>
> Chuyển đổi định dạng: Thành phần audit_worker thực hiện cơ chế quét
> (polling) liên tục thư mục chứa log. Khi phát hiện file log đã đóng
> (kết thúc phiên kết nối), Worker sẽ sử dụng công cụ guacenc để tiến
> hành convert file .guac thô thành file video chuẩn định dạng .mp4
> (hoặc .m4v).
>
> Lưu trữ lên Object Storage: Sau khi file video được kết xuất thành
> công, Worker sẽ thực hiện kết nối và đẩy file .mp4 này lên hệ thống
> lưu trữ MinIO, cụ thể là lưu vào bucket bảo mật có tên
> \"pam-audit-logs\". Để đảm bảo an toàn khi phát video trên trình duyệt
> cho người quản trị xem lại, hệ thống sử dụng module get_video_url.py
> để sinh Presigned URL (đường dẫn tạm thời có hiệu lực 15 phút) thay vì
> mở quyền truy cập public cho video.
>
> Cập nhật dữ liệu về Backend: Ở bước cuối cùng, Worker tính toán mã băm
> SHA-256 Hash của file video hiện tại, sau đó thực hiện gọi API qua
> giao thức POST đến endpoint /audit/sessions/{id}/recording để lưu các
> thông số siêu dữ liệu (metadata) cũng như mã băm này vào cơ sở dữ liệu
> của Control Plane.

## 8.3. Cơ chế Chống sửa đổi (Tamper-Evidence) bằng móc xích mã băm

Hệ thống Audit mang đặc thù yêu cầu bảo mật nghiêm ngặt chống lại việc
xóa dấu vết hoặc làm giả bằng chứng của nội gián. Do đó, cơ chế chống
sửa đổi (Tamper-Evidence) được nâng cấp bằng thuật toán Móc xích mã băm
(Hash-Chaining):

Sinh và lưu trữ mã băm móc xích: Mỗi file video .mp4 sau khi được upload
lên MinIO sẽ được tính toán mã băm bằng thuật toán SHA-256 (gọi là
file_hash). Thay vì chỉ lưu mã băm đơn lẻ, hệ thống sẽ lấy thêm mã băm
của phiên làm việc liền trước đó (previous_chained_hash), ghép nối với
file_hash hiện tại để băm ra một mã tổng hợp gọi là chained_hash. Mã này
được lưu cố định vào trường recording_hash trong bảng session_logs.

Quy trình kiểm tra toàn vẹn: Khi có yêu cầu kiểm tra tính toàn vẹn thông
qua module verify_chain.py, hệ thống sẽ tải danh sách các bản ghi từ DB:
lấy mã file_hash của từng bản ghi, ghép với chained_hash của bản ghi
trước, rồi hệ thống tự tính toán lại mã băm. Cuối cùng đem so sánh đối
chiếu với giá trị đang lưu trong Database.

Phát hiện sửa đổi trái phép: Dựa trên đặc tính của Hash-Chaining, nếu
bất kỳ một file video .mp4 nào trên MinIO bị chỉnh sửa, cắt ghép, hoặc
một bản ghi trong quá khứ bị hacker lén lút xóa khỏi DB, mã Hash tính
toán lại tại mắt xích đó sẽ thay đổi. Sự thay đổi này làm đứt gãy toàn
bộ chuỗi băm phía sau. Khi tiến hành so sánh sẽ sinh ra hiện tượng không
khớp (Hash Mismatch), hệ thống ngay lập tức phát hiện và cảnh báo chính
xác bản ghi nào đã bị sửa đổi trái phép.

# Chương 9: Hạ tầng & Docker Compose

(Phần này do Quốc Vinh triển khai chính)

## 9.1. Danh sách Service trong docker-compose.yml

  ----------------------------------------------------------------------------------------------
  **Service**        **Image**               **Container**         **Port**       **Network**
  ------------------ ----------------------- --------------------- -------------- --------------
  nginx              nginx:alpine            pam_nginx             80, 443        frontend,
                                                                                  backend

  keycloak           keycloak:23.0.0         pam_keycloak          8080           backend
                                                                   (internal)     

  guacd              guacamole/guacd:1.5.4   pam_guacd             4822           backend,
                                                                   (internal)     targets

  guacamole          guacamole:1.5.4         pam_guacamole         8080           backend
                                                                   (internal)     

  control-plane      Build Dockerfile        pam_control_backend   8000           backend,
                                                                                  frontend

  postgres           postgres:15-alpine      pam_postgres          5432           backend
                                                                   (internal)     

  target_linux_ssh   openssh-server          target_linux_ssh      22 (internal)  targets

  target_vnc         chromium                target_vnc            5900           targets
                                                                   (internal)     

  minio              minio/minio             pam_minio             9000, 9001     backend

  audit_worker       Build Dockerfile        pam_audit_worker      ---            backend
  ----------------------------------------------------------------------------------------------

## 9.2. Khởi tạo Database Tự động

File init-db/init-multiple-dbs.sh được mount vào
/docker-entrypoint-initdb.d của Postgres container. Khi Postgres khởi
động lần đầu, script tự động tạo 3 database: keycloak, guacamole,
pam_control từ biến POSTGRES_MULTIPLE_DATABASES.

**9.3. Chi tiết Cấu hình Mạng (Network)**

Hệ thống sử dụng các Docker network riêng biệt nhằm đảm bảo an toàn, bảo
mật và phân lập giao thông (traffic isolation) giữa các thành phần:

Network frontend: Là mạng dành cho giao tiếp từ phía người dùng cuối
(client) vào hệ thống thông qua Reverse Proxy (Nginx). Nginx sẽ tiếp
nhận các request trên cổng 80/443 ở mạng này và định tuyến chúng đến các
dịch vụ giao diện hoặc API tương ứng.

Network backend: Đây là mạng nội bộ an toàn (internal network) dành
riêng cho các core services giao tiếp với nhau. Các dịch vụ lõi như
control-plane, keycloak, guacamole, cơ sở dữ liệu postgres, và bộ nhớ
lưu trữ minio được đặt trong mạng này. Các cổng của backend (như 5432,
8080) không bị expose trực tiếp ra ngoài máy host, giúp ngăn chặn triệt
để các rủi ro tấn công từ bên ngoài.

Network targets: Mạng chuyên dụng để kết nối thành phần proxy của PAM
(cụ thể là guacd) với các máy đích (target machines) cần được quản lý
quyền truy cập (ví dụ: target_linux_ssh, target_vnc). Việc cô lập mạng
này giúp hệ thống kiểm soát chặt chẽ luồng kết nối SSH/VNC/RDP nội bộ,
ngăn không cho các dịch vụ bên ngoài can thiệp vào traffic của máy đích.

9.4. Nginx (Reverse Proxy & API Gateway)

Dịch vụ nginx (sử dụng image nginx:alpine) đóng vai trò là cửa ngõ giao
tiếp duy nhất (Single Point of Contact) của toàn bộ hạ tầng PAM đối với
thế giới bên ngoài.

Định tuyến (Routing): Nginx đóng vai trò phân luồng request dựa trên
URL/Path hoặc Domain. Ví dụ: định tuyến /auth tới Keycloak, /guacamole
tới Guacamole client, hoặc /api tới backend control-plane. Việc này giúp
người dùng chỉ cần tương tác qua một địa chỉ duy nhất.

Bảo mật & SSL/TLS Termination: Nginx đảm nhiệm việc xử lý chứng chỉ số
và mã hóa đường truyền (HTTPS qua cổng 443). Mọi kết nối từ client đến
Nginx đều được mã hóa, sau đó Nginx có thể giao tiếp với các dịch vụ
backend bằng HTTP thông thường (qua mạng backend an toàn), giúp giảm tải
quá trình giải mã cho các dịch vụ phía sau.

Tối ưu và Cân bằng tải: Nginx cung cấp khả năng caching các tài nguyên
tĩnh, nén dữ liệu truyền tải và duy trì tính ổn định (high availability)
khi luồng traffic truy cập lớn.

9.5. Keycloak (Identity and Access Management - IAM)

Dịch vụ keycloak được triển khai làm hệ thống quản lý định danh và phân
quyền trung tâm, đóng vai trò cốt lõi trong kiến trúc bảo mật của PAM.

Xác thực tập trung (Single Sign-On - SSO): Keycloak giúp đồng bộ hóa
phiên đăng nhập. Người dùng chỉ cần xác thực một lần để có thể truy cập
vào cả trang quản trị (Control Plane) và cổng kết nối máy đích
(Guacamole) mà không phải đăng nhập lại nhiều lần.

Quản lý Phân quyền (Roles & Policies): Keycloak lưu trữ tập trung các
danh tính người dùng, nhóm (groups), và các roles bảo mật. Hệ thống
control-plane sẽ dựa trên các token xác thực từ Keycloak để quyết định
xem người dùng có quyền truy cập vào phiên làm việc SSH/RDP/VNC cụ thể
nào hay không.

Giao thức bảo mật chuẩn công nghiệp: Keycloak tích hợp chặt chẽ qua các
chuẩn OpenID Connect (OIDC) / OAuth 2.0. Token sinh ra (JWT) được dùng
làm cơ sở xác thực xuyên suốt giữa Nginx, Frontend và Backend.

Lưu trữ dữ liệu độc lập: Quá trình khởi tạo (qua script
init-multiple-dbs.sh) đã chuẩn bị sẵn một database riêng có tên keycloak
trên cụm postgres. Keycloak sử dụng schema này để lưu trữ mọi cấu hình,
thông tin tài khoản và chính sách bảo mật một cách an toàn ở mạng
backend.

# Chương 10: Giao diện Người dùng & RBAC UI

## 10.1. Kiến trúc Tổng quan Giao diện

Giao diện quản trị PAM Gateway được xây dựng theo kiến trúc
server-rendered, không dùng SPA framework (React/Vue) nhằm giảm độ phức
tạp và phù hợp với đặc thù cần cập nhật tức thời từng phần giao diện (ví
dụ: danh sách yêu cầu chờ duyệt) sau mỗi thao tác.

-   Công nghệ: FastAPI (xử lý route & logic) kết hợp HTMX (cập nhật một
    > phần giao diện không cần tải lại trang) và Jinja2 (render HTML
    > phía server).

-   Cổng chạy: 8001, độc lập với Control Plane API (cổng 8000) do Inh
    > phụ trách.

-   Nguyên tắc kiến trúc: main.py không thao tác dữ liệu trực tiếp mà
    > luôn gọi qua lớp trung gian api_client.py --- toàn bộ giao tiếp
    > với Control Plane API đều tập trung tại đây.

-   Cờ USE_MOCK (khai báo trong api_client.py): cho phép chuyển đổi giữa
    > dữ liệu giả lập (khi Control Plane chưa sẵn sàng hoặc đang phát
    > triển độc lập) và dữ liệu thật, mà không cần sửa main.py hay bất
    > kỳ template nào.

Mọi request tới giao diện đều đi qua middleware kiểm tra JWT token lưu
trong session (được cấp sau khi đăng nhập qua Keycloak). Nếu chưa đăng
nhập hoặc token hết hạn, hệ thống tự động chuyển hướng người dùng về
trang đăng nhập.

## 10.2. Luồng Đăng nhập (OIDC qua Keycloak)

Toàn bộ quá trình xác thực sử dụng Authorization Code Flow with PKCE,
không có luồng đăng nhập giả lập (mock) --- đây là luồng thật kết nối
trực tiếp với Keycloak.

-   Người dùng truy cập giao diện khi chưa đăng nhập → hệ thống tự động
    > chuyển hướng (redirect) sang trang đăng nhập của Keycloak.

![](media/image1.png){width="5.0in" height="3.3346741032370955in"}

-   Người dùng nhập tài khoản, mật khẩu (và mã OTP nếu tài khoản có bật
    > xác thực 2 lớp).

-   Keycloak xác thực thành công, chuyển hướng về /auth/callback kèm
    > authorization code.

-   Backend đổi code lấy access token + refresh token, lưu vào session
    > người dùng.

-   Hệ thống đọc role trong token (PAM-Admins / PAM-Support /
    > PAM-Auditors) để xác định quyền hiển thị tương ứng. Nếu role không
    > khớp với nhóm hợp lệ nào, hệ thống chặn truy cập và hiển thị lỗi
    > --- không có bước chọn nhóm thủ công (fallback) như bản demo trước
    > đây.

![](media/image11.png){width="5.0in" height="4.048938101487314in"}

## 10.3. Các Màn hình Chức năng

Giao diện có 4 tab điều hướng cố định (Xin quyền, Quản lý server, Quyền
đang active, Nhóm & phân quyền), hiển thị giống nhau cho mọi tài khoản
đã đăng nhập.

Lưu ý quan trọng: hiện tại middleware chỉ kiểm tra \"đã đăng nhập hay
chưa\", KHÔNG kiểm tra vai trò (role) ở tầng route cho 3/4 tab. Role
Keycloak (PAM-Admins/PAM-Support/PAM-Auditors) chỉ ảnh hưởng tới tab
\"Xin quyền\" --- cụ thể là danh sách server được phép xin quyền hiển
thị theo policy của nhóm khớp với role. Các tab còn lại (Quản lý server,
Quyền đang active, Nhóm & phân quyền) hiện chưa có giới hạn vai trò ở
phía server --- bất kỳ ai đăng nhập cũng thao tác được. Đây là điểm cần
trao đổi thêm với nhóm nếu muốn siết chặt theo đúng tinh thần RBAC.

  --------------------------------------------------------------------------
  **Màn hình**     **Route**        **Chức năng chính**
  ---------------- ---------------- ----------------------------------------
  **Xin quyền**    /                Chọn server (theo policy nhóm mình), gửi
                                    yêu cầu JIT; đồng thời liệt kê toàn bộ
                                    yêu cầu trong hệ thống kèm nút Duyệt/Từ
                                    chối cho yêu cầu đang chờ

  **Quản lý        /servers         Sửa tên hiển thị, IP và tag của server
  server**                          (đồng bộ tự động từ Guacamole, không
                                    thêm/xoá được)

  **Quyền đang     /active-grants   Danh sách quyền đã duyệt, tự làm mới mỗi
  active**                          5 giây, nút Thu hồi ngay

  **Nhóm & phân    /groups          Ma trận Nhóm × Server: bật/tắt được phép
  quyền**                           truy cập, thời lượng tối đa, có cần
                                    duyệt hay không
  --------------------------------------------------------------------------

# 

### 10.3.1.Màn hình Xin quyền (Xin quyền truy cập JIT)

Đây là trang chủ (\"/\"), gồm 2 phần trên cùng 1 trang:

-   Form \"Xin quyền mới\": chọn server trong danh sách server mà nhóm
    > của mình được phép (lấy theo policy khớp với nhóm), nhập lý do,
    > nhập thời lượng (phút). Dropdown server hiển thị kèm gợi ý thời
    > lượng tối đa và có tự động cấp hay không, lấy từ policy.

-   Bảng \"Yêu cầu của tôi\": thực chất liệt kê TOÀN BỘ yêu cầu trong hệ
    > thống (không lọc theo người gửi). Với mỗi yêu cầu đang ở trạng
    > thái pending, hiển thị 2 nút Duyệt / Từ chối ngay trong bảng ---
    > không có trang Approve/Reject riêng biệt.

Do chưa có giới hạn vai trò ở route này, bất kỳ user nào đăng nhập cũng
thấy và duyệt/từ chối được yêu cầu của bất kỳ ai khác, không chỉ của
riêng Admin. Cần cân nhắc bổ sung kiểm tra vai trò nếu muốn đúng mô hình
RBAC.

![](media/image2.png){width="6.0in" height="5.861111111111111in"}

![](media/image10.png){width="6.0in" height="5.722222222222222in"}

![](media/image9.png){width="6.0in" height="5.611111111111111in"}

### 10.3.2. Màn hình Nhóm & phân quyền

Hiển thị dạng ma trận: mỗi nhóm (đồng bộ tên từ Keycloak) có 1 bảng con
liệt kê toàn bộ server trong hệ thống, mỗi dòng là 1 server với các cột:

-   Được phép: checkbox bật/tắt --- nhóm này có được xin quyền vào
    > server đó hay không.

-   Thời lượng tối đa (phút): số phút JIT tối đa cho phép.

-   Cần duyệt: checkbox --- bật thì Admin phải duyệt thủ công, tắt thì
    > cấp quyền tự động ngay khi user gửi yêu cầu.

-   Nút Lưu riêng cho từng dòng (từng server), không phải lưu cả nhóm
    > một lượt.

Kỹ thuật: do Control Plane chưa có PATCH/PUT cho policy, khi bấm Lưu, hệ
thống sẽ tự xoá policy cũ (nếu tồn tại giữa nhóm và server đó) rồi tạo
policy mới với thông số vừa nhập. Nếu bỏ tick \"Được phép\" mà trước đó
đã có policy, hệ thống sẽ xoá thẳng policy đó (thu hồi quyền xin server
này của nhóm).

![](media/image8.png){width="6.0in" height="4.736111111111111in"}

### 10.3.3. Màn hình Quyền đang active

-   Liệt kê các quyền đã được duyệt: server, lý do, trạng thái (Đang
    > hoạt động / Đã hết hạn / Đã thu hồi), thời gian còn lại.

-   Bảng tự động làm mới mỗi 5 giây (HTMX polling), không phải đồng hồ
    > đếm ngược chạy bằng JavaScript --- thời gian còn lại là chuỗi text
    > được tính lại mỗi lần làm mới (ví dụ \"1 giờ 20 phút\").

-   Nút \"Thu hồi ngay\" chỉ hiện với quyền đang ở trạng thái hoạt động,
    > gọi thu hồi thủ công trước khi tự động hết hạn.

![](media/image7.png){width="6.0in" height="2.9444444444444446in"}

### 10.3.4. Màn hình Quản lý Server

-   Danh sách server được đồng bộ tự động từ Guacamole --- màn hình này
    > cho phép sửa tên hiển thị, IP và tag, không thêm mới hoặc xoá
    > server.

-   Mỗi dòng server có nút Sửa; khi bấm vào, dòng đó chuyển sang chế độ
    > chỉnh sửa (3 ô nhập: tên, IP, tag) với 2 nút Lưu / Hủy.

![](media/image6.png){width="6.0in" height="3.375in"}

![](media/image12.png){width="6.0in" height="3.3472222222222223in"}

## 10.4. Luồng Thao tác Chi tiết (End-to-end)

Phần này mô tả các luồng thao tác đầy đủ, kết hợp cả thao tác trên giao
diện và xử lý phía backend --- phù hợp làm kịch bản quay video demo, đặc
biệt luồng 10.4.3 (cấu hình phân quyền) là trọng tâm chính của project.

### 10.4.1. Luồng User xin quyền truy cập

-   User đăng nhập, ở ngay trang chủ (\"Xin quyền\").

-   Chọn server cần truy cập (chỉ thấy server mà nhóm mình có policy
    > được phép), nhập thời gian mong muốn và lý do.

-   Gửi yêu cầu → giao diện gọi POST /access-requests.

-   Yêu cầu được lưu với trạng thái pending (hoặc được cấp quyền ngay
    > nếu policy của server đó tắt \"Cần duyệt\").

### 10.4.2. Luồng Duyệt & Thu hồi Quyền

-   Duyệt: bất kỳ ai đang đăng nhập, ở ngay bảng \"Yêu cầu của tôi\"
    > trên trang chủ, bấm Duyệt trên 1 yêu cầu pending bất kỳ → gọi POST
    > /access-requests/{id}/approve → Control Plane cấp quyền trên
    > Guacamole, tạo bản ghi quyền, đặt lịch tự động thu hồi (chi tiết
    > tại Chương 7.1).

-   Từ chối: tương tự nhưng gọi \.../reject, yêu cầu chuyển trạng thái
    > rejected.

-   Thu hồi tự động: khi hết thời gian JIT, scheduler thật (APScheduler,
    > do Inh phụ trách) tự động thu hồi quyền và cập nhật trạng thái
    > (Chương 7.2).

-   Thu hồi thủ công: vào \"Quyền đang active\", bấm \"Thu hồi ngay\"
    > trên 1 quyền đang hoạt động → gọi POST /active-grants/{id}/revoke,
    > thu hồi ngay lập tức.

### 10.4.3. Luồng Cấu hình Phân quyền (RBAC Policy)

Đây là luồng trọng tâm cần quay kỹ trong video demo theo yêu cầu của Hào
--- tập trung giải thích cách cấu hình và custom phân quyền.

-   Vào tab \"Nhóm & phân quyền\", tìm đúng nhóm cần chỉnh (ví dụ
    > PAM-Support) trong danh sách hiển thị theo từng khối.

-   Trong bảng của nhóm đó, tìm dòng server cần cấu hình.

-   Tick/bỏ tick \"Được phép\", chỉnh số phút ở ô \"Thời lượng tối đa\",
    > tick/bỏ tick \"Cần duyệt\".

-   Bấm nút Lưu ở đúng dòng đó → giao diện gọi POST
    > /groups/{group_id}/servers/{server_id}/policy. Phía sau, nếu
    > policy giữa nhóm và server này đã tồn tại, hệ thống tự xoá rồi tạo
    > lại (vì backend chưa hỗ trợ sửa trực tiếp).

-   Chính sách áp dụng ngay cho các yêu cầu tiếp theo --- có thể minh
    > hoạ bằng cách quay lại tab \"Xin quyền\" và gửi yêu cầu mới để
    > thấy giới hạn thời gian/mức duyệt thay đổi tương ứng.

![](media/image3.png){width="6.0in" height="2.7222222222222223in"}

![](media/image4.png){width="6.0in" height="4.25in"}

## 10.5. Xử lý Lỗi & Trạng thái Đặc biệt Thường gặp

-   \"Cannot connect to Control Plane\": hiển thị khi Control Plane
    > (Inh) offline hoặc mất kết nối mạng. Nhờ kiến trúc tách bạch qua
    > api_client.py, giao diện UI vẫn tải bình thường, chỉ phần dữ liệu
    > động báo lỗi.

-   Server chưa gán nhãn phân loại (tags): đã fix lỗi TypeError
    > \'NoneType\' object is not iterable khi hiển thị danh sách server
    > không có tags, bằng cách xử lý \"s.tags or \[\]\" thay vì
    > \"s.tags\" trực tiếp trong template.

![](media/image5.png){width="6.0in" height="4.180555555555555in"}

# Chương 11: Hướng dẫn Triển khai & Vận hành

## 11.1. Yêu cầu Hệ thống

-   Docker Engine 24+ & Docker Compose v2

-   RAM tối thiểu 4GB (khuyến nghị 8GB)

-   Ổ đĩa trống 10GB+

-   Hệ điều hành: Ubuntu 22.04+ (AWS EC2) hoặc Windows 10+ (Local)

## 11.2. Triển khai Lần đầu

> Clone mã nguồn: git clone
> https://github.com/nhutHao05/privileged-access-gateway.git
>
> Khởi chạy toàn bộ service: docker compose up -d \--build
>
> Tạo cấu trúc bảng Database: docker exec -it pam_control_backend
> alembic upgrade head
>
> Nạp dữ liệu khởi tạo: docker exec -it pam_control_backend python
> seed_data.py

## 11.3. URL Truy cập trên AWS hiện tại

  -----------------------------------------------------------------------
  **Dịch vụ**                         **URL**
  ----------------------------------- -----------------------------------
  Control Plane Swagger UI            http://52.55.177.7:8000/docs

  Guacamole Web UI                    https://52.55.177.7
  -----------------------------------------------------------------------

# Chương 12: Kịch bản Demo Nghiệm thu

## 12.1. Kịch bản End-to-End 4 Bước

  -----------------------------------------------------------------------
  **Bước**                **Hành động**           **Kết quả mong đợi**
  ----------------------- ----------------------- -----------------------
  1                       Đăng nhập support1 qua  Vào được hệ thống,
                          Keycloak OIDC           Guacamole rỗng (chưa có
                                                  quyền)

  2                       support1 xin truy cập   Request pending, hiển
                          Linux SSH trong 2 phút  thị trên Dashboard
                                                  Admin

  3                       Admin admin1 bấm        Guacamole cấp quyền,
                          Approve                 support1 mở SSH không
                                                  thấy mật khẩu gốc

  4                       Hết 2 phút              APScheduler tự động thu
                                                  hồi, video lưu MinIO
                                                  kèm SHA-256 Hash
  -----------------------------------------------------------------------

## 12.2. Kịch bản Thu hồi Khẩn cấp

  -----------------------------------------------------------------------
  **Bước**                **Hành động**           **Kết quả**
  ----------------------- ----------------------- -----------------------
  1                       Support đang SSH bình   Active Grant hiển thị
                          thường                  trên Dashboard

  2                       Admin bấm nút Revoke    Quyền bị thu hồi ngay,
                                                  job APScheduler bị hủy

  3                       Support thử kết nối lại Bị từ chối (Permission
                                                  Denied)
  -----------------------------------------------------------------------

## 12.3. Kịch bản Kiểm tra Tính toàn vẹn Video

  -----------------------------------------------------------------------
  **Bước**                **Hành động**           **Kết quả**
  ----------------------- ----------------------- -----------------------
  1                       Tải file video từ MinIO File .mp4 nguyên vẹn

  2                       Tính SHA-256 Hash của   Hash khớp DB → Verified
                          file                    

  3                       Sửa đổi 1 byte trong    Hash thay đổi → Hash
                          file .mp4               Mismatch → Phát hiện
                                                  sửa đổi
  -----------------------------------------------------------------------

# Phụ lục: API Reference

## A. JIT Access Management (/access/)

  ------------------------------------------------------------------------------
  **Method**              **Endpoint**                   **Mô tả**
  ----------------------- ------------------------------ -----------------------
  POST                    /access/requests/              Gửi yêu cầu xin quyền
                                                         JIT

  GET                     /access/requests/              Lấy danh sách tất cả
                                                         yêu cầu

  POST                    /access/requests/{id}/review   Admin phê duyệt/từ chối

  GET                     /access/grants/                Lấy danh sách quyền
                                                         đang hoạt động

  POST                    /access/grants/{id}/revoke     Admin thu hồi quyền
                                                         khẩn cấp
  ------------------------------------------------------------------------------

## B. Server Management (/servers/)

  -----------------------------------------------------------------------
  **Method**              **Endpoint**            **Mô tả**
  ----------------------- ----------------------- -----------------------
  POST                    /servers/               Tạo server mới

  GET                     /servers/               Lấy danh sách server

  PUT                     /servers/{server_id}    Cập nhật thông tin
                                                  server

  DELETE                  /servers/{server_id}    Xóa server
  -----------------------------------------------------------------------

## C. User & Group Management (/auth/)

  -----------------------------------------------------------------------------------------
  **Method**              **Endpoint**                              **Mô tả**
  ----------------------- ----------------------------------------- -----------------------
  GET                     /auth/users/                              Lấy danh sách users

  GET                     /auth/groups/                             Lấy danh sách groups

  POST                    /auth/groups/                             Tạo group mới

  GET                     /auth/groups/{group_id}/users             Lấy users trong group

  POST                    /auth/users/{user_id}/groups/{group_id}   Gán user vào group

  DELETE                  /auth/users/{user_id}/groups/{group_id}   Gỡ user khỏi group
  -----------------------------------------------------------------------------------------

## D. Policy Management (/policy/)

  ----------------------------------------------------------------------------------
  **Method**              **Endpoint**                       **Mô tả**
  ----------------------- ---------------------------------- -----------------------
  POST                    /policy/group-server/              Tạo chính sách phân
                                                             quyền

  GET                     /policy/group-server/              Lấy danh sách chính
                                                             sách

  PUT                     /policy/group-server/{policy_id}   Cập nhật chính sách

  DELETE                  /policy/group-server/{policy_id}   Xóa chính sách
  ----------------------------------------------------------------------------------

## E. Audit & Recording (/audit/)

  ----------------------------------------------------------------------------------------
  **Method**              **Endpoint**                             **Mô tả**
  ----------------------- ---------------------------------------- -----------------------
  GET                     /audit/sessions/                         Lấy danh sách phiên làm
                                                                   việc

  GET                     /audit/sessions/{session_id}             Xem chi tiết 1 phiên

  POST                    /audit/sessions/{session_id}/recording   Worker gửi video +
                                                                   SHA-256 Hash

  GET                     /audit/logs/                             Lấy nhật ký thao tác hệ
                                                                   thống

  POST                    /audit/logs/                             Ghi thêm 1 nhật ký
  ----------------------------------------------------------------------------------------
