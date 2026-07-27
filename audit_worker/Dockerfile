FROM guacamole/guacd:1.5.4

# Chuyển sang quyền root để cài đặt thêm thư viện
USER root

# guacd 1.5.4 được build trên nền Alpine Linux, ta cài thêm Python3 và Pip
RUN apk update && apk add --no-cache python3 py3-pip

WORKDIR /app

# Copy requirement và cài đặt
COPY requirements.txt .
# Alpine dùng pip mới có thể báo lỗi PEP668, dùng --break-system-packages
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages || pip3 install --no-cache-dir -r requirements.txt

# Copy toàn bộ code worker
COPY . .

# Vô hiệu hóa ENTRYPOINT mặc định của guacd (vốn dùng để chạy server)
ENTRYPOINT []

# Lệnh chạy Worker của Sang
CMD ["python3", "worker.py"]
