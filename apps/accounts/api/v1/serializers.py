from rest_framework import serializers

from apps.accounts.models import Role


class AuthLoginInputSerializer(serializers.Serializer):
    """Serializer để validate dữ liệu đầu vào của API Login."""

    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class AuthTokenOutputSerializer(serializers.Serializer):
    """Serializer để định dạng kết quả token trả về."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user_id = serializers.CharField()
    username = serializers.CharField()
    email = serializers.CharField()
    role = serializers.CharField(allow_null=True)
    permissions = serializers.ListField(child=serializers.CharField())


class RoleSerializer(serializers.ModelSerializer):
    """Serializer định dạng thông tin vai trò."""

    class Meta:
        model = Role
        fields = ["id", "name", "description"]
