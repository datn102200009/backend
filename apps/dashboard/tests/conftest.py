import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Permission, UserPermission
from apps.common.tests.conftest import admin_user, mock_permission, regular_user
from apps.inventory.tests.factories import UserFactory


@pytest.fixture
def api_client():
    """Return a Django Rest Framework APIClient."""
    return APIClient()


@pytest.fixture
def authenticated_client_with_perms(api_client, db):
    """Return an authenticated client with sales order viewing permission."""
    user = UserFactory(username="sales_rep", password_hash="testpass")

    # Give sales.view_order permission
    perm, _ = Permission.objects.get_or_create(code="sales.view_order", defaults={"name": "Xem đơn hàng"})
    UserPermission.objects.get_or_create(user=user, permission=perm)

    api_client.force_authenticate(user=user)
    return api_client, user
