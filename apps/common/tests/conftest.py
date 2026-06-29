"""
Shared pytest fixtures for all apps.
"""

from unittest.mock import patch

import pytest


@pytest.fixture
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Database setup for tests.
    """
    with django_db_blocker.unblock():
        pass


@pytest.fixture
def api_client():
    """Return DRF API client."""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def admin_user(db):
    """Return a common admin user."""
    from apps.inventory.tests.factories import RoleFactory, UserFactory

    role, _ = RoleFactory.objects.get_or_create(name="Admin")
    user = UserFactory(role=role, username="admin_common")
    return user


@pytest.fixture
def regular_user(db):
    """Return a common regular user."""
    from apps.inventory.tests.factories import RoleFactory, UserFactory

    role, _ = RoleFactory.objects.get_or_create(name="Regular User")
    user = UserFactory(role=role, username="regular_common")
    return user


@pytest.fixture
def authenticated_api_client(api_client, regular_user):
    """Return an authenticated API client using regular user."""
    api_client.force_authenticate(user=regular_user)
    return api_client


@pytest.fixture
def mock_permission():
    """Fixture to bypass permission checks when active."""
    with patch("apps.common.xlib.permissions.PermissionChecker.check_permission", return_value=True) as mock:
        yield mock
