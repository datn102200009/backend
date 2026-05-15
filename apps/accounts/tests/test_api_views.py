import pytest
from rest_framework.test import APIClient

from apps.inventory.tests.factories import UserFactory


@pytest.mark.django_db
class TestAuthLoginAPI:

    @pytest.fixture
    def api_client(self):
        return APIClient()

    def test_login_endpoint_success(self, api_client):
        # Arrange
        user = UserFactory(username="api_user", password_hash="api_pass123")

        # Act
        response = api_client.post(
            "/api/v1/accounts/auth/login/", data={"username": "api_user", "password": "api_pass123"}, format="json"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access" in data
        assert "refresh" in data
        assert data["username"] == "api_user"

    def test_login_endpoint_missing_fields(self, api_client):
        # Act
        response = api_client.post(
            "/api/v1/accounts/auth/login/", data={"username": "api_user"}, format="json"  # missing password
        )

        # Assert
        assert response.status_code == 400
        assert "password" in response.json()["errors"]

    def test_login_endpoint_invalid_credentials(self, api_client):
        user = UserFactory(username="v_user", password_hash="valid_pass")

        # Act
        response = api_client.post(
            "/api/v1/accounts/auth/login/", data={"username": "v_user", "password": "invalid_pass"}, format="json"
        )

        # Assert
        assert response.status_code == 400
        assert response.json()["error"] == "Mật khẩu không chính xác"

    def test_login_endpoint_not_found(self, api_client):
        # Act
        response = api_client.post(
            "/api/v1/accounts/auth/login/", data={"username": "no_user", "password": "123"}, format="json"
        )

        # Assert
        assert response.status_code == 404
        assert response.json()["error"] == "Tên đăng nhập hoặc email không tồn tại"
