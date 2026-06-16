from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("hrm", "0020_cleanup_duplicate_active_contracts")]
    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX IF NOT EXISTS employment_contract_active_unique "
                "ON employment_contract (employee_id) WHERE status = 'active';"
            ),
            reverse_sql="DROP INDEX IF EXISTS employment_contract_active_unique;",
        ),
    ]
