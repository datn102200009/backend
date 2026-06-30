import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.inventory.tests.factories import PermissionFactory, UserFactory


@pytest.mark.django_db
class TestCustomJWTAuthentication:

    def test_access_protected_route_with_valid_token(self, api_client):
        # Arrange: Setup user with permissions
        from apps.accounts.models import UserPermission

        perm = PermissionFactory(code="inventory.view")
        user = UserFactory(username="secure_usr")
        UserPermission.objects.create(user=user, permission=perm)

        # Generate valid token
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Act
        response = api_client.get(
            "/api/v1/inventory/stock-entry/list/",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        # Assert
        if response.status_code == 500:
            print(response.json())
        assert response.status_code == 200

    def test_access_protected_route_without_token(self, api_client):
        # Act
        response = api_client.get("/api/v1/inventory/stock-entry/list/")

        # Assert
        assert response.status_code == 401

    def test_access_protected_route_with_invalid_token(self, api_client):
        # Act
        response = api_client.get(
            "/api/v1/inventory/stock-entry/list/",
            HTTP_AUTHORIZATION="Bearer invalid.token.string",
        )

        # Assert
        assert response.status_code == 401
