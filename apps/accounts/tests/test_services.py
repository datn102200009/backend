import pytest
from django.contrib.auth.hashers import make_password

from apps.accounts.services import auth_login
from apps.common.xlib.exceptions import NotFoundException, ValidationException
from apps.inventory.tests.factories import UserFactory


@pytest.mark.django_db
class TestAuthLoginService:

    def test_login_success_with_hashed_password(self):
        # Arrange
        hashed = make_password("securepassword")
        user = UserFactory(username="john_doe", password_hash=hashed, email="john@example.com")

        # Act
        result = auth_login(username="john_doe", password="securepassword")

        # Assert
        assert "access" in result
        assert "refresh" in result
        assert result["username"] == "john_doe"
        assert result["user_id"] == str(user.id)

    def test_login_success_with_email(self):
        # Arrange
        user = UserFactory(username="jane_doe", password_hash="plainpass", email="jane@example.com")

        # Act
        result = auth_login(username="jane@example.com", password="plainpass")

        # Assert
        assert "access" in result
        assert result["username"] == "jane_doe"

    def test_login_fails_wrong_password(self):
        user = UserFactory(username="admin_user", password_hash="secret")

        with pytest.raises(ValidationException) as exc:
            auth_login(username="admin_user", password="wrong_password")

        assert "Mật khẩu không chính xác" in str(exc.value)

    def test_login_fails_user_not_found(self):
        with pytest.raises(NotFoundException) as exc:
            auth_login(username="ghost_user", password="123")

        assert "Tên đăng nhập hoặc email không tồn tại" in str(exc.value)

    def test_login_fails_inactive_user(self):
        user = UserFactory(username="inactive_user", password_hash="secret", is_active=False)

        with pytest.raises(ValidationException) as exc:
            auth_login(username="inactive_user", password="secret")

        assert "Tài khoản đã bị vô hiệu hóa" in str(exc.value)
