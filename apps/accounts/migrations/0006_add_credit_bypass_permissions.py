from django.db import migrations


def add_credit_bypass_permissions_to_admin(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    permissions_to_add = [
        {"code": "sales.approve_credit_bypass", "name": "Phê duyệt tín dụng đặc cách"},
    ]

    for perm_data in permissions_to_add:
        perm, _ = Permission.objects.get_or_create(
            code=perm_data["code"],
            defaults={"name": perm_data["name"]},
        )
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)


def remove_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code__in=["sales.approve_credit_bypass"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_add_holiday_permissions"),
    ]

    operations = [
        migrations.RunPython(add_credit_bypass_permissions_to_admin, remove_permissions),
    ]
