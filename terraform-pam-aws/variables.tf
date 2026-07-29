variable "aws_region" {
  description = "AWS region để deploy"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "Loại EC2 instance. Guacamole khá ăn RAM nên đừng chọn t3.micro (dễ bị OOM)."
  type        = string
  default     = "t3.small"
}

variable "key_pair_name" {
  description = "Tên Key Pair EC2 dùng để SSH vào máy (tạo sẵn trên AWS Console trước, xem README bước 1)"
  type        = string
}

variable "my_ip_cidr" {
  description = "IP của ní (dạng x.x.x.x/32) để giới hạn ai được SSH vào máy — TUYỆT ĐỐI không để 0.0.0.0/0 cho port 22"
  type        = string
}

variable "root_volume_size_gb" {
  description = "Dung lượng ổ đĩa gốc (GB). Guacamole + Postgres + Control Plane cần kha khá chỗ."
  type        = number
  default     = 30
}

variable "project_name" {
  description = "Tiền tố đặt tên cho các resource, để dễ nhận biết trên AWS Console"
  type        = string
  default     = "pam-gateway"
}

variable "team_ips_cidr" {
  description = "Danh sach IP cua cac thanh vien trong nhom (dang x.x.x.x/32), duoc phep goi Control Plane API (port 8000)."
  type        = list(string)
}
