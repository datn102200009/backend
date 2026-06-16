from django.db import migrations
from django.db.models import Count


def cleanup_duplicate_active_contracts(apps, schema_editor):
    """Giữ HĐLĐ mới nhất (start_date DESC), các HĐLĐ cũ chuyển expired."""
    EmploymentContract = apps.get_model("hrm", "EmploymentContract")
    duplicates = (
        EmploymentContract.objects.filter(status="active").values("employee_id").annotate(c=Count("id")).filter(c__gt=1)
    )
    for dup in duplicates:
        contracts = list(
            EmploymentContract.objects.filter(employee_id=dup["employee_id"], status="active").order_by("-start_date")
        )
        keep = contracts[0]
        from datetime import timedelta

        for old in contracts[1:]:
            old.status = "expired"
            if keep.start_date and (old.end_date is None or keep.start_date <= old.end_date):
                old.end_date = keep.start_date - timedelta(days=1)
            old.save(update_fields=["status", "end_date"])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("hrm", "0019_employmentcontract_salary_base")]
    operations = [migrations.RunPython(cleanup_duplicate_active_contracts, reverse_noop)]
