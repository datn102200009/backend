from django.db import migrations


def add_hrm_adjust_salary_permission(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()

    perm, _ = Permission.objects.get_or_create(
        code="hrm.adjust_salary",
        defaults={"name": "Điều chỉnh lương nhân viên"},
    )

    if admin_role:
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)


def remove_hrm_adjust_salary_permission(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code="hrm.adjust_salary").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0020_add_hrm_payroll_submit"),
    ]

    operations = [
        migrations.RunPython(add_hrm_adjust_salary_permission, remove_hrm_adjust_salary_permission),
    ]
