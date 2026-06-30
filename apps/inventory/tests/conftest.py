"""
Test configuration for inventory app.
"""

import pytest
from rest_framework.test import APIClient

from apps.inventory.tests.factories import PermissionFactory, UserFactory


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
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def authenticated_api_client(api_client, warehouse_keeper_user):
    """Fixture để tạo APIClient đã xác thực."""
    api_client.force_authenticate(user=warehouse_keeper_user)
    return api_client


@pytest.fixture
def admin_user():
    """Fixture để tạo user admin (có tất cả quyền)."""
    from apps.accounts.models import Permission, UserPermission

    user = UserFactory(username="admin")
    # Gán tất cả permissions
    all_perms = Permission.objects.all()
    user_perms = [UserPermission(user=user, permission=p) for p in all_perms]
    UserPermission.objects.bulk_create(user_perms)
    return user


@pytest.fixture
def warehouse_keeper_user():
    """Fixture để tạo user thủ kho (có quyền quản lý kho)."""
    from apps.accounts.models import UserPermission

    user = UserFactory(username="warehouse_keeper")

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
        UserPermission.objects.get_or_create(user=user, permission=perm)

    return user


@pytest.fixture
def regular_user():
    """Fixture để tạo user thường (chỉ có quyền xem)."""
    from apps.accounts.models import UserPermission

    user = UserFactory(username="regular_user")
    perm = PermissionFactory(code="inventory.view")
    UserPermission.objects.get_or_create(user=user, permission=perm)

    return user
