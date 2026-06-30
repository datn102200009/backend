import pytest
from rest_framework.test import APIClient

from apps.inventory.tests.factories import UserFactory


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

        # Assert last_login was updated
        user.refresh_from_db()
        assert user.last_login is not None

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


@pytest.mark.django_db
class TestSystemLogAPI:

    def test_system_logs_unauthenticated(self, api_client):
        response = api_client.get("/api/v1/accounts/system-logs/")
        assert response.status_code == 401

    def test_system_logs_success_and_filtering(self, api_client):
        from apps.accounts.models import Permission, SystemLog, UserPermission

        # Create two permissions
        perm_inv_log, _ = Permission.objects.get_or_create(code="inventory.view_log", defaults={"name": "Xem log kho"})
        perm_sales_log, _ = Permission.objects.get_or_create(
            code="sales.view_log", defaults={"name": "Xem log bán hàng"}
        )

        # Create user with ONLY inventory.view_log permission
        user = UserFactory(username="inv_auditor")
        UserPermission.objects.create(user=user, permission=perm_inv_log)

        # Create two logs
        log_inv = SystemLog.objects.create(
            user=user,
            action="inventory.stock_in",
            table_name="stock_entry",
            record_id="rec_inv_1",
            new_value={"msg": "Nhập kho thành công"},
            allowed_permissions=["inventory.view_log", "inventory.stock_in"],
        )
        log_sales = SystemLog.objects.create(
            user=user,
            action="sales.order_create",
            table_name="sales_order",
            record_id="rec_sales_1",
            new_value={"msg": "Tạo đơn hàng thành công"},
            allowed_permissions=["sales.view_log", "sales.order_create"],
        )

        # Authenticate
        api_client.force_authenticate(user=user)

        # Act
        response = api_client.get("/api/v1/accounts/system-logs/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        results = data["results"]
        # Should only see the inventory log, not the sales log!
        assert len(results) == 1
        assert results[0]["id"] == str(log_inv.id)
        assert results[0]["action"] == "inventory.stock_in"
        assert "message" in results[0]
