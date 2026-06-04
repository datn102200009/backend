from django.db import migrations


def add_cancel_order_permissions_to_admin(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    permissions_to_add = [
        {"code": "purchasing.cancel_order", "name": "Hủy đơn mua hàng đã duyệt"},
        {"code": "sales.cancel_order", "name": "Hủy đơn bán hàng đã duyệt"},
    ]

    for perm_data in permissions_to_add:
        perm, _ = Permission.objects.get_or_create(
            code=perm_data["code"],
            defaults={"name": perm_data["name"]},
        )
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)


def remove_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code__in=["purchasing.cancel_order", "sales.cancel_order"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_add_credit_bypass_permissions"),
    ]

    operations = [
        migrations.RunPython(add_cancel_order_permissions_to_admin, remove_permissions),
    ]
