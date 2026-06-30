"""
Services for common app.

All write operations (Create, Update, Delete) should be defined here.
Never receive request objects, only primitive types or DTOs.
Always ensure atomic transactions.
"""

from typing import Any, Dict, List, Optional

from django.db import transaction

from apps.accounts.models import SystemLog, User


@transaction.atomic
def create_system_log(
    *,
    user: Optional[User],
    action: str,
    table_name: str,
    record_id: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    allowed_permissions: Optional[List[str]] = None,
) -> SystemLog:
    """
    Tạo một bản ghi nhật ký hệ thống (audit log).

    Args:
        user: User thực hiện hành động
        action: Loại hành động (create, update, delete, approve, etc.)
        table_name: Tên bảng được thay đổi
        record_id: ID của bản ghi được thay đổi
        old_value: Giá trị cũ (cho các hành động update)
        new_value: Giá trị mới (cho các hành động update hoặc create)
        allowed_permissions: Danh sách các permissions được phép xem log này

    Returns:
        SystemLog object

    Ví dụ:
        create_system_log(
            user=user,
            action="create",
            table_name="stock_entry",
            record_id=str(stock_entry.id),
            new_value={"name": "SE-001", "purpose": "receipt"},
            allowed_permissions=["inventory.view_log"]
        )
    """
    # 1. Populate user_repr
    user_repr = "Hệ thống"
    if user:
        user_repr = user.username
        if user.employee_id:
            try:
                from apps.master_data.models import Employee

                emp = Employee.objects.filter(employee_id=user.employee_id).first()
                if emp:
                    user_repr = emp.full_name
            except Exception:
                pass

    # 2. Populate record_code
    record_code = None
    try:
        from django.apps import apps

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
        if table_name in model_map:
            app_label, model_name = model_map[table_name]
            model = apps.get_model(app_label, model_name)
            record = model.objects.filter(id=record_id).first()
            if record:
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
        record_code = record_id

    import re

    uuid_pattern = re.compile(r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$")
    if record_code and uuid_pattern.match(str(record_code)):
        record_code = str(record_code)[:8].upper()

    return SystemLog.objects.create(
        user=user,
        user_repr=user_repr,
        record_code=record_code,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_value=old_value,
        new_value=new_value,
        allowed_permissions=allowed_permissions or [],
    )
