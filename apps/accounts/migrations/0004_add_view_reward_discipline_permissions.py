from django.db import migrations


def add_view_reward_discipline_permissions_to_admin(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    permissions_to_add = [
        {"code": "hrm.view_rewardrecord", "name": "Xem Khen Thưởng"},
        {"code": "hrm.view_disciplinerecord", "name": "Xem Kỷ Luật"},
    ]

    for perm_data in permissions_to_add:
        perm, _ = Permission.objects.get_or_create(
            code=perm_data["code"],
            defaults={"name": perm_data["name"]},
        )
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)


def remove_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code__in=["hrm.view_rewardrecord", "hrm.view_disciplinerecord"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_add_hrm_permissions_to_admin"),
    ]

    operations = [
        migrations.RunPython(add_view_reward_discipline_permissions_to_admin, remove_permissions),
    ]
