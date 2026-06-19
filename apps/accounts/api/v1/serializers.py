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
    full_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    permissions = serializers.ListField(child=serializers.CharField())


class RoleSerializer(serializers.ModelSerializer):
    """Serializer định dạng thông tin vai trò."""

    class Meta:
        model = Role
        fields = ["id", "name", "description"]


class UserOutputSerializer(serializers.Serializer):
    """Serializer định dạng kết quả tài khoản người dùng."""

    id = serializers.UUIDField()
    username = serializers.CharField()
    employee_id = serializers.CharField()
    employee_name = serializers.SerializerMethodField()
    direct_permissions = serializers.SerializerMethodField()
    all_permissions = serializers.SerializerMethodField()
    is_active = serializers.BooleanField()
    last_login = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()

    def get_employee_name(self, obj):
        employee_map = self.context.get("employee_map")
        if employee_map and obj.employee_id:
            return employee_map.get(obj.employee_id, "")
        if obj.employee_id:
            from apps.master_data.models import Employee

            emp = Employee.objects.filter(employee_id=obj.employee_id).first()
            return emp.full_name if emp else ""
        return ""

    def get_direct_permissions(self, obj):
        return list(obj.direct_permissions.values_list("permission__code", flat=True))

    def get_all_permissions(self, obj):
        return list(obj.direct_permissions.values_list("permission__code", flat=True))


class UserCreateInputSerializer(serializers.Serializer):
    """Serializer validate đầu vào khi tạo tài khoản người dùng."""

    employee_id = serializers.CharField(max_length=50, required=True)
    username = serializers.CharField(max_length=150, required=True)
    password = serializers.CharField(max_length=128, required=True)
    direct_permissions = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class UserUpdateInputSerializer(serializers.Serializer):
    """Serializer validate đầu vào khi cập nhật tài khoản người dùng."""

    direct_permissions = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class UserChangePasswordInputSerializer(serializers.Serializer):
    """Serializer validate đầu vào khi đổi mật khẩu."""

    password = serializers.CharField(max_length=128, required=True)


class PermissionOutputSerializer(serializers.Serializer):
    """Serializer định dạng thông tin quyền hạn."""

    code = serializers.CharField()
    name = serializers.CharField()


class EmployeeUnlinkedOutputSerializer(serializers.Serializer):
    """Serializer định dạng thông tin nhân viên chưa có tài khoản."""

    employee_id = serializers.CharField()
    full_name = serializers.CharField()
    email = serializers.EmailField(allow_blank=True, allow_null=True)
