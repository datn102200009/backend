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
