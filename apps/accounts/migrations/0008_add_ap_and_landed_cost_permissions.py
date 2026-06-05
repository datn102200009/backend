from django.db import migrations


def add_ap_and_landed_cost_permissions_to_admin(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()
    if not admin_role:
        return

    permissions_to_add = [
        {"code": "purchasing.allocate_landed_cost", "name": "Ghi nhận chi phí cập bến và quản lý lô hàng"},
        {"code": "purchasing.pay_invoice", "name": "Thanh toán hóa đơn mua hàng"},
        {"code": "purchasing.view_ap_aging", "name": "Xem báo cáo tuổi nợ nhà cung cấp"},
        {"code": "purchasing.verify_matching", "name": "Thực hiện/Xác minh khớp đối 4 bên"},
    ]

    for perm_data in permissions_to_add:
        perm, _ = Permission.objects.get_or_create(
            code=perm_data["code"],
            defaults={"name": perm_data["name"]},
        )
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)


def remove_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(
        code__in=[
            "purchasing.allocate_landed_cost",
            "purchasing.pay_invoice",
            "purchasing.view_ap_aging",
            "purchasing.verify_matching",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_add_cancel_order_permissions"),
    ]

    operations = [
        migrations.RunPython(add_ap_and_landed_cost_permissions_to_admin, remove_permissions),
    ]
