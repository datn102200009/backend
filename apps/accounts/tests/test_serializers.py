import pytest

from apps.accounts.api.v1.serializers import AuthTokenOutputSerializer


class TestAuthTokenOutputSerializer:

    def test_serialize_token_output_with_full_name(self):
        # Arrange
        data = {
            "access": "access-token-123",
            "refresh": "refresh-token-456",
            "user_id": "some-uuid-string",
            "username": "test_user",
            "full_name": "Test Full Name",
            "permissions": ["inventory.stock_in_approve", "accounts.view_users"],
        }

        # Act
        serializer = AuthTokenOutputSerializer(data=data)
        is_valid = serializer.is_valid()

        # Assert
        assert is_valid is True
        serialized_data = serializer.data
        assert serialized_data["full_name"] == "Test Full Name"
        assert serialized_data["access"] == "access-token-123"
        assert serialized_data["username"] == "test_user"

    def test_serialize_token_output_empty_full_name(self):
        # Arrange
        data = {
            "access": "access-token-123",
            "refresh": "refresh-token-456",
            "user_id": "some-uuid-string",
            "username": "test_user",
            "full_name": "",
            "permissions": [],
        }

        # Act
        serializer = AuthTokenOutputSerializer(data=data)
        is_valid = serializer.is_valid()

        # Assert
        assert is_valid is True
        assert serializer.data["full_name"] == ""
