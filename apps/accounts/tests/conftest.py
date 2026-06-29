import pytest

from apps.common.tests.conftest import admin_user, api_client, mock_permission, regular_user


@pytest.fixture
def authenticated_api_client(api_client, db):
    """Return authenticated API client."""
    from apps.inventory.tests.factories import UserFactory

    user = UserFactory(username="testuser", password_hash="testpass")
    api_client.force_authenticate(user=user)
    return api_client
