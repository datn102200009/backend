from django.urls import path

from apps.accounts.api.v1.views import RoleListAPIView, auth_login_view, auth_me_view

app_name = "accounts_api_v1"

urlpatterns = [
    path("auth/login/", auth_login_view, name="auth-login"),
    path("auth/me/", auth_me_view, name="auth-me"),
    path("roles/", RoleListAPIView.as_view(), name="role-list"),
]
