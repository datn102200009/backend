from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("hrm", "0021_unique_active_employment_contract"),
    ]

    operations = [
        migrations.DeleteModel(
            name="EmploymentHistory",
        ),
    ]
