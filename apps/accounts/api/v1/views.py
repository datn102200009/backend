from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.api.v1.serializers import AuthLoginInputSerializer, AuthTokenOutputSerializer
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
    try:
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

    except ValidationException as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except NotFoundException as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Lỗi server: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
