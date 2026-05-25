from django.db import migrations


def add_holiday_permissions_to_admin(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    permissions_to_add = [
        {"code": "hrm.view_publicholiday", "name": "Xem Ngày Nghỉ Lễ"},
        {"code": "hrm.add_publicholiday", "name": "Thêm Ngày Nghỉ Lễ"},
        {"code": "hrm.change_publicholiday", "name": "Sửa Ngày Nghỉ Lễ"},
        {"code": "hrm.delete_publicholiday", "name": "Xóa Ngày Nghỉ Lễ"},
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
            "hrm.view_publicholiday",
            "hrm.add_publicholiday",
            "hrm.change_publicholiday",
            "hrm.delete_publicholiday",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_add_view_reward_discipline_permissions"),
    ]

    operations = [
        migrations.RunPython(add_holiday_permissions_to_admin, remove_permissions),
    ]
