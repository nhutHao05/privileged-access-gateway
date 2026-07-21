FROM python:3.10-slim

# Cài đặt các thư viện cần thiết để biên dịch guacenc
RUN apt-get update && apt-get install -y \
    build-essential \
    libcairo2-dev \
    libjpeg-dev \
    libpng-dev \
    libtool-bin \
    libossp-uuid-dev \
    libvncserver-dev \
    freerdp2-dev \
    libssh2-1-dev \
    libtelnet-dev \
    libwebsockets-dev \
    libpulse-dev \
    libvorbis-dev \
    libwebp-dev \
    libssl-dev \
    libpango1.0-dev \
    libswscale-dev \
    libavcodec-dev \
    libavutil-dev \
    libavformat-dev \
    guacamole-server \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirement và cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code
COPY . .

# Lệnh chạy Worker
CMD ["python", "worker.py"]
