from django.db import migrations


def add_user_management_permissions(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()

    permissions_to_add = [
        {"code": "accounts.view_user", "name": "Xem tài khoản người dùng"},
        {"code": "accounts.add_user", "name": "Thêm tài khoản người dùng"},
        {"code": "accounts.change_user", "name": "Cập nhật tài khoản người dùng"},
        {"code": "accounts.delete_user", "name": "Xóa tài khoản người dùng"},
    ]

    for perm_data in permissions_to_add:
        perm, _ = Permission.objects.get_or_create(
            code=perm_data["code"],
            defaults={"name": perm_data["name"]},
        )
        if admin_role:
            RolePermission.objects.get_or_create(role=admin_role, permission=perm)


def remove_user_management_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(
        code__in=[
            "accounts.view_user",
            "accounts.add_user",
            "accounts.change_user",
            "accounts.delete_user",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0022_userpermission"),
    ]

    operations = [
        migrations.RunPython(add_user_management_permissions, remove_user_management_permissions),
    ]
