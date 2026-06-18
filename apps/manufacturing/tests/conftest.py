"""
Test configuration for manufacturing app.
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
    from apps.accounts.models import UserPermission

    # Gán full quyền manufacturing
    permissions = [
        "manufacturing.bom_create",
        "manufacturing.bom_update",
        "manufacturing.bom_delete",
        "manufacturing.bom_view",
        "manufacturing.work_order_create",
        "manufacturing.work_order_approve",
        "manufacturing.work_order_declare",
        "manufacturing.work_order_complete",
        "manufacturing.work_order_cancel",
        "manufacturing.work_order_view",
    ]
    user = UserFactory(username="admin")
    for code in permissions:
        perm = PermissionFactory(code=code)
        UserPermission.objects.get_or_create(user=user, permission=perm)

    return user


@pytest.fixture
def production_user():
    """Fixture để tạo user sản xuất (có quyền quản lý BOM và WO)."""
    from apps.accounts.models import UserPermission

    # Tạo và gán các permissions
    permissions = [
        "manufacturing.bom_create",
        "manufacturing.bom_update",
        "manufacturing.bom_delete",
        "manufacturing.bom_view",
        "manufacturing.work_order_create",
        "manufacturing.work_order_approve",
        "manufacturing.work_order_declare",
        "manufacturing.work_order_complete",
        "manufacturing.work_order_cancel",
        "manufacturing.work_order_view",
    ]

    user = UserFactory(username="production_user")
    for code in permissions:
        perm = PermissionFactory(code=code)
        UserPermission.objects.get_or_create(user=user, permission=perm)

    return user


@pytest.fixture
def regular_user():
    """Fixture để tạo user thường (không có quyền manufacturing)."""
    from apps.accounts.models import UserPermission

    user = UserFactory(username="regular_user")
    perm = PermissionFactory(code="other.view")
    UserPermission.objects.get_or_create(user=user, permission=perm)

    return user
