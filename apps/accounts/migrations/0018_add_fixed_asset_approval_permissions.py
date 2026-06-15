from django.db import migrations


def add_approval_permissions_to_admin(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    permissions_to_add = [
        {
            "code": "finance.approve_fixed_asset_purchase",
            "name": "Phê duyệt mua tài sản cố định",
        },
        {
            "code": "finance.approve_fixed_asset_dispose",
            "name": "Phê duyệt thanh lý tài sản cố định",
        },
    ]

    for perm_data in permissions_to_add:
        perm, _ = Permission.objects.get_or_create(
            code=perm_data["code"],
            defaults={"name": perm_data["name"]},
        )
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)


def remove_approval_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(
        code__in=[
            "finance.approve_fixed_asset_purchase",
            "finance.approve_fixed_asset_dispose",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0017_rename_collect_invoice_to_collect_sales_invoice"),
    ]

    operations = [
        migrations.RunPython(add_approval_permissions_to_admin, remove_approval_permissions),
    ]
