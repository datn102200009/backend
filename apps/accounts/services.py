"""
Services for accounts app.
"""

from django.contrib.auth.hashers import check_password
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.common.xlib.exceptions import InvalidCredentialsException, NotFoundException, ValidationException


@transaction.atomic
def auth_login(*, username: str, password: str) -> dict:
    """
    Xác thực người dùng và sinh JWT token.

    Args:
        username: Tên đăng nhập (username)
        password: Mật khẩu

    Returns:
        Dict: Thông tin access, refresh token và thông tin user
    """
    # Tim user theo username
    user = User.objects.filter(username=username).first()
    generic_invalid_msg = "Tài khoản hoặc mật khẩu không chính xác."

    if not user:
        raise InvalidCredentialsException(generic_invalid_msg)

    # Kiểm tra password
    if not check_password(password, user.password_hash):
        # Fallback check in case dev environment uses plaintext passwords
        if password != user.password_hash:
            raise InvalidCredentialsException(generic_invalid_msg)

    if not user.is_active:
        raise InvalidCredentialsException(generic_invalid_msg)

    # Lấy full_name từ Employee nếu có liên kết
    full_name = ""
    if user.employee_id:
        from apps.master_data.models import Employee

        emp = Employee.objects.filter(employee_id=user.employee_id).first()
        if emp:
            full_name = emp.full_name

    # Update last login timestamp
    from django.utils import timezone

    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    # Tạo JWT token
    refresh = RefreshToken.for_user(user)
    direct_perms = set(user.direct_permissions.values_list("permission__code", flat=True))
    permissions = list(direct_perms)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user_id": str(user.id),
        "username": user.username,
        "full_name": full_name,
        "permissions": permissions,
    }


@transaction.atomic
def user_create(
    *,
    employee_id: str,
    username: str,
    password: str,
    direct_permissions: list[str] = None,
    creator: User = None,
) -> User:
    """
    Tạo tài khoản User mới liên kết với Employee.
    """
    if creator:
        from apps.common.xlib.permissions import PermissionChecker

        PermissionChecker.check_permission(creator, "accounts.add_user")

    from apps.master_data.models import Employee

    employee = Employee.objects.filter(employee_id=employee_id, employment_status="active").first()
    if not employee:
        raise ValidationException("Nhân viên không tồn tại hoặc đã nghỉ việc.")

    if User.objects.filter(employee_id=employee_id).exists():
        raise ValidationException("Nhân viên này đã được liên kết với một tài khoản khác.")

    if User.objects.filter(username=username).exists():
        raise ValidationException(f"Tên đăng nhập '{username}' đã tồn tại.")

    from django.contrib.auth.hashers import make_password

    from apps.accounts.models import Permission, UserPermission
    from apps.common.services import create_system_log

    user = User.objects.create(
        username=username,
        password_hash=make_password(password),
        employee_id=employee_id,
        is_active=True,
    )

    if direct_permissions:
        perms = Permission.objects.filter(code__in=direct_permissions)
        user_perms = [UserPermission(user=user, permission=p) for p in perms]
        UserPermission.objects.bulk_create(user_perms)

    create_system_log(
        user=creator,
        action="create",
        table_name="user",
        record_id=str(user.id),
        new_value={
            "username": username,
            "employee_id": employee_id,
            "direct_permissions": direct_permissions or [],
        },
        allowed_permissions=[],
    )
    return user


@transaction.atomic
def user_update(
    *,
    user_id: str,
    direct_permissions: list[str] = None,
    updater: User = None,
) -> User:
    """
    Cập nhật vai trò và các quyền gán trực tiếp cho User.
    """
    if updater:
        from apps.common.xlib.permissions import PermissionChecker

        PermissionChecker.check_permission(updater, "accounts.change_user")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise NotFoundException("Tài khoản người dùng không tồn tại.")

    from apps.accounts.models import Permission, UserPermission
    from apps.common.services import create_system_log

    old_direct_perms = list(user.direct_permissions.values_list("permission__code", flat=True))

    # Cập nhật direct permissions (đồng bộ)
    user.direct_permissions.all().delete()
    if direct_permissions:
        perms = Permission.objects.filter(code__in=direct_permissions)
        user_perms = [UserPermission(user=user, permission=p) for p in perms]
        UserPermission.objects.bulk_create(user_perms)

    # Xóa cache quyền của user để nạp lại
    if hasattr(user, "_perm_cache"):
        delattr(user, "_perm_cache")

    create_system_log(
        user=updater,
        action="update",
        table_name="user",
        record_id=str(user.id),
        old_value={
            "direct_permissions": old_direct_perms,
        },
        new_value={
            "direct_permissions": direct_permissions or [],
        },
        allowed_permissions=[],
    )
    return user


@transaction.atomic
def user_change_password(
    *,
    user_id: str,
    password: str,
    updater: User = None,
) -> None:
    """
    Đổi mật khẩu cho một tài khoản cụ thể.
    """
    if updater:
        from apps.common.xlib.permissions import PermissionChecker

        PermissionChecker.check_permission(updater, "accounts.change_user")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise NotFoundException("Tài khoản người dùng không tồn tại.")

    from django.contrib.auth.hashers import make_password

    from apps.common.services import create_system_log

    user.password_hash = make_password(password)
    user.save(update_fields=["password_hash"])

    create_system_log(
        user=updater,
        action="change_password",
        table_name="user",
        record_id=str(user.id),
        new_value={"message": "Mật khẩu đã được cập nhật thành công."},
        allowed_permissions=[],
    )


@transaction.atomic
def user_delete(
    *,
    user_id: str,
    deleter: User = None,
) -> None:
    """
    Xóa tài khoản người dùng khỏi hệ thống.
    """
    if deleter:
        from apps.common.xlib.permissions import PermissionChecker

        PermissionChecker.check_permission(deleter, "accounts.delete_user")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise NotFoundException("Tài khoản người dùng không tồn tại.")

    username = user.username
    user.delete()

    from apps.common.services import create_system_log

    create_system_log(
        user=deleter,
        action="delete",
        table_name="user",
        record_id=str(user_id),
        old_value={"username": username},
        new_value=None,
        allowed_permissions=[],
    )
