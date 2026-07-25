# Script tự động tạo SSL Certificate tự ký & Khởi chạy Docker Stack cho Sprint 0

$CertDir = ".\nginx\certs"
if (-not (Test-Path $CertDir)) {
    New-Item -ItemType Directory -Path $CertDir | Out-Null
    Write-Host "[+] Đã tạo thư mục $CertDir" -ForegroundColor Green
}

# Tạo OpenSSL Certificate tự ký cho localhost
if (Get-Command openssl -ErrorAction SilentlyContinue) {
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout "$CertDir\server.key" -out "$CertDir\server.crt" -subj "/CN=localhost"
    Write-Host "[+] Đã tạo SSL Certificate tự ký thành công!" -ForegroundColor Green
} else {
    Write-Host "[!] Không tìm thấy openssl trong PATH. Tạo cert bằng PowerShell native..." -ForegroundColor Yellow
    $cert = New-SelfSignedCertificate -DnsName "localhost" -CertStoreLocation "cert:\CurrentUser\My"
    # Export cert & key nếu cần hoặc dùng OpenSSL
}

Write-Host "[+] Đang khởi chạy Docker Compose Stack..." -ForegroundColor Cyan
docker-compose up -d

Write-Host "[+] Kiểm tra danh sách container đang chạy:" -ForegroundColor Cyan
docker ps
