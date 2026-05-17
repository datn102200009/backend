"""
Test configuration for accounts app.
"""

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
def authenticated_api_client(api_client, db):
    """Return authenticated API client."""
    from apps.inventory.tests.factories import UserFactory

    user = UserFactory(username="testuser", password_hash="testpass")
    api_client.force_authenticate(user=user)
    return api_client
