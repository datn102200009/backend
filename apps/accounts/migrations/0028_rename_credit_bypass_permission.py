from django.db import migrations


def rename_permission(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    User = apps.get_model("accounts", "User")
    UserPermission = apps.get_model("accounts", "UserPermission")

    # Retrieve the existing permission or create it if missing, then rename it
    perm, created = Permission.objects.get_or_create(
        code="sales.approve_credit_bypass", defaults={"name": "Phê duyệt tín dụng đặc cách"}
    )
    perm.code = "finance.approve_credit_bypass"
    perm.name = "Phê duyệt tín dụng đặc cách (Finance)"
    perm.save()

    # Ensure the admin user has this permission assigned
    admin_user = User.objects.filter(username="admin").first()
    if admin_user:
        UserPermission.objects.get_or_create(user=admin_user, permission=perm)


def reverse_rename(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    try:
        perm = Permission.objects.get(code="finance.approve_credit_bypass")
        perm.code = "sales.approve_credit_bypass"
        perm.name = "Phê duyệt tín dụng đặc cách"
        perm.save()
    except Permission.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0027_add_system_log_permissions"),
    ]

    operations = [
        migrations.RunPython(rename_permission, reverse_rename),
    ]
