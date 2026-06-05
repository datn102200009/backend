"""
Production settings for datn_backend project.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa

# Production-specific settings
DEBUG = False

# SECRET_KEY validation
if SECRET_KEY == "django-insecure-*i15f-t1dfnzh)4#_y%_+raw*+%@0e$xlpv7o10^%$7%^w=&@&":
    raise ImproperlyConfigured(
        "Insecure default SECRET_KEY is used in production. Please set SECRET_KEY via environment variable."
    )

# SECURITY SETTINGS
# SSL/TLS được đảm nhận bởi Reverse Proxy (ví dụ: Nginx hoặc AWS ALB) nằm ở phía trước.
# Reverse Proxy sẽ chuyển tiếp request HTTPS và terminate SSL tại đó, rồi gửi request HTTP thông thường vào Django.
# Do đó SECURE_SSL_REDIRECT được đặt thành False để tránh vòng lặp chuyển hướng vô hạn (infinite redirect loop).
# SECURE_PROXY_SSL_HEADER giúp Django nhận biết request gốc là HTTPS thông qua Header X-Forwarded-Proto.
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# HSTS Settings
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Security Headers
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_SECURITY_POLICY = {
    "default-src": ("'self'",),
}

# Simplified static files storage for production
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Caching for production
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://redis:6379/1",
    }
}

# Email backend for production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

# Database backup
DATABASES["default"]["CONN_MAX_AGE"] = 600

# Allowed hosts from environment
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost").split(",")
