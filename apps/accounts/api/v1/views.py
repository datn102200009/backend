from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.v1.serializers import AuthLoginInputSerializer, AuthTokenOutputSerializer, RoleSerializer
from apps.accounts.selectors import role_list
from apps.accounts.services import auth_login
from apps.common.xlib.exceptions import NotFoundException, ValidationException


@api_view(["POST"])
@permission_classes([AllowAny])
def auth_login_view(request):
    """
    API Đăng nhập và lấy Bearer Token (JWT).

    POST /api/v1/accounts/auth/login/
    {
        "username": "admin",
        "password": "password123"
    }
    """
    serializer = AuthLoginInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = auth_login(
        username=serializer.validated_data["username"],
        password=serializer.validated_data["password"],
    )

    return Response(
        AuthTokenOutputSerializer(result).data,
        status=status.HTTP_200_OK,
    )


class RoleListAPIView(APIView):
    """
    API Lấy danh sách các vai trò (roles) trong hệ thống.

    GET /api/v1/accounts/roles/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        roles = role_list()
        serializer = RoleSerializer(roles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def auth_me_view(request):
    """
    API Lấy thông tin user hiện tại và danh sách quyền hạn.

    GET /api/v1/accounts/auth/me/
    """
    user = request.user

    direct_perms = set(user.direct_permissions.values_list("permission__code", flat=True))
    permissions = list(direct_perms)

    return Response(
        {
            "id": str(user.id),
            "username": user.username,
            "employee_id": user.employee_id,
            "permissions": permissions,
        },
        status=status.HTTP_200_OK,
    )


class UserListCreateAPIView(APIView):
    """
    API Danh sách người dùng và Tạo tài khoản mới.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from apps.common.xlib.permissions import PermissionChecker

        PermissionChecker.check_permission(request.user, "accounts.view_user")

        search = request.query_params.get("search")
        try:
            limit = int(request.query_params.get("limit", 20))
            offset = int(request.query_params.get("offset", 0))
            limit = min(limit, 100)
        except ValueError:
            limit = 20
            offset = 0

        from apps.accounts.api.v1.serializers import UserOutputSerializer
        from apps.accounts.selectors import user_list
        from apps.master_data.models import Employee

        qs = user_list(search=search)
        count = qs.count()
        results = qs[offset : offset + limit]

        # Cache employee names to avoid N+1 query
        employee_map = {e.employee_id: e.full_name for e in Employee.objects.filter(employment_status="active")}

        serializer = UserOutputSerializer(results, many=True, context={"employee_map": employee_map})
        return Response(
            {
                "count": count,
                "next": None,
                "previous": None,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        from apps.common.xlib.permissions import PermissionChecker

        PermissionChecker.check_permission(request.user, "accounts.add_user")

        from apps.accounts.api.v1.serializers import UserCreateInputSerializer

        serializer = UserCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.accounts.services import user_create

        user = user_create(
            employee_id=data["employee_id"],
            username=data["username"],
            password=data["password"],
            direct_permissions=data.get("direct_permissions", []),
            creator=request.user,
        )

        return Response(
            {
                "id": str(user.id),
                "username": user.username,
                "employee_id": user.employee_id,
            },
            status=status.HTTP_201_CREATED,
        )


class UserDetailUpdateDeleteAPIView(APIView):
    """
    API Cập nhật và Xóa tài khoản người dùng.
    """

    permission_classes = [IsAuthenticated]

    def put(self, request, pk, *args, **kwargs):
        from apps.common.xlib.permissions import PermissionChecker

        PermissionChecker.check_permission(request.user, "accounts.change_user")

        from apps.accounts.api.v1.serializers import UserUpdateInputSerializer

        serializer = UserUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.accounts.services import user_update

        user = user_update(
            user_id=pk,
            direct_permissions=data.get("direct_permissions", []),
            updater=request.user,
        )

        return Response(
            {
                "id": str(user.id),
                "username": user.username,
                "direct_permissions": list(user.direct_permissions.values_list("permission__code", flat=True)),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk, *args, **kwargs):
        from apps.common.xlib.permissions import PermissionChecker

        PermissionChecker.check_permission(request.user, "accounts.delete_user")

        from apps.accounts.services import user_delete

        user_delete(user_id=pk, deleter=request.user)

        return Response(status=status.HTTP_204_NO_CONTENT)


class UserChangePasswordAPIView(APIView):
    """
    API Đổi mật khẩu tài khoản người dùng.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        from apps.common.xlib.permissions import PermissionChecker

        PermissionChecker.check_permission(request.user, "accounts.change_user")

        from apps.accounts.api.v1.serializers import UserChangePasswordInputSerializer

        serializer = UserChangePasswordInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.accounts.services import user_change_password

        user_change_password(
            user_id=pk,
            password=data["password"],
            updater=request.user,
        )

        return Response({"message": "Đổi mật khẩu thành công."}, status=status.HTTP_200_OK)


class UserUnlinkedEmployeesAPIView(APIView):
    """
    API Danh sách nhân viên chưa liên kết tài khoản User.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from apps.common.xlib.permissions import PermissionChecker

        PermissionChecker.check_permission(request.user, "accounts.add_user")

        from apps.accounts.api.v1.serializers import EmployeeUnlinkedOutputSerializer
        from apps.accounts.selectors import unlinked_employees_list

        employees = unlinked_employees_list()
        serializer = EmployeeUnlinkedOutputSerializer(employees, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PermissionListAPIView(APIView):
    """
    API Danh sách tất cả quyền hạn trong hệ thống.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from apps.common.xlib.permissions import PermissionChecker

        PermissionChecker.check_permission(request.user, "accounts.view_user")

        from apps.accounts.api.v1.serializers import PermissionOutputSerializer
        from apps.accounts.models import Permission

        perms = Permission.objects.all().order_by("code")
        serializer = PermissionOutputSerializer(perms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
