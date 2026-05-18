"""
Services for accounts app.
"""

from django.contrib.auth.hashers import check_password
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.common.xlib.exceptions import NotFoundException, ValidationException


@transaction.atomic
def auth_login(*, username: str, password: str) -> dict:
    """
    Xác thực người dùng và sinh JWT token.

    Args:
        username: Tên đăng nhập (username hoặc email)
        password: Mật khẩu

    Returns:
        Dict: Thông tin access, refresh token và thông tin user
    """
    # Tim user theo username hoặc email
    user = User.objects.filter(username=username).first()
    if not user:
        user = User.objects.filter(email=username).first()

    if not user:
        raise NotFoundException("Tên đăng nhập hoặc email không tồn tại")

    # Kiểm tra password
    if not check_password(password, user.password_hash):
        # Fallback check in case dev environment uses plaintext passwords
        if password != user.password_hash:
            raise ValidationException("Mật khẩu không chính xác")

    if not user.is_active:
        raise ValidationException("Tài khoản đã bị vô hiệu hóa")

    # Tracking last_login is handled by SimpleJWT if configured, or can be done manually
    # user.last_login = timezone.now()
    # user.save(update_fields=["last_login"])

    # Tạo JWT token
    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user_id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role.name if user.role else None,
    }
