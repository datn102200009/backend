from django.db import migrations


def rename_permission(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    User = apps.get_model("accounts", "User")
    UserPermission = apps.get_model("accounts", "UserPermission")

    old_perm = Permission.objects.filter(code="sales.approve_credit_bypass").first()
    new_perm = Permission.objects.filter(code="finance.approve_credit_bypass").first()

    if old_perm and new_perm:
        # Both exist: Move UserPermission relationships from old to new, then delete old
        old_user_perms = UserPermission.objects.filter(permission=old_perm)
        for up in old_user_perms:
            if not UserPermission.objects.filter(user=up.user, permission=new_perm).exists():
                up.permission = new_perm
                up.save()
            else:
                up.delete()  # Avoid duplicates
        old_perm.delete()
        perm = new_perm
    elif old_perm:
        # Only old exists: Rename it
        old_perm.code = "finance.approve_credit_bypass"
        old_perm.name = "Phê duyệt tín dụng đặc cách (Finance)"
        old_perm.save()
        perm = old_perm
    elif new_perm:
        # Only new exists: Use it
        perm = new_perm
    else:
        # Neither exists: Create new
        perm = Permission.objects.create(
            code="finance.approve_credit_bypass", name="Phê duyệt tín dụng đặc cách (Finance)"
        )

    # Ensure the admin user has this permission assigned
    admin_user = User.objects.filter(username="admin").first()
    if admin_user:
        UserPermission.objects.get_or_create(user=admin_user, permission=perm)


def reverse_rename(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    UserPermission = apps.get_model("accounts", "UserPermission")

    old_perm = Permission.objects.filter(code="sales.approve_credit_bypass").first()
    new_perm = Permission.objects.filter(code="finance.approve_credit_bypass").first()

    if old_perm and new_perm:
        # Move UserPermission relationships from new to old, then delete new
        new_user_perms = UserPermission.objects.filter(permission=new_perm)
        for up in new_user_perms:
            if not UserPermission.objects.filter(user=up.user, permission=old_perm).exists():
                up.permission = old_perm
                up.save()
            else:
                up.delete()
        new_perm.delete()
    elif new_perm:
        # Only new exists: Rename to old
        new_perm.code = "sales.approve_credit_bypass"
        new_perm.name = "Phê duyệt tín dụng đặc cách"
        new_perm.save()
    elif old_perm:
        pass
    else:
        # Neither exists: Create old
        Permission.objects.create(code="sales.approve_credit_bypass", name="Phê duyệt tín dụng đặc cách")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0027_add_system_log_permissions"),
    ]

    operations = [
        migrations.RunPython(rename_permission, reverse_rename),
    ]
