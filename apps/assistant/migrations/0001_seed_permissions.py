from django.db import migrations


def seed_chatbot_permission(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    perm, created = Permission.objects.get_or_create(
        code="common.use_chatbot",
        defaults={"name": "Sử dụng Chatbot AI"},
    )

    # Gán quyền cho role Admin và/hoặc admin user theo đúng project rules
    try:
        Role = apps.get_model("accounts", "Role")
        RolePermission = apps.get_model("accounts", "RolePermission")
        admin_role = Role.objects.filter(name="Admin").first()
        if admin_role:
            RolePermission.objects.get_or_create(
                role=admin_role,
                permission=perm,
            )
    except LookupError:
        pass

    User = apps.get_model("accounts", "User")
    UserPermission = apps.get_model("accounts", "UserPermission")
    admin_user = User.objects.filter(username="admin").first()
    if admin_user:
        UserPermission.objects.get_or_create(
            user=admin_user,
            permission=perm,
        )


def remove_chatbot_permission(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code="common.use_chatbot").delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0025_assign_all_permissions_to_admin"),
    ]

    operations = [
        migrations.RunPython(seed_chatbot_permission, remove_chatbot_permission),
    ]
