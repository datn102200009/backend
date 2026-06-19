import pytest
from rest_framework.test import APIClient

from apps.inventory.tests.factories import RoleFactory, UserFactory


@pytest.mark.django_db
class TestAuthLoginAPI:

    def test_login_endpoint_success(self, api_client):
        # Arrange
        user = UserFactory(username="api_user", password_hash="api_pass123")

        # Act
        response = api_client.post(
            "/api/v1/accounts/auth/login/",
            data={"username": "api_user", "password": "api_pass123"},
            format="json",
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access" in data
        assert "refresh" in data
        assert data["username"] == "api_user"
        assert "permissions" in data
        assert isinstance(data["permissions"], list)

    def test_login_endpoint_returns_permissions(self, api_client):
        # Arrange
        from apps.accounts.models import Permission, UserPermission

        perm, _ = Permission.objects.get_or_create(
            code="accounts.test_permission", defaults={"name": "Test Permission"}
        )
        user = UserFactory(username="perm_user", password_hash="pass123")
        UserPermission.objects.create(user=user, permission=perm)

        # Act
        response = api_client.post(
            "/api/v1/accounts/auth/login/",
            data={"username": "perm_user", "password": "pass123"},
            format="json",
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "permissions" in data
        assert "accounts.test_permission" in data["permissions"]

    def test_login_endpoint_missing_fields(self, api_client):
        # Act
        response = api_client.post(
            "/api/v1/accounts/auth/login/",
            data={"username": "api_user"},
            format="json",  # missing password
        )

        # Assert
        assert response.status_code == 400
        assert "password" in response.json()["errors"]

    def test_login_endpoint_invalid_credentials(self, api_client):
        user = UserFactory(username="v_user", password_hash="valid_pass")
        generic_msg = "Tài khoản hoặc mật khẩu không chính xác."

        # Act
        response = api_client.post(
            "/api/v1/accounts/auth/login/",
            data={"username": "v_user", "password": "invalid_pass"},
            format="json",
        )

        # Assert
        assert response.status_code == 401
        assert response.json()["error"] == generic_msg

    def test_login_endpoint_not_found(self, api_client):
        generic_msg = "Tài khoản hoặc mật khẩu không chính xác."
        # Act
        response = api_client.post(
            "/api/v1/accounts/auth/login/",
            data={"username": "no_user", "password": "123"},
            format="json",
        )

        # Assert
        assert response.status_code == 401
        assert response.json()["error"] == generic_msg

    def test_login_endpoint_inactive_user(self, api_client):
        user = UserFactory(username="in_user", password_hash="pass", is_active=False)
        generic_msg = "Tài khoản hoặc mật khẩu không chính xác."

        # Act
        response = api_client.post(
            "/api/v1/accounts/auth/login/",
            data={"username": "in_user", "password": "pass"},
            format="json",
        )

        # Assert
        assert response.status_code == 401
        assert response.json()["error"] == generic_msg


@pytest.mark.django_db
class TestRoleListAPI:

    def test_role_list_unauthenticated(self, api_client):
        # Act
        response = api_client.get("/api/v1/accounts/roles/")

        # Assert
        assert response.status_code == 401

    def test_role_list_success(self, authenticated_api_client):
        # Arrange
        # authenticated_api_client is already authenticated as a user.
        # Create some extra roles to verify listing functionality
        RoleFactory(name="Manager")
        RoleFactory(name="Supervisor")

        # Act
        response = authenticated_api_client.get("/api/v1/accounts/roles/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        role_names = [r["name"] for r in data]
        assert "Manager" in role_names
        assert "Supervisor" in role_names


@pytest.mark.django_db
class TestAuthMeAPI:

    def test_auth_me_unauthenticated(self, api_client):
        response = api_client.get("/api/v1/accounts/auth/me/")
        assert response.status_code == 401

    def test_auth_me_success(self, api_client):
        from apps.accounts.models import Permission, UserPermission

        perm, _ = Permission.objects.get_or_create(
            code="accounts.test_permission", defaults={"name": "Test Permission"}
        )
        user = UserFactory(username="perm_user")
        UserPermission.objects.create(user=user, permission=perm)
        api_client.force_authenticate(user=user)

        response = api_client.get("/api/v1/accounts/auth/me/")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "perm_user"
        assert "accounts.test_permission" in data["permissions"]
        assert "role" not in data
