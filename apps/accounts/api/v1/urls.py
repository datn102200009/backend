from django.urls import path

from apps.accounts.api.v1.views import (
    PermissionListAPIView,
    RoleListAPIView,
    UserChangePasswordAPIView,
    UserDetailUpdateDeleteAPIView,
    UserListCreateAPIView,
    UserUnlinkedEmployeesAPIView,
    auth_login_view,
    auth_me_view,
)

app_name = "accounts_api_v1"

urlpatterns = [
    path("auth/login/", auth_login_view, name="auth-login"),
    path("auth/me/", auth_me_view, name="auth-me"),
    path("roles/", RoleListAPIView.as_view(), name="role-list"),
    path("users/", UserListCreateAPIView.as_view(), name="user-list-create"),
    path("users/unlinked-employees/", UserUnlinkedEmployeesAPIView.as_view(), name="user-unlinked-employees"),
    path("users/<uuid:pk>/", UserDetailUpdateDeleteAPIView.as_view(), name="user-detail-update-delete"),
    path("users/<uuid:pk>/change-password/", UserChangePasswordAPIView.as_view(), name="user-change-password"),
    path("permissions/", PermissionListAPIView.as_view(), name="permission-list"),
]
