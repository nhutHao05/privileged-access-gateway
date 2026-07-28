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
  description = "URL Guacamole web UI tu ben ngoai"
  value       = "http://${aws_eip.pam_eip.public_ip}:8080/guacamole"
}
