from django.db import migrations


def rename_payroll_approve(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    old_perm = Permission.objects.filter(code="hrm.payroll_approve").first()
    if old_perm:
        old_perm.code = "finance.payroll_approve"
        old_perm.name = "Phê duyệt phiếu lương (Finance)"
        old_perm.save(update_fields=["code", "name"])
    else:
        Permission.objects.get_or_create(
            code="finance.payroll_approve",
            defaults={"name": "Phê duyệt phiếu lương (Finance)"},
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
