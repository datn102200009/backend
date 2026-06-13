from django.db import migrations


def refactor_permissions(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()

    # 1. Tạo các permission mới
    new_perms = [
        ("purchasing.view_shipment", "Xem lô hàng"),
        ("finance.view_invoice", "Xem hóa đơn mua/bán"),
        ("finance.collect_invoice", "Thu tiền hóa đơn bán"),
    ]
    created_perms = {}
    for code, name in new_perms:
        perm, _ = Permission.objects.get_or_create(code=code, defaults={"name": name})
        created_perms[code] = perm
        if admin_role:
            RolePermission.objects.get_or_create(role=admin_role, permission=perm)

    # 2. Gán finance.view_invoice cho bất kỳ Role nào đang có sales.view_invoice hoặc purchasing.view_invoice
    view_invoice_perm = created_perms["finance.view_invoice"]
    old_codes = ["sales.view_invoice", "purchasing.view_invoice"]
    old_perms = Permission.objects.filter(code__in=old_codes)
    for old_perm in old_perms:
        # Tìm tất cả các role đang được liên kết với permission cũ này
        role_ids = RolePermission.objects.filter(permission=old_perm).values_list("role_id", flat=True)
        for r_id in role_ids:
            RolePermission.objects.get_or_create(role_id=r_id, permission=view_invoice_perm)

    # 3. Gán finance.view_invoice và finance.collect_invoice cho Finance role (nếu có)
    finance_role = Role.objects.filter(name__icontains="finance").first()
    if finance_role:
        RolePermission.objects.get_or_create(role=finance_role, permission=view_invoice_perm)
        RolePermission.objects.get_or_create(role=finance_role, permission=created_perms["finance.collect_invoice"])

    # 4. Xóa các permission cũ
    old_perms.delete()


def rollback(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    admin_role = Role.objects.filter(name="Admin").first()

    # 1. Khôi phục các permission cũ
    old_perms = [
        ("sales.view_invoice", "Xem hóa đơn bán"),
        ("purchasing.view_invoice", "Xem hóa đơn mua"),
    ]
    for code, name in old_perms:
        perm, _ = Permission.objects.get_or_create(code=code, defaults={"name": name})
        if admin_role:
            RolePermission.objects.get_or_create(role=admin_role, permission=perm)

    # 2. Xóa các permission mới
    new_codes = ["purchasing.view_shipment", "finance.view_invoice", "finance.collect_invoice"]
    Permission.objects.filter(code__in=new_codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_remove_qc_permissions"),
    ]

    operations = [
        migrations.RunPython(refactor_permissions, rollback),
    ]
