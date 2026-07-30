output "public_ip" {
  description = "IP tinh (Elastic IP) cua may chu tren AWS"
  value       = aws_eip.pam_eip.public_ip
}

output "ssh_command" {
  description = "Lenh SSH de vao may"
  value       = "ssh -i <ten-file-key.pem> ubuntu@${aws_eip.pam_eip.public_ip}"
}

output "control_plane_url" {
  description = "URL Control Plane API tu ben ngoai"
  value       = "http://${aws_eip.pam_eip.public_ip}:8000"
}

output "guacamole_url" {
  description = "URL Guacamole web UI tu ben ngoai (qua nginx reverse proxy, cert tu ky)"
  value       = "https://${aws_eip.pam_eip.public_ip}"
}

output "demo_target_ip" {
  description = "Public IP cua EC2 demo target (khong dung Elastic IP, co the doi neu stop/start)"
  value       = aws_instance.demo_target.public_ip
}

output "demo_target_username" {
  description = "Username SSH cua EC2 demo target"
  value       = "ubuntu"
}

output "demo_target_password" {
  description = "Password SSH cua EC2 demo target"
  value       = random_password.demo_target_password.result
  sensitive   = true
}
