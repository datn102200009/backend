from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.settings import api_settings

from apps.accounts.models import User


class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that authenticates against apps.accounts.models.User
    instead of the global Django AUTH_USER_MODEL.
    """

    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        """
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise AuthenticationFailed(
                _("Token contained no recognizable user identification"),
                code="token_not_valid",
            )

        try:
            user = User.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except User.DoesNotExist:
            raise AuthenticationFailed(
                _("User not found"),
                code="user_not_found",
            )

        if not user.is_active:
            raise AuthenticationFailed(
                _("User is inactive"),
                code="user_inactive",
            )

        return user
