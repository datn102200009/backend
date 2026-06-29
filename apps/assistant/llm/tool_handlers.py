# flake8: noqa
from decimal import Decimal

from apps.common.xlib.exceptions import NotFoundException, PermissionException, ValidationException
from apps.common.xlib.permissions import PermissionChecker
from apps.crm import selectors as crm_selectors
from apps.finance import selectors as finance_selectors
from apps.hrm.models import LeaveRequest
from apps.inventory import selectors as inv_selectors
from apps.manufacturing import selectors as mfg_selectors
from apps.master_data import selectors as md_selectors
from apps.master_data.models import Employee, Item, Warehouse
from apps.procurement import selectors as proc_selectors
from apps.purchasing import selectors as purchasing_selectors
from apps.sales import selectors as sales_selectors

# ===== master_data =====


def search_items_handler(args, user):
    PermissionChecker.check_permission(user, "master_data.view_item")
    query = args.get("query", "").strip()
    status = args.get("status")

    # Sử dụng md_selectors.item_list thay thế cho các selectors không tồn tại
    qs = md_selectors.item_list(search=query or None, status=status or None)
    return {
        "count": min(qs.count(), 20),
        "items": [_serialize_item(i) for i in qs[:20]],
    }


def get_item_detail_handler(args, user):
    PermissionChecker.check_permission(user, "master_data.view_item")
    code = args.get("item_code", "").strip()
    if not code:
        raise ValidationException("item_code không được trống")
    try:
        item = md_selectors.item_get_detail(item_code=code)
        return _serialize_item(item)
    except Exception:
        return {"error": f"Không tìm thấy sản phẩm '{code}'"}


# ===== inventory =====


def get_inventory_balance_handler(args, user):
    PermissionChecker.check_permission(user, "inventory.view")
    item_code = args.get("item_code", "").strip()
    warehouse_code = args.get("warehouse_code", "").strip() or None
    if not item_code:
        raise ValidationException("item_code không được trống")

    try:
        item = Item.objects.get(item_code=item_code)
    except Item.DoesNotExist:
        return {"error": f"Không tìm thấy sản phẩm '{item_code}'"}

    if warehouse_code:
        try:
            wh = Warehouse.objects.get(name=warehouse_code)
        except Warehouse.DoesNotExist:
            return {"error": f"Không tìm thấy kho '{warehouse_code}'"}
        balance = inv_selectors.stock_ledger_balance_by_item_warehouse(item, wh)
        return {"item_code": item_code, "warehouse": warehouse_code, "balance": str(balance)}
    else:
        qs = inv_selectors.stock_ledger_balance(detailed=True).filter(item_id=item.id)
        rows = []
        for row in qs[:20]:
            rows.append({"warehouse": row["warehouse_name"], "balance": str(row["total_quantity"])})
        return {"item_code": item_code, "warehouses": rows}


def search_warehouses_handler(args, user):
    PermissionChecker.check_permission(user, "inventory.view")
    qs = md_selectors.warehouse_list().filter(is_group=False)[:50]
    return {
        "count": qs.count() if hasattr(qs, "count") else len(list(qs)),
        "warehouses": [{"name": w.name} for w in qs],
    }


def list_stock_entries_handler(args, user):
    PermissionChecker.check_permission(user, "inventory.view")
    status = args.get("status", "submitted")
    purpose = args.get("purpose")
    limit = min(int(args.get("limit", 20)), 50)
    qs = inv_selectors.stock_entry_list_by_status(status, purpose)
    return {
        "count": min(qs.count(), limit),
        "entries": [
            {
                "name": e.name,
                "purpose": e.purpose,
                "posting_date": e.posting_date.isoformat(),
                "status": e.status,
            }
            for e in qs[:limit]
        ],
    }


# ===== hrm =====


def search_employees_handler(args, user):
    PermissionChecker.check_permission(user, "hrm.view_employee")
    query = args.get("query", "").strip()
    limit = min(int(args.get("limit", 10)), 50)
    if not query:
        raise ValidationException("query không được trống")

    qs = Employee.objects.filter(full_name__icontains=query) | Employee.objects.filter(employee_id__icontains=query)
    qs = qs.distinct()[:limit]

    return {
        "count": min(qs.count() if hasattr(qs, "count") else len(list(qs)), limit),
        "employees": [
            {
                "employee_id": e.employee_id,
                "full_name": e.full_name,
                "email": e.email,
                "employment_status": e.employment_status,
            }
            for e in qs
        ],
    }


def list_leave_requests_handler(args, user):
    PermissionChecker.check_permission(user, "hrm.view_leaverequest")
    status = args.get("status")
    employee_code = args.get("employee_code")
    limit = min(int(args.get("limit", 20)), 50)
    qs = LeaveRequest.objects.select_related("employee").all().order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    if employee_code:
        qs = qs.filter(employee__employee_id=employee_code)

    return {
        "count": min(qs.count(), limit),
        "requests": [
            {
                "employee": r.employee.full_name,
                "leave_type": r.leave_type,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
                "days": float(r.days),
                "status": r.status,
            }
            for r in qs[:limit]
        ],
    }


# ===== sales =====


def list_sales_orders_handler(args, user):
    PermissionChecker.check_permission(user, "sales.view_order")
    status = args.get("status")
    customer_id = args.get("customer_id")
    limit = min(int(args.get("limit", 20)), 50)
    qs = sales_selectors.sales_order_list()
    if status:
        qs = qs.filter(status=status)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)

    # QuerySet được sắp xếp sẵn từ selector, giới hạn limit
    qs = qs[:limit]
    return {
        "count": min(qs.count() if hasattr(qs, "count") else len(list(qs)), limit),
        "orders": [
            {
                "id": str(o.id),
                "customer": o.customer.customer_name if o.customer else None,
                "status": o.status,
                "total_amount": str(o.total_amount),
            }
            for o in qs
        ],
    }


