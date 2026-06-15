from django.db import migrations


def rename_payroll_approve(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code="hrm.payroll_approve").update(
        code="finance.payroll_approve", name="Phê duyệt phiếu lương (Finance)"
    )


def reverse_rename_payroll_approve(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code="finance.payroll_approve").update(
        code="hrm.payroll_approve", name="Phê duyệt phiếu lương"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0018_add_fixed_asset_approval_permissions"),
    ]

    operations = [
        migrations.RunPython(rename_payroll_approve, reverse_rename_payroll_approve),
    ]
