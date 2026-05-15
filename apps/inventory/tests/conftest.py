"""
Test configuration for inventory app.
"""

import pytest
from rest_framework.test import APIClient

from apps.inventory.tests.factories import PermissionFactory, RoleFactory, UserFactory


@pytest.fixture
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Database setup for tests.
    """
    with django_db_blocker.unblock():
        pass


@pytest.fixture
def api_client():
    """Fixture để tạo APIClient."""
    return APIClient()


@pytest.fixture
def admin_user():
    """Fixture để tạo user admin (có tất cả quyền)."""
    role = RoleFactory(name="Admin")
    # Tạo user với role admin
    user = UserFactory(role=role, username="admin")
    return user


@pytest.fixture
def warehouse_keeper_user():
    """Fixture để tạo user thủ kho (có quyền quản lý kho)."""
    from apps.accounts.models import RolePermission

    role = RoleFactory(name="Thủ kho")

    # Tạo và gán các permissions
    permissions = [
        "inventory.stock_in",
        "inventory.stock_in_approve",
        "inventory.stock_issue",
        "inventory.stock_issue_approve",
        "inventory.stock_transfer",
        "inventory.stock_transfer_approve",
        "inventory.view",
    ]

    for code in permissions:
        perm = PermissionFactory(code=code)
        RolePermission.objects.create(role=role, permission=perm)

    user = UserFactory(role=role, username="warehouse_keeper")
    return user


@pytest.fixture
def regular_user():
    """Fixture để tạo user thường (chỉ có quyền xem)."""
    from apps.accounts.models import RolePermission

    role = RoleFactory(name="Nhân viên")
    perm = PermissionFactory(code="inventory.view")
    RolePermission.objects.create(role=role, permission=perm)

    user = UserFactory(role=role, username="regular_user")
    return user
