import pytest
from django.contrib.auth.hashers import check_password
from rest_framework import status

from apps.accounts.models import Permission, User, UserPermission
from apps.common.xlib.exceptions import PermissionException
from apps.common.xlib.permissions import PermissionChecker
from apps.inventory.tests.factories import UserFactory
from apps.master_data.models import Employee


@pytest.fixture
def test_employee():
    return Employee.objects.create(
        employee_id="NV9990",
        full_name="Nguyễn Văn Quản Lý",
        email="quanly@xuanhoa.vn",
        employment_status="active",
    )


@pytest.fixture
def admin_user():
    user = UserFactory(username="superadmin", is_active=True)
    # Grant accounts.view_user, accounts.add_user, accounts.change_user, accounts.delete_user directly
    for code in ["accounts.view_user", "accounts.add_user", "accounts.change_user", "accounts.delete_user"]:
        perm, _ = Permission.objects.get_or_create(code=code, defaults={"name": code})
        UserPermission.objects.get_or_create(user=user, permission=perm)

    return user


@pytest.fixture
def authorized_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.mark.django_db
class TestUserManagementAPI:

    def test_permission_checker_with_direct_permissions(self):
        # Arrange
        user = UserFactory(username="staff_user", is_active=True)
        perm, _ = Permission.objects.get_or_create(code="sales.create_order", defaults={"name": "Sales Create"})

        # Initially user should fail permission check
        with pytest.raises(PermissionException):
            PermissionChecker.check_permission(user, "sales.create_order")

        # Assign directly
        UserPermission.objects.create(user=user, permission=perm)
        if hasattr(user, "_perm_cache"):
            delattr(user, "_perm_cache")

        # Now it should pass
        PermissionChecker.check_permission(user, "sales.create_order")
        assert PermissionChecker.has_permission(user, "sales.create_order") is True

    def test_list_users(self, authorized_client):
        # Arrange
        UserFactory(username="emp_user_1", employee_id="NV001")
        UserFactory(username="emp_user_2", employee_id="NV002")

        # Act
        response = authorized_client.get("/api/v1/accounts/users/")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] >= 3  # emp_user_1, emp_user_2, and admin_user

    def test_list_unlinked_employees(self, authorized_client, test_employee):
        # Arrange
        # test_employee is active and has no linked user

        # Act
        response = authorized_client.get("/api/v1/accounts/users/unlinked-employees/")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        employee_ids = [e["employee_id"] for e in data]
        assert "NV9990" in employee_ids

    def test_create_user_success(self, authorized_client, test_employee):
        # Arrange
        perm, _ = Permission.objects.get_or_create(code="inventory.stock_in", defaults={"name": "Nhập Kho"})
        data = {
            "employee_id": test_employee.employee_id,
            "username": "manager1",
            "password": "Password123!",
            "direct_permissions": ["inventory.stock_in"],
        }

        # Act
        response = authorized_client.post("/api/v1/accounts/users/", data=data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["username"] == "manager1"

        # Verify DB
        user = User.objects.get(username="manager1")
        assert user.employee_id == test_employee.employee_id
        assert check_password("Password123!", user.password_hash)
        assert UserPermission.objects.filter(user=user, permission=perm).exists()

    def test_create_user_duplicate_username(self, authorized_client, test_employee):
        # Arrange
        UserFactory(username="manager1")
        data = {
            "employee_id": test_employee.employee_id,
            "username": "manager1",
            "password": "Password123!",
        }

        # Act
        response = authorized_client.post("/api/v1/accounts/users/", data=data, format="json")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Tên đăng nhập" in response.json()["error"]

    def test_update_user(self, authorized_client):
        # Arrange
        user = UserFactory(username="user_to_update")
        perm1, _ = Permission.objects.get_or_create(code="sales.create_order", defaults={"name": "Sales"})
        perm2, _ = Permission.objects.get_or_create(code="inventory.stock_in", defaults={"name": "Stock"})

        UserPermission.objects.create(user=user, permission=perm1)

        data = {
            "direct_permissions": ["inventory.stock_in"],
        }

        # Act
        response = authorized_client.put(f"/api/v1/accounts/users/{user.id}/", data=data, format="json")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert not UserPermission.objects.filter(user=user, permission=perm1).exists()
        assert UserPermission.objects.filter(user=user, permission=perm2).exists()

    def test_change_password(self, authorized_client):
        # Arrange
        user = UserFactory(username="user_change_pass")
        data = {"password": "NewStrongPassword123!"}

        # Act
        response = authorized_client.post(
            f"/api/v1/accounts/users/{user.id}/change-password/", data=data, format="json"
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert check_password("NewStrongPassword123!", user.password_hash)

    def test_delete_user(self, authorized_client):
        # Arrange
        user = UserFactory(username="user_to_delete")

        # Act
        response = authorized_client.delete(f"/api/v1/accounts/users/{user.id}/")

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not User.objects.filter(id=user.id).exists()

    def test_permission_list(self, authorized_client):
        # Arrange
        Permission.objects.get_or_create(code="test.dummy_perm", defaults={"name": "Dummy"})

        # Act
        response = authorized_client.get("/api/v1/accounts/permissions/")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        codes = [p["code"] for p in response.json()]
        assert "test.dummy_perm" in codes
