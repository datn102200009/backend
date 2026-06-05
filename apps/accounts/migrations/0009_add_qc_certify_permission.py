from django.db import migrations


def add_qc_certify_permission_to_admin(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    permissions_to_add = [
        {"code": "purchasing.manage_qc", "name": "Quản lý và thực hiện kiểm định chất lượng QA/QC"},
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
            "purchasing.manage_qc",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_add_ap_and_landed_cost_permissions"),
    ]

    operations = [
        migrations.RunPython(add_qc_certify_permission_to_admin, remove_permissions),
    ]
