"""
Permission checking utilities for authorization.
Tái sử dụng cho toàn bộ ứng dụng.
"""

from typing import Optional

from apps.accounts.models import User
from apps.common.xlib.exceptions import PermissionException


class PermissionChecker:
    """
    Utility class để kiểm tra quyền của user.
    """

    @staticmethod
    def check_permission(user: Optional[User], permission_code: str) -> None:
        """
        Kiểm tra xem user có quyền được chỉ định hay không.

        Args:
            user: User object để kiểm tra
            permission_code: Code của permission cần kiểm tra (ví dụ: "inventory.stock_in")

        Raises:
            PermissionException: Nếu user không có quyền

        Ví dụ:
            PermissionChecker.check_permission(user, "inventory.stock_in")
        """
        if user is None:
            raise PermissionException("User không được xác thực")

        if not user.is_active:
            raise PermissionException("Tài khoản người dùng đã bị vô hiệu hóa")

        if user.role_id is None:
            raise PermissionException("Người dùng không được gán vai trò")

        if not hasattr(user, "_perm_cache"):
            user._perm_cache = set(user.role.permissions.values_list("permission__code", flat=True))

        if permission_code not in user._perm_cache:
            raise PermissionException(f"Người dùng không có quyền: {permission_code}")

    @staticmethod
    def has_permission(user: Optional[User], permission_code: str) -> bool:
        """
        Kiểm tra xem user có quyền được chỉ định hay không.
        Trả về boolean thay vì raise exception.

        Args:
            user: User object để kiểm tra
            permission_code: Code của permission cần kiểm tra

        Returns:
            True nếu user có quyền, False nếu không

        Ví dụ:
            if PermissionChecker.has_permission(user, "inventory.stock_in"):
                # Thực hiện hành động
        """
        try:
            PermissionChecker.check_permission(user, permission_code)
            return True
        except PermissionException:
            return False

    @staticmethod
    def check_multiple_permissions(user: Optional[User], permission_codes: list, require_all: bool = True) -> None:
        """
        Kiểm tra xem user có một hoặc tất cả các quyền được chỉ định hay không.

        Args:
            user: User object để kiểm tra
            permission_codes: Danh sách các permission codes
            require_all: Nếu True, yêu cầu tất cả quyền. Nếu False, yêu cầu ít nhất một quyền.

        Raises:
            PermissionException: Nếu điều kiện không được đáp ứng

        Ví dụ:
            # Yêu cầu cả hai quyền
            PermissionChecker.check_multiple_permissions(
                user,
                ["inventory.stock_in", "inventory.approve"],
                require_all=True
            )
        """
        if user is None:
            raise PermissionException("User không được xác thực")

        if not user.is_active:
            raise PermissionException("Tài khoản người dùng đã bị vô hiệu hóa")

        if user.role_id is None:
            raise PermissionException("Người dùng không được gán vai trò")

        if not hasattr(user, "_perm_cache"):
            user._perm_cache = set(user.role.permissions.values_list("permission__code", flat=True))

        user_permission_codes = user._perm_cache

        if require_all:
            # Kiểm tra xem user có tất cả quyền hay không
            missing_permissions = set(permission_codes) - user_permission_codes
            if missing_permissions:
                raise PermissionException(f"Người dùng thiếu quyền: {', '.join(missing_permissions)}")
        else:
            # Kiểm tra xem user có ít nhất một quyền hay không
            has_any = bool(user_permission_codes & set(permission_codes))
            if not has_any:
                raise PermissionException(f"Người dùng không có bất kỳ quyền nào: {', '.join(permission_codes)}")
