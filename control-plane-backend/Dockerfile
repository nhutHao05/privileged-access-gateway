# Sử dụng Python 3.12 slim image cho nhẹ và chuẩn hóa
FROM python:3.12-slim

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Cấu hình môi trường Python tối ưu
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Cài đặt thư viện hệ thống cần thiết cho PostgreSQL & build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy file requirements và cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn ứng dụng
COPY . .

# Expose port 8000
EXPOSE 8000

# Lệnh chạy FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
