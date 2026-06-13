from django.db import migrations


def remove_qc_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    # Get the permissions to delete
    perms = Permission.objects.filter(code__in=["purchasing.manage_qc"])

    # Delete RolePermission entries first to be safe
    RolePermission.objects.filter(permission__in=perms).delete()

    # Delete the permissions themselves
    perms.delete()


def rollback(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if admin_role:
        perm, _ = Permission.objects.get_or_create(
            code="purchasing.manage_qc",
            defaults={"name": "Quản lý và thực hiện kiểm định chất lượng QA/QC"},
        )
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0014_add_missing_permissions_to_admin"),
    ]

    operations = [
        migrations.RunPython(remove_qc_permissions, rollback),
    ]
