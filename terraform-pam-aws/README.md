# Hướng dẫn deploy PAM Gateway (Guacamole + Control Plane) lên AWS bằng Terraform

Làm theo đúng thứ tự từng bước dưới đây. Đừng nhảy cóc bước nào.

---

## Bước 0: Đợi quyền IAM có hiệu lực

Đợi Hào/AWS confirm là user IAM của ní đã ở trong group admin và quyền đã propagate xong (thường vài phút sau khi thêm vào group).

## Bước 1: Tạo Key Pair trên AWS Console (để SSH vào máy sau này)

1. Đăng nhập AWS Console → gõ tìm "EC2" → vào trang EC2
2. Nhìn menu bên trái, chọn **Key Pairs** (trong mục Network & Security)
3. Bấm **Create key pair**
4. Đặt tên: `pam-gateway-key`
5. Type: chọn **RSA**, Format: chọn **.pem**
6. Bấm **Create key pair** → trình duyệt sẽ tự tải file `pam-gateway-key.pem` về máy
7. **Copy file này vào thư mục** cùng chỗ với các file Terraform (hoặc nhớ đường dẫn để dùng SSH sau)

## Bước 2: Cài Terraform trên máy Windows

1. Vào https://developer.hashicorp.com/terraform/install
2. Tải bản Windows (amd64), giải nén ra, được file `terraform.exe`
3. Copy `terraform.exe` vào 1 thư mục cố định, ví dụ `C:\terraform\`
4. Thêm `C:\terraform\` vào biến môi trường PATH:
   - Gõ "Environment Variables" vào Windows Search → mở "Edit the system environment variables"
   - Bấm **Environment Variables** → tìm dòng `Path` trong "User variables" → **Edit** → **New** → gõ `C:\terraform\` → OK hết
5. Mở PowerShell **mới** (đóng cái cũ mở lại), gõ thử: `terraform -version` — nếu ra số phiên bản là cài xong

## Bước 3: Lấy IP thật của ní

1. Mở trình duyệt vào: https://whatismyipaddress.com/
2. Copy dòng "IPv4" (dạng `123.45.67.89`)
3. Nhớ số này, lát điền vào file `terraform.tfvars`

## Bước 4: Cài AWS CLI + đăng nhập

1. Tải AWS CLI: https://awscli.amazonaws.com/AWSCLIV2.msi → cài như bình thường
2. Mở PowerShell, gõ: `aws configure`
3. Nó hỏi lần lượt, điền theo thứ tự (lấy từ IAM user của ní trên AWS Console → Security credentials → Create access key):
   ```
   AWS Access Key ID: <dán access key>
   AWS Secret Access Key: <dán secret key>
   Default region name: us-east-1
   Default output format: json
   ```

## Bước 5: Chuẩn bị file cấu hình

1. Mở thư mục chứa các file Terraform mình đưa (`main.tf`, `variables.tf`, `outputs.tf`, `user_data.sh`, `terraform.tfvars.example`)
2. Copy file `terraform.tfvars.example` thành file mới tên `terraform.tfvars` (bỏ chữ `.example`)
3. Mở `terraform.tfvars` bằng VS Code, sửa lại:
   ```hcl
   aws_region    = "us-east-1"
   instance_type = "t3.small"
   key_pair_name = "pam-gateway-key"
   my_ip_cidr    = "123.45.67.89/32"   # thay bằng IP thật lấy ở Bước 3, nhớ giữ "/32" ở cuối
   ```
4. Lưu file (`Ctrl+S`)

## Bước 6: Chạy Terraform

Mở PowerShell, `cd` vào đúng thư mục chứa các file `.tf`:

```powershell
cd C:\đường-dẫn-tới-thư-mục-terraform-pam-aws
terraform init
```

`terraform init` sẽ tải plugin AWS về — đợi xong (thường vài chục giây).

Tiếp theo, xem trước Terraform định tạo gì (không tạo gì thật cả, chỉ xem trước):

```powershell
terraform plan
```

Đọc lướt qua, thấy nó liệt kê sẽ tạo: `aws_instance`, `aws_security_group`, `aws_eip` — đúng những gì mình cần.

**Chạy thật** (lệnh này mới thực sự tạo resource trên AWS, sẽ tốn tiền — dùng credit free $200):

```powershell
terraform apply
```

Nó hỏi confirm, gõ `yes` rồi Enter. Đợi khoảng 1-2 phút.

Xong sẽ in ra kết quả dạng:
```
public_ip = "3.xx.xx.xx"
ssh_command = "ssh -i <ten-file-key.pem> ubuntu@3.xx.xx.xx"
control_plane_url = "http://3.xx.xx.xx:8000"
guacamole_url = "http://3.xx.xx.xx:8080/guacamole"
```

**Lưu lại IP này** — đây là địa chỉ cố định của server từ giờ trở đi.

## Bước 7: SSH vào máy, kiểm tra Docker đã cài xong chưa

Đợi khoảng 1-2 phút sau khi `apply` xong (để user_data script chạy xong), rồi SSH vào:

```powershell
ssh -i pam-gateway-key.pem ubuntu@<public_ip-vừa-in-ra>
```

Nếu PowerShell báo lỗi "Permissions too open" cho file `.pem`, chạy lệnh này trước (đổi đường dẫn cho đúng):

```powershell
icacls.exe pam-gateway-key.pem /reset
icacls.exe pam-gateway-key.pem /grant:r "$($env:USERNAME):(R)"
icacls.exe pam-gateway-key.pem /inheritance:r
```

Sau khi vào được máy, gõ:
```bash
docker --version
cat user-data-done.txt
```
Nếu thấy có version Docker và file `user-data-done.txt` tồn tại → cài xong, sẵn sàng bước tiếp theo (đưa `docker-compose.yml` của Guacamole + Control Plane lên và chạy — mình sẽ hướng dẫn ở bước sau khi tới đó).

---

## Lưu ý quan trọng

- **Đừng xoá file `terraform.tfstate`** sinh ra sau khi `apply` — đây là "bộ nhớ" của Terraform, biết resource nào đã tạo. Mất file này thì Terraform không biết đường xoá/sửa lại resource cũ.
- Nhớ thêm `.gitignore` cho thư mục Terraform này (file riêng, không chung với `authorization/`):
  ```
  .terraform/
  terraform.tfstate
  terraform.tfstate.backup
  terraform.tfvars
  *.pem
  ```
  (đặc biệt `terraform.tfvars` và `*.pem` — chứa thông tin nhạy cảm, TUYỆT ĐỐI không push lên GitHub)
- Muốn xoá sạch resource đã tạo (ví dụ deploy sai muốn làm lại): `terraform destroy`
- Security Group hiện đang mở port 8000 và 8080 cho `0.0.0.0/0` (public) — tạm thời để cả nhóm dễ test, sau này nên siết lại chỉ cho IP của Inh/Vinh/Nghĩa thôi. Nói với Hào để bàn thêm khi cần.

---

## Việc CHƯA làm trong bước này (để làm sau)

- Chưa đưa `docker-compose.yml` thật của Guacamole + Control Plane lên server (mới chỉ cài Docker nền)
- Chưa đổi cấu hình app của Nghĩa/Inh để trỏ sang IP AWS mới thay vì Tailscale IP cũ
- Chưa cấu hình domain tên (dùng tạm IP số cho gọn, scope nhỏ không cần domain)

Sau khi ní chạy xong tới Bước 7 và SSH vào được, quay lại báo mình, mình hướng dẫn tiếp bước đưa Guacamole + Control Plane lên chạy.