def get_customer_debt_handler(args, user):
    PermissionChecker.check_permission(user, "crm.customer_view")
    customer_id = args.get("customer_id")
    if not customer_id:
        raise ValidationException("customer_id không được trống")
    debt = sales_selectors.get_customer_current_debt(customer_id)
    return {"customer_id": customer_id, "current_debt": str(debt)}


# ===== crm =====


def list_customers_handler(args, user):
    PermissionChecker.check_permission(user, "crm.customer_view")
    search = args.get("search", "").strip() or None
    limit = min(int(args.get("limit", 20)), 100)
    qs = crm_selectors.customer_list()
    if search:
        qs = qs.filter(customer_name__icontains=search)
    qs = qs[:limit]
    return {
        "count": min(qs.count() if hasattr(qs, "count") else len(list(qs)), limit),
        "customers": [
            {
                "id": str(c.id),
                "name": c.customer_name,
                "group": c.customer_group,
                "credit_limit": str(c.credit_limit),
                "is_credit_locked": c.is_credit_locked,
            }
            for c in qs
        ],
    }


# ===== purchasing =====


def list_purchase_orders_handler(args, user):
    PermissionChecker.check_permission(user, "purchasing.view_order")
    status = args.get("status")
    supplier_id = args.get("supplier_id")
    limit = min(int(args.get("limit", 20)), 50)
    qs = purchasing_selectors.purchase_order_list()
    if status:
        qs = qs.filter(status=status)
    if supplier_id:
        qs = qs.filter(vendor_id=supplier_id)

    qs = qs[:limit]
    return {
        "count": min(qs.count() if hasattr(qs, "count") else len(list(qs)), limit),
        "orders": [
            {
                "id": str(o.id),
                "vendor": o.vendor.supplier_name if o.vendor else None,
                "status": o.status,
                "total_amount": str(o.total_amount),
            }
            for o in qs
        ],
    }


# ===== procurement =====


def list_suppliers_handler(args, user):
    PermissionChecker.check_permission(user, "procurement.supplier_view")
    search = args.get("search", "").strip() or None
    limit = min(int(args.get("limit", 20)), 100)
    qs = proc_selectors.supplier_list()
    if search:
        qs = qs.filter(supplier_name__icontains=search)
    qs = qs[:limit]
    return {
        "count": min(qs.count() if hasattr(qs, "count") else len(list(qs)), limit),
        "suppliers": [
            {
                "id": str(s.id),
                "name": s.supplier_name,
                "group": s.supplier_group,
            }
            for s in qs
        ],
    }


# ===== manufacturing =====


def list_work_orders_handler(args, user):
    PermissionChecker.check_permission(user, "manufacturing.work_order_view")
    status = args.get("status")
    limit = min(int(args.get("limit", 20)), 50)
    qs = mfg_selectors.work_order_list(status=status)
    qs = qs[:limit]
    return {
        "count": min(qs.count() if hasattr(qs, "count") else len(list(qs)), limit),
        "work_orders": [
            {
                "id": str(w.id),
                "name": w.name,
                "status": w.status,
                "quantity": str(w.quantity),
                "produced_qty": str(w.produced_qty),
            }
            for w in qs
        ],
    }


def list_boms_handler(args, user):
    PermissionChecker.check_permission(user, "manufacturing.bom_view")
    search = args.get("search", "").strip() or None
    limit = min(int(args.get("limit", 20)), 50)
    qs = mfg_selectors.bom_list(search=search, is_active=True)
    qs = qs[:limit]
    return {
        "count": min(qs.count() if hasattr(qs, "count") else len(list(qs)), limit),
        "boms": [{"id": str(b.id), "name": b.name, "quantity": str(b.quantity)} for b in qs],
    }


# ===== finance =====


def list_cash_flows_handler(args, user):
    PermissionChecker.check_permission(user, "finance.view_cash_flow")
    status = args.get("status")
    limit = min(int(args.get("limit", 20)), 50)
    qs = finance_selectors.cash_flow_list(status=status) if status else finance_selectors.cash_flow_list()
    qs = qs[:limit]
    return {
        "count": min(qs.count() if hasattr(qs, "count") else len(list(qs)), limit),
        "transactions": [
            {
                "name": t.name,
                "payment_type": t.payment_type,
                "amount": str(t.amount),
                "payment_date": t.payment_date.isoformat() if t.payment_date else None,
                "status": t.status,
            }
            for t in qs
        ],
    }


def list_fixed_assets_handler(args, user):
    PermissionChecker.check_permission(user, "finance.view_fixed_asset")
    status = args.get("status")
    limit = min(int(args.get("limit", 20)), 100)
    status_filter = [status] if status else None
    qs = finance_selectors.fixed_asset_list(status_filter=status_filter)
    qs = qs[:limit]
    return {
        "count": min(qs.count() if hasattr(qs, "count") else len(list(qs)), limit),
        "assets": [
            {
                "asset_code": a.asset_code,
                "asset_name": a.asset_name,
                "original_value": str(a.original_value),
                "accumulated_depreciation": str(a.accumulated_depreciation),
                "status": a.status,
            }
            for a in qs
        ],
    }


# ===== Helper =====
def _serialize_item(item) -> dict:
    return {
        "item_code": item.item_code,
        "item_name": item.item_name,
        "item_group": item.item_group.name if item.item_group else None,
        "stock_uom": item.stock_uom.name if item.stock_uom else None,
        "minimum_threshold": str(item.minimum_threshold) if item.minimum_threshold else None,
        "status": item.status,
    }
