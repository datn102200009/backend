from django.db import migrations


def rename_permission(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    perm = Permission.objects.filter(code="finance.collect_invoice").first()
    if perm:
        # Since code is UNIQUE, let's modify it directly
        perm.code = "finance.collect_sales_invoice"
        perm.name = "Thu tiền hóa đơn bán hàng"
        perm.save()


def rollback(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    perm = Permission.objects.filter(code="finance.collect_sales_invoice").first()
    if perm:
        perm.code = "finance.collect_invoice"
        perm.name = "Thu tiền hóa đơn bán"
        perm.save()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0016_add_view_shipment_and_refactor_invoice_permissions"),
    ]
    operations = [
        migrations.RunPython(rename_permission, rollback),
    ]
