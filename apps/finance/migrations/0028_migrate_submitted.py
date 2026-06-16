from django.db import migrations


def migrate_submitted_to_pending(apps, schema_editor):
    SalarySlip = apps.get_model("finance", "SalarySlip")
    SalarySlip.objects.filter(status="submitted").update(status="pending_finance_review")


def rollback_pending_to_submitted(apps, schema_editor):
    SalarySlip = apps.get_model("finance", "SalarySlip")
    SalarySlip.objects.filter(status="pending_finance_review").update(status="submitted")


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0027_alter_salaryslip_status"),
    ]

    operations = [
        migrations.RunPython(migrate_submitted_to_pending, reverse_code=rollback_pending_to_submitted),
    ]
