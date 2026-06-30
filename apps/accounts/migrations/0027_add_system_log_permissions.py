from django.db import migrations


def add_system_log_permissions(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Permission = apps.get_model("accounts", "Permission")
    UserPermission = apps.get_model("accounts", "UserPermission")

    # Define system log and other view_log permissions
    new_perms = [
        {"code": "accounts.view_system_log", "name": "Xem nhật ký hệ thống"},
        {"code": "inventory.view_log", "name": "Xem nhật ký kho"},
        {"code": "manufacturing.view_log", "name": "Xem nhật ký sản xuất"},
        {"code": "finance.view_log", "name": "Xem nhật ký tài chính"},
        {"code": "sales.view_log", "name": "Xem nhật ký bán hàng"},
        {"code": "purchasing.view_log", "name": "Xem nhật ký mua hàng"},
        {"code": "hrm.view_log", "name": "Xem nhật ký nhân sự"},
    ]

    admin_user = User.objects.filter(username="admin").first()

    for perm_data in new_perms:
        perm, created = Permission.objects.get_or_create(
            code=perm_data["code"],
            defaults={"name": perm_data["name"]},
        )
        if not created and perm.name != perm_data["name"]:
            perm.name = perm_data["name"]
            perm.save()

        # Automatically assign to admin
        if admin_user:
            UserPermission.objects.get_or_create(
                user=admin_user,
                permission=perm,
            )


def remove_system_log_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    codes = [
        "accounts.view_system_log",
        "inventory.view_log",
        "manufacturing.view_log",
        "finance.view_log",
        "sales.view_log",
        "purchasing.view_log",
        "hrm.view_log",
    ]
    Permission.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0026_remove_rolepermission_role_and_more"),
    ]

    operations = [
        migrations.RunPython(add_system_log_permissions, remove_system_log_permissions),
    ]
