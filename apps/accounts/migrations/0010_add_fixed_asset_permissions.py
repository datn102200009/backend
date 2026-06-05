from django.db import migrations


def add_fixed_asset_permissions_to_admin(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    permissions_to_add = [
        {"code": "finance.create_fixed_asset", "name": "Thêm mới tài sản cố định"},
        {"code": "finance.view_fixed_asset", "name": "Xem tài sản cố định"},
        {"code": "finance.update_fixed_asset", "name": "Cập nhật tài sản cố định"},
        {"code": "finance.delete_fixed_asset", "name": "Xóa tài sản cố định"},
        {"code": "finance.run_depreciation", "name": "Thực hiện trích khấu hao tài sản cố định"},
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
            "finance.create_fixed_asset",
            "finance.view_fixed_asset",
            "finance.update_fixed_asset",
            "finance.delete_fixed_asset",
            "finance.run_depreciation",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_add_qc_certify_permission"),
    ]

    operations = [
        migrations.RunPython(add_fixed_asset_permissions_to_admin, remove_permissions),
    ]
