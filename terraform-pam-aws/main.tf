terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ---------------------------------------------------------------------------
# Dùng default VPC có sẵn của AWS — KHÔNG tạo VPC riêng, đúng scope nhỏ gọn.
# ---------------------------------------------------------------------------
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Lấy AMI Ubuntu 22.04 mới nhất (chính chủ Canonical, không phải hàng lạ)
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ---------------------------------------------------------------------------
# Security Group — chỉ mở đúng port cần thiết
# ---------------------------------------------------------------------------
resource "aws_security_group" "pam_sg" {
  name        = "${var.project_name}-sg"
  description = "Security group for PAM Gateway (Guacamole + Control Plane) on AWS"
  vpc_id      = data.aws_vpc.default.id

  # SSH — CHỈ cho IP của ní, không mở public
  ingress {
    description = "SSH tu may cua Nghia"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  # Control Plane API (Inh) - port 8000, cho cả nhóm gọi vào
  ingress {
    description = "Control Plane API"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # tạm mở rộng, có thể siết lại sau theo IP từng người
  }

  # Guacamole web UI - port 8080 (nếu cần truy cập trực tiếp để debug)
  # HTTP - port 80 (redirect sang HTTPS)
  ingress {
    description = "HTTP for nginx redirect"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS - port 443 (cong chinh vao Guacamole qua nginx)
  ingress {
    description = "HTTPS via nginx"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Cho phep moi ket noi ra ngoai"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.project_name}-sg"
    Project = "PAM Gateway"
  }
}

# ---------------------------------------------------------------------------
# EC2 Instance
# ---------------------------------------------------------------------------
resource "aws_instance" "pam_server" {
  ami                    = "ami-0446f93cefa2981e5"  # ghim cung, khong auto-update nua
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.pam_sg.id]

  root_block_device {
    volume_size = var.root_volume_size_gb
    volume_type = "gp3"
  }

  user_data = file("${path.module}/user_data.sh")

  tags = {
    Name    = "${var.project_name}-server"
    Project = "PAM Gateway"
  }
}

# ---------------------------------------------------------------------------
# Elastic IP — để IP không đổi mỗi lần restart instance
# ---------------------------------------------------------------------------
resource "aws_eip" "pam_eip" {
  instance = aws_instance.pam_server.id
  domain   = "vpc"

  tags = {
    Name = "${var.project_name}-eip"
  }
}
