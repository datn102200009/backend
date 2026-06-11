from django.db import migrations


def add_missing_permissions_to_admin(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    permissions_to_add = [
        {"code": "finance.approve_cash_flow", "name": "Phê duyệt dòng tiền"},
        {"code": "hrm.change_rewardrecord", "name": "Sửa Khen Thưởng"},
        {"code": "hrm.change_disciplinerecord", "name": "Sửa Kỷ Luật"},
    ]

    for perm_data in permissions_to_add:
        perm, _ = Permission.objects.get_or_create(
            code=perm_data["code"],
            defaults={"name": perm_data["name"]},
        )
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)


def rollback_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(
        code__in=[
            "finance.approve_cash_flow",
            "hrm.change_rewardrecord",
            "hrm.change_disciplinerecord",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_add_finance_pay_invoice_permission"),
    ]

    operations = [
        migrations.RunPython(add_missing_permissions_to_admin, rollback_permissions),
    ]
