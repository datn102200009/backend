import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Permission, RolePermission
from apps.inventory.tests.factories import RoleFactory, UserFactory


@pytest.fixture
def api_client():
    """Return a Django Rest Framework APIClient."""
    return APIClient()


@pytest.fixture
def authenticated_client_with_perms(api_client, db):
    """Return an authenticated client with sales order viewing permission."""
    role = RoleFactory(name="Sales Representative")
    user = UserFactory(username="sales_rep", password_hash="testpass", role=role)

    # Give sales.view_order permission
    perm, _ = Permission.objects.get_or_create(code="sales.view_order", defaults={"name": "Xem đơn hàng"})
    RolePermission.objects.get_or_create(role=role, permission=perm)

    api_client.force_authenticate(user=user)
    return api_client, user
