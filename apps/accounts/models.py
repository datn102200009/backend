from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.models import BaseModel


class Permission(BaseModel):
    """
    Permission model for defining what actions users can perform.
    """

    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)

    class Meta:
        db_table = "permission"
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"

    def __str__(self):
        return f"{self.code} - {self.name}"


class User(BaseModel):
    """
    Custom user model for authentication and authorization.
    """

    username = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=255)
    employee_id = models.CharField(max_length=50, null=True, blank=True, unique=True)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.username

    @property
    def is_authenticated(self):
        """Return True if user is authenticated (always True for User instances)."""
        return True


class SystemLog(BaseModel):
    """
    Audit log for tracking system changes.
    """

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs")
    user_repr = models.CharField(max_length=255, null=True, blank=True, help_text="Tên người thực hiện lưu tĩnh")
    record_code = models.CharField(max_length=255, null=True, blank=True, help_text="Mã/Tên bản ghi lưu tĩnh")
    action = models.CharField(max_length=50)
    table_name = models.CharField(max_length=100)
    record_id = models.CharField(max_length=255, db_index=True)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    allowed_permissions = models.JSONField(
        default=list, blank=True, help_text="Danh sách permissions được phép xem log này"
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "system_log"
        verbose_name = "System Log"
        verbose_name_plural = "System Logs"
        indexes = [
            models.Index(fields=["table_name", "record_id"]),
            models.Index(fields=["-timestamp"]),
        ]

    def __str__(self):
        return f"{self.action} on {self.table_name} at {self.timestamp}"


class Notification(BaseModel):
    """
    Notification model for user notifications.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "notification"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.user.username}"


class UserPermission(BaseModel):
    """
    Junction table for User and Permission relationship (direct user-level permissions).
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="direct_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="users")

    class Meta:
        db_table = "user_permission"
        unique_together = ("user", "permission")
        verbose_name = "User Permission"
        verbose_name_plural = "User Permissions"

    def __str__(self):
        return f"{self.user.username} - {self.permission.code}"
