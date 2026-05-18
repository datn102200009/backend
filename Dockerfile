# ==================== Builder Stage ====================
FROM python:3.13-slim as builder

WORKDIR /app

# Cài đặt thư viện hệ thống cần thiết để build (như gcc cho C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Tạo Virtual Environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy và cài đặt thư viện Python (tận dụng cache layer)
COPY requirements/base.txt .
RUN pip install --no-cache-dir -r base.txt

# ==================== Production Stage ====================
FROM python:3.13-slim

WORKDIR /app

# Biến môi trường tối ưu hoá Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Cài đặt thư viện hệ thống runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Khởi tạo user non-root (appuser)
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment từ builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy toàn bộ code vào image với quyền sở hữu của appuser
COPY --chown=appuser:appuser . .

# Đảm bảo các thư mục ghi đè (logs, media, static) tồn tại và cấp quyền cho appuser
RUN mkdir -p logs media static && chown -R appuser:appuser logs media static /app

# Gom static files (nếu cần thiết cho trang admin của Django)
RUN python manage.py collectstatic --noinput || true

# Chuyển sang sử dụng user appuser để tăng tính bảo mật
USER appuser

# Khai báo port
EXPOSE 8000

# Kiểm tra trạng thái "sống" của ứng dụng
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(2); s.connect(('127.0.0.1', 8000)); s.close()" || exit 1

# Khởi chạy gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "datn_backend.wsgi:application"]
