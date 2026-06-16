from django.db import migrations


def add_hrm_payroll_submit_permission(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    hr_role = Role.objects.filter(name="HR Manager").first()

    perm, _ = Permission.objects.get_or_create(
        code="hrm.payroll_submit",
        defaults={"name": "Gửi Finance Duyệt phiếu lương"},
    )

    if admin_role:
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)
    if hr_role:
        RolePermission.objects.get_or_create(role=hr_role, permission=perm)


def remove_hrm_payroll_submit_permission(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code="hrm.payroll_submit").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0019_rename_payroll_approve"),
    ]

    operations = [
        migrations.RunPython(add_hrm_payroll_submit_permission, remove_hrm_payroll_submit_permission),
    ]
