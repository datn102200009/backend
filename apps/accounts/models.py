from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.models import BaseModel


class Role(BaseModel):
    """
    Role model for managing user roles and permissions.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "role"
        verbose_name = "Role"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.name


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


class RolePermission(BaseModel):
    """
    Junction table for Role and Permission relationship.
    """

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="roles")

    class Meta:
        db_table = "role_permission"
        unique_together = ("role", "permission")
        verbose_name = "Role Permission"
        verbose_name_plural = "Role Permissions"

    def __str__(self):
        return f"{self.role.name} - {self.permission.code}"


class User(BaseModel):
    """
    Custom user model for authentication and authorization.
    """

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    employee_id = models.CharField(max_length=50, null=True, blank=True, unique=True)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.username


class SystemLog(BaseModel):
    """
    Audit log for tracking system changes.
    """

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs")
    action = models.CharField(max_length=50)
    table_name = models.CharField(max_length=100)
    record_id = models.CharField(max_length=255)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "system_log"
        verbose_name = "System Log"
        verbose_name_plural = "System Logs"
        indexes = [models.Index(fields=["table_name", "record_id"])]

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
