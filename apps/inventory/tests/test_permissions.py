"""
Tests for permission checking utilities.
"""

import pytest

from apps.accounts.models import Permission, RolePermission
from apps.common.xlib.exceptions import PermissionException
from apps.common.xlib.permissions import PermissionChecker
from apps.inventory.tests.factories import PermissionFactory, RoleFactory, UserFactory


@pytest.mark.django_db
class TestPermissionChecker:
    """Test suite cho PermissionChecker."""

    def test_check_permission_success(self):
        """Test kiểm tra quyền thành công."""
        # Setup
        role = RoleFactory(name="Thủ kho")
        permission = PermissionFactory(code="inventory.stock_in")
        RolePermission.objects.create(role=role, permission=permission)
        user = UserFactory(role=role)

        # Test
        PermissionChecker.check_permission(user, "inventory.stock_in")
        # Nếu không raise exception, test pass

    def test_check_permission_denied(self):
        """Test kiểm tra quyền bị từ chối."""
        # Setup
        role = RoleFactory(name="Nhân viên")
        user = UserFactory(role=role)

        # Test
        with pytest.raises(PermissionException) as exc_info:
            PermissionChecker.check_permission(user, "inventory.stock_in")

        assert "không có quyền" in str(exc_info.value)

    def test_check_permission_no_user(self):
        """Test kiểm tra quyền khi user là None."""
        with pytest.raises(PermissionException) as exc_info:
            PermissionChecker.check_permission(None, "inventory.stock_in")

        assert "User không được xác thực" in str(exc_info.value)

    def test_check_permission_inactive_user(self):
        """Test kiểm tra quyền của user không hoạt động."""
        # Setup
        role = RoleFactory()
        user = UserFactory(role=role, is_active=False)

        # Test
        with pytest.raises(PermissionException) as exc_info:
            PermissionChecker.check_permission(user, "inventory.stock_in")

        assert "vô hiệu hóa" in str(exc_info.value)

    def test_check_permission_no_role(self):
        """Test kiểm tra quyền của user không có role."""
        # Setup
        user = UserFactory(role=None)

        # Test
        with pytest.raises(PermissionException) as exc_info:
            PermissionChecker.check_permission(user, "inventory.stock_in")

        assert "không được gán vai trò" in str(exc_info.value)

    def test_has_permission_true(self):
        """Test has_permission trả về True."""
        # Setup
        role = RoleFactory()
        permission = PermissionFactory(code="inventory.stock_in")
        RolePermission.objects.create(role=role, permission=permission)
        user = UserFactory(role=role)

        # Test
        result = PermissionChecker.has_permission(user, "inventory.stock_in")
        assert result is True

    def test_has_permission_false(self):
        """Test has_permission trả về False."""
        # Setup
        role = RoleFactory()
        user = UserFactory(role=role)

        # Test
        result = PermissionChecker.has_permission(user, "inventory.stock_in")
        assert result is False

    def test_check_multiple_permissions_all_granted(self):
        """Test kiểm tra nhiều quyền - cả hai được cấp."""
        # Setup
        role = RoleFactory()
        perm1 = PermissionFactory(code="inventory.stock_in")
        perm2 = PermissionFactory(code="inventory.stock_in_approve")
        RolePermission.objects.create(role=role, permission=perm1)
        RolePermission.objects.create(role=role, permission=perm2)
        user = UserFactory(role=role)

        # Test
        PermissionChecker.check_multiple_permissions(
            user,
            ["inventory.stock_in", "inventory.stock_in_approve"],
            require_all=True,
        )
        # Không raise exception

    def test_check_multiple_permissions_some_missing(self):
        """Test kiểm tra nhiều quyền - thiếu một."""
        # Setup
        role = RoleFactory()
        perm1 = PermissionFactory(code="inventory.stock_in")
        RolePermission.objects.create(role=role, permission=perm1)
        user = UserFactory(role=role)

        # Test
        with pytest.raises(PermissionException) as exc_info:
            PermissionChecker.check_multiple_permissions(
                user,
                ["inventory.stock_in", "inventory.stock_in_approve"],
                require_all=True,
            )

        assert "thiếu quyền" in str(exc_info.value)

    def test_check_multiple_permissions_any_granted(self):
        """Test kiểm tra nhiều quyền - ít nhất một được cấp."""
        # Setup
        role = RoleFactory()
        perm1 = PermissionFactory(code="inventory.stock_in")
        RolePermission.objects.create(role=role, permission=perm1)
        user = UserFactory(role=role)

        # Test
        PermissionChecker.check_multiple_permissions(
            user,
            ["inventory.stock_in", "inventory.stock_in_approve"],
            require_all=False,
        )
        # Không raise exception

    def test_check_multiple_permissions_none_granted(self):
        """Test kiểm tra nhiều quyền - không có quyền nào."""
        # Setup
        role = RoleFactory()
        user = UserFactory(role=role)

        # Test
        with pytest.raises(PermissionException) as exc_info:
            PermissionChecker.check_multiple_permissions(
                user,
                ["inventory.stock_in", "inventory.stock_in_approve"],
                require_all=False,
            )

        assert "không có bất kỳ quyền nào" in str(exc_info.value)
