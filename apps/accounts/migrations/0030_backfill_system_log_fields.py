from django.db import migrations
import re


def backfill_fields(apps, schema_editor):
    SystemLog = apps.get_model("accounts", "SystemLog")
    User = apps.get_model("accounts", "User")
    Employee = apps.get_model("master_data", "Employee")

    model_map = {
        "sales_order": ("sales", "SalesOrder"),
        "purchase_order": ("purchasing", "PurchaseOrder"),
        "stock_entry": ("inventory", "StockEntry"),
        "employee": ("master_data", "Employee"),
        "user": ("accounts", "User"),
        "salary_slip": ("finance", "SalarySlip"),
        "shipment": ("purchasing", "Shipment"),
        "customer": ("crm", "Customer"),
        "supplier": ("procurement", "Supplier"),
        "bom": ("master_data", "BOM"),
        "work_order": ("master_data", "WorkOrder"),
        "fixed_asset": ("finance", "FixedAsset"),
        "leave_request": ("hrm", "LeaveRequest"),
        "employee_document": ("hrm", "EmployeeDocument"),
        "employment_contract": ("hrm", "EmploymentContract"),
        "attendance": ("hrm", "Attendance"),
        "reward_record": ("hrm", "RewardRecord"),
        "discipline_record": ("hrm", "DisciplineRecord"),
        "public_holiday": ("hrm", "PublicHoliday"),
    }

    # Process logs in batches to be memory efficient
    logs = SystemLog.objects.all().select_related("user")

    uuid_pattern = re.compile(r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$")

    for obj in logs:
        # 1. Backfill user_repr
        user_repr = "Hệ thống"
        if obj.user:
            user = obj.user
            if user.employee_id:
                emp = Employee.objects.filter(employee_id=user.employee_id).first()
                if emp:
                    user_repr = emp.full_name
                else:
                    user_repr = user.username
            else:
                user_repr = user.username
        obj.user_repr = user_repr

        # 2. Backfill record_code
        record_code = None
        if obj.record_id and obj.table_name in model_map:
            try:
                app_label, model_name = model_map[obj.table_name]
                model = apps.get_model(app_label, model_name)
                record = model.objects.filter(id=obj.record_id).first()
                if record:
                    # Resolve code fields
                    for attr in [
                        "order_code",
                        "voucher_code",
                        "shipment_num",
                        "contract_no",
                        "asset_code",
                        "employee_id",
                        "customer_name",
                        "supplier_name",
                        "username",
                        "code",
                        "name",
                        "title",
                    ]:
                        if hasattr(record, attr):
                            val = getattr(record, attr)
                            if val:
                                record_code = str(val)
                                break

                    # Special composite case for attendance
                    if not record_code and hasattr(record, "employee") and record.employee:
                        if hasattr(record, "date"):
                            record_code = f"{record.employee.full_name} ({record.date})"
                        elif hasattr(record, "start_date"):
                            record_code = f"{record.employee.full_name} ({record.start_date})"
                        else:
                            record_code = record.employee.full_name
            except Exception:
                pass

        if not record_code:
            record_code = obj.record_id

        if record_code and uuid_pattern.match(str(record_code)):
            obj.record_code = str(record_code)[:8].upper()
        else:
            obj.record_code = record_code

        obj.save(update_fields=["user_repr", "record_code"])


def reverse_backfill(apps, schema_editor):
    SystemLog = apps.get_model("accounts", "SystemLog")
    SystemLog.objects.all().update(user_repr=None, record_code=None)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0029_systemlog_record_code_systemlog_user_repr"),
        ("master_data", "0001_initial"),  # Ensure master_data app is loaded first
    ]

    operations = [
        migrations.RunPython(backfill_fields, reverse_backfill),
    ]
