from django.db import migrations


def add_new_permissions_to_admin(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    permissions_to_add = [
        {"code": "manufacturing.work_order_cancel", "name": "Hủy Lệnh Sản Xuất"},
        {"code": "hrm.payroll_approve", "name": "Phê duyệt phiếu lương"},
    ]

    for perm_data in permissions_to_add:
        perm, _ = Permission.objects.get_or_create(
            code=perm_data["code"],
            defaults={"name": perm_data["name"]},
        )
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)


def remove_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(
        code__in=[
            "manufacturing.work_order_cancel",
            "hrm.payroll_approve",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_add_fixed_asset_permissions"),
    ]

    operations = [
        migrations.RunPython(add_new_permissions_to_admin, remove_permissions),
    ]
