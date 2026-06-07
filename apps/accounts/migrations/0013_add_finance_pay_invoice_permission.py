from django.db import migrations


def add_finance_pay_invoice_permission_to_admin(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    # 1. Thêm permission mới finance.pay_invoice
    new_perm, _ = Permission.objects.get_or_create(
        code="finance.pay_invoice",
        defaults={"name": "Thanh toán hóa đơn mua hàng"},
    )
    RolePermission.objects.get_or_create(role=admin_role, permission=new_perm)

    # 2. Xóa permission cũ purchasing.pay_invoice (cascade tự động xóa RolePermission liên quan)
    Permission.objects.filter(code="purchasing.pay_invoice").delete()


def rollback_permissions(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    # 1. Khôi phục permission cũ purchasing.pay_invoice
    old_perm, _ = Permission.objects.get_or_create(
        code="purchasing.pay_invoice",
        defaults={"name": "Thanh toán hóa đơn mua hàng"},
    )
    RolePermission.objects.get_or_create(role=admin_role, permission=old_perm)

    # 2. Xóa permission mới finance.pay_invoice
    Permission.objects.filter(code="finance.pay_invoice").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0012_alter_systemlog_record_id_alter_user_role"),
    ]

    operations = [
        migrations.RunPython(add_finance_pay_invoice_permission_to_admin, rollback_permissions),
    ]
