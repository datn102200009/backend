import datetime
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

from apps.finance.models import FixedAssetDepreciationLog, SalarySlip
from apps.hrm.models import Attendance, EmploymentContract, LeaveRequest
from apps.inventory.models import StockEntry, StockLedger
from apps.master_data.models import Employee, Item, Warehouse, WorkOrder
from apps.purchasing.models import PurchaseInvoice, PurchaseOrder, Shipment
from apps.sales.models import SalesInvoice, SalesOrder


# 1. sales_today_revenue
def get_sales_today_revenue():
    today = timezone.now().date()
    result = (
        SalesOrder.objects.filter(created_at__date=today)
        .exclude(status__in=[SalesOrder.Status.DRAFT, SalesOrder.Status.CANCELLED])
        .aggregate(revenue=Sum("total_amount"), count=Count("id"))
    )
    revenue = result["revenue"] or Decimal("0.00")
    count = result["count"] or 0
    return {"revenue": float(revenue), "order_count": count}


# 2. sales_draft_orders
def get_sales_draft_orders():
    orders = (
        SalesOrder.objects.filter(status=SalesOrder.Status.DRAFT).select_related("customer").order_by("-created_at")[:5]
    )
    return [
        {
            "id": str(o.id),
            "customer_name": o.customer.customer_name,
            "total_amount": float(o.total_amount),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


# 3. sales_pending_credit_bypass
def get_sales_pending_credit_bypass():
    from apps.sales.services import validate_sales_order_credit

    orders = (
        SalesOrder.objects.filter(status=SalesOrder.Status.PENDING_CREDIT_APPROVAL)
        .select_related("customer")
        .order_by("-created_at")[:5]
    )
    res = []
    for o in orders:
        _, reason = validate_sales_order_credit(str(o.id))
        res.append(
            {
                "id": str(o.id),
                "customer_name": o.customer.customer_name,
                "total_amount": float(o.total_amount),
                "reason": reason,
                "created_at": o.created_at.isoformat(),
            }
        )
    return res


# 4. sales_pending_fulfillment
def get_sales_pending_fulfillment():
    orders = (
        SalesOrder.objects.filter(status=SalesOrder.Status.PENDING)
        .select_related("customer")
        .order_by("-created_at")[:5]
    )
    return [
        {
            "id": str(o.id),
            "customer_name": o.customer.customer_name,
            "total_amount": float(o.total_amount),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


# 5. purchasing_active_po_count
def get_purchasing_active_po_count():
    count = PurchaseOrder.objects.filter(
        status__in=[
            PurchaseOrder.Status.PENDING,
            PurchaseOrder.Status.PAID_UNSHIPPED,
            PurchaseOrder.Status.SHIPPED_UNPAID,
        ]
    ).count()
    return {"active_po_count": count}


# 6. purchasing_draft_orders
def get_purchasing_draft_orders():
    orders = (
        PurchaseOrder.objects.filter(status=PurchaseOrder.Status.DRAFT)
        .select_related("vendor")
        .order_by("-created_at")[:5]
    )
    return [
        {
            "id": str(o.id),
            "supplier_name": o.vendor.supplier_name,
            "total_amount": float(o.total_amount),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


# 7. purchasing_pending_delivery
def get_purchasing_pending_delivery():
    orders = (
        PurchaseOrder.objects.filter(
            status__in=[
                PurchaseOrder.Status.PENDING,
                PurchaseOrder.Status.PAID_UNSHIPPED,
            ]
        )
        .select_related("vendor")
        .order_by("-created_at")[:5]
    )
    return [
        {
            "id": str(o.id),
            "supplier_name": o.vendor.supplier_name,
            "total_amount": float(o.total_amount),
            "expected_delivery_date": o.expected_delivery_date.isoformat() if o.expected_delivery_date else None,
            "receipt_fulfillment_rate": float(o.receipt_fulfillment_rate),
            "payment_fulfillment_rate": float(o.payment_fulfillment_rate),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


# 8. purchasing_pending_qc
def get_purchasing_pending_qc():
    shipments = Shipment.objects.filter(status=Shipment.Status.ARRIVED).order_by("-created_at")[:5]
    return [
        {
            "id": str(s.id),
            "shipment_num": s.shipment_num,
            "name": s.name,
            "created_at": s.created_at.isoformat(),
        }
        for s in shipments
    ]


# 9. purchasing_pending_logistic_fees
def get_purchasing_pending_logistic_fees():
    shipments = Shipment.objects.filter(status=Shipment.Status.INSPECTED).order_by("-created_at")[:5]
    return [
        {
            "id": str(s.id),
            "shipment_num": s.shipment_num,
            "name": s.name,
            "created_at": s.created_at.isoformat(),
        }
        for s in shipments
    ]


# 10. purchasing_blocked_invoices
def get_purchasing_blocked_invoices():
    invoices = (
        PurchaseInvoice.objects.filter(
            Q(status=PurchaseInvoice.Status.BLOCKED_FOR_PAYMENT) | ~Q(block_reason=None) & ~Q(block_reason="")
        )
        .exclude(status=PurchaseInvoice.Status.CANCELLED)
        .select_related("vendor")
        .order_by("-created_at")[:5]
    )
    return [
        {
            "id": str(i.id),
            "supplier_name": i.vendor.supplier_name,
            "total_amount": float(i.total_amount),
            "block_reason": i.block_reason,
            "created_at": i.created_at.isoformat(),
        }
        for i in invoices
    ]


# 11. inventory_pending_entry_count
def get_inventory_pending_entry_count():
    count = StockEntry.objects.filter(status="draft").count()
    return {"pending_entry_count": count}


# 12. inventory_low_stock (Optimized implementation from approved plan)
def get_warehouse_low_stock_alerts():
    today = timezone.now()
    thirty_days_ago = today - timedelta(days=30)

    # 1. Lọc danh sách Kho Khả dụng
    active_warehouses = Warehouse.objects.filter(is_active=True, is_group=False).exclude(
        Q(name__icontains="wip")
        | Q(name__icontains="sản xuất")
        | Q(name__icontains="phế phẩm")
        | Q(name__icontains="lỗi")
        | Q(name__icontains="qc")
    )
    warehouse_ids = list(active_warehouses.values_list("id", flat=True))
    if not warehouse_ids:
        return []

    # 2. Lấy số dư hiện tại của từng cặp (Item, Warehouse)
    balances = (
        StockLedger.objects.filter(warehouse_id__in=warehouse_ids)
        .values("item_id", "warehouse_id")
        .annotate(total_balance=Sum("actual_quantity"))
        .filter(total_balance__gt=0)
    )

    if not balances:
        return []

    # 3. Lấy lượng tiêu thụ trong 30 ngày qua (Chỉ lấy Stock Issue)
    consumption_data = (
        StockLedger.objects.filter(
            warehouse_id__in=warehouse_ids,
            voucher_type="Stock Issue",
            actual_quantity__lt=0,
            posting_date__gte=thirty_days_ago,
        )
        .values("item_id", "warehouse_id")
        .annotate(total_issued=Sum("actual_quantity"))
    )

    # Tra cứu nhanh: (item_id, warehouse_id) -> total_issued (dương)
    consumption_map = {(c["item_id"], c["warehouse_id"]): abs(c["total_issued"]) for c in consumption_data}

    # 4. Cache thông tin Master Data vào memory để tránh query liên tục trong loop
    item_ids = [b["item_id"] for b in balances]
    items_map = {item.id: item for item in Item.objects.filter(id__in=item_ids).select_related("stock_uom")}
    warehouses_map = {wh.id: wh for wh in active_warehouses}

    alert_list = []

    # 5. Phân tích cảnh báo (Không gọi query DB nào trong loop này)
    for b in balances:
        item_id = b["item_id"]
        wh_id = b["warehouse_id"]
        balance = b["total_balance"]

        item = items_map.get(item_id)
        warehouse = warehouses_map.get(wh_id)
        if not item or not warehouse:
            continue

        issued = consumption_map.get((item_id, wh_id), Decimal("0.00"))
        adc = issued / Decimal("30.0")

        # Ngưỡng fallback tĩnh theo UOM
        uom_name = item.stock_uom.name.lower() if item.stock_uom else ""
        fallback_threshold = Decimal("10.0")
        if uom_name in ["tấn", "ton", "kg"]:
            fallback_threshold = Decimal("0.5")
        elif uom_name in ["cái", "piece", "pcs"]:
            fallback_threshold = Decimal("200.0")

        is_alert = False
        alert_reason = ""
        days_left = None
        status = "normal"

        if adc > 0:
            days_left = float(balance / adc)
            if days_left <= 3.0:
                is_alert = True
                status = "critical"
                alert_reason = f"Khẩn cấp (Còn {days_left:.1f} ngày dùng)"
            elif days_left <= 7.0:
                is_alert = True
                status = "warning"
                alert_reason = f"Cảnh báo (Còn {days_left:.1f} ngày dùng)"
        else:
            if balance < fallback_threshold:
                is_alert = True
                status = "critical"
                alert_reason = f"Dưới ngưỡng tối thiểu ({balance:.1f}/{fallback_threshold:.1f} {item.stock_uom.name})"

        if is_alert:
            wh_name_lower = warehouse.name.lower()
            action_suggest = "Tạo Lệnh sản xuất (WO)" if "thành phẩm" in wh_name_lower else "Tạo Yêu cầu Mua hàng (PO)"

            alert_list.append(
                {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "uom": item.stock_uom.name if item.stock_uom else "",
                    "warehouse_name": warehouse.name,
                    "balance": float(balance),
                    "days_left": days_left,
                    "status": status,
                    "reason": alert_reason,
                    "action_suggest": action_suggest,
                }
            )

    # Sắp xếp cảnh báo: Mức độ khẩn cấp lên trước, sau đó là ngày còn lại tăng dần
    alert_list.sort(
        key=lambda x: (0 if x["status"] == "critical" else 1, x["days_left"] if x["days_left"] is not None else 9999.0)
    )

    return alert_list[:5]


# 13. inventory_pending_entries
def get_inventory_pending_entries():
    from django.db.models import Prefetch

    from apps.inventory.models import StockEntryDetail

    entries = (
        StockEntry.objects.filter(status="draft")
        .select_related("purchase_order", "sales_order", "work_order", "shipment")
        .prefetch_related(
            Prefetch(
                "details", queryset=StockEntryDetail.objects.select_related("source_warehouse", "target_warehouse")
            )
        )
        .order_by("-created_at")[:5]
    )

    results = []
    for e in entries:
        route_desc = ""
        if e.purpose == "transfer":
            first_detail = e.details.first()
            if first_detail and first_detail.source_warehouse and first_detail.target_warehouse:
                route_desc = f"{first_detail.source_warehouse.name} → {first_detail.target_warehouse.name}"
            elif first_detail and first_detail.source_warehouse:
                route_desc = f"Từ {first_detail.source_warehouse.name}"
            elif first_detail and first_detail.target_warehouse:
                route_desc = f"Đến {first_detail.target_warehouse.name}"
        elif e.purpose == "receipt":
            if e.purchase_order:
                route_desc = f"Từ PO: {e.purchase_order.id}"
            elif e.shipment:
                route_desc = f"Từ lô: {e.shipment.shipment_num}"
            else:
                route_desc = "Nhập kho"
        elif e.purpose == "issue":
            if e.sales_order:
                route_desc = f"Cho SO: {e.sales_order.id}"
            elif e.work_order:
                route_desc = f"Cho WO: {e.work_order.name}"
            else:
                route_desc = "Xuất kho"
        elif e.purpose == "manufacture":
            if e.work_order:
                route_desc = f"Sản xuất WO: {e.work_order.name}"
            else:
                route_desc = "Sản xuất thành phẩm"
        else:
            route_desc = e.remarks or "Khác"

        results.append(
            {
                "id": str(e.id),
                "name": e.name,
                "purpose": e.purpose,
                "remarks": e.remarks,
                "route_desc": route_desc,
                "item_count": e.details.count(),
                "posting_date": e.posting_date.isoformat(),
                "created_at": e.created_at.isoformat(),
            }
        )
    return results


# 14. finance_cashflow_chart
def get_finance_cashflow_chart():
    from apps.finance.models import CashFlowTransaction

    start_date = timezone.now().date() - timedelta(days=28)
    txs = (
        CashFlowTransaction.objects.filter(payment_date__gte=start_date)
        .annotate(week=TruncWeek("payment_date"))
        .values("week", "payment_type")
        .annotate(total=Sum("amount"))
        .order_by("week")
    )

    weeks_data = {}
    for i in range(4):
        w_start = start_date + timedelta(weeks=i)
        w_start_monday = w_start - timedelta(days=w_start.weekday())
        label = f"Tuần {w_start_monday.strftime('%d/%m')}"
        weeks_data[w_start_monday] = {"week_label": label, "receive": 0.0, "pay": 0.0}

    for t in txs:
        w_date = t["week"]
        if w_date in weeks_data:
            ptype = t["payment_type"]
            total = float(t["total"] or 0)
            if ptype == "receive":
                weeks_data[w_date]["receive"] = total
            elif ptype == "pay":
                weeks_data[w_date]["pay"] = total

    return {"weeks": list(weeks_data.values())}


# 15. finance_cashflow_summary
def get_finance_cashflow_summary():
    from apps.finance.models import CashFlowTransaction

    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    totals = (
        CashFlowTransaction.objects.filter(payment_date__gte=start_of_month, payment_date__lte=today)
        .values("payment_type")
        .annotate(total=Sum("amount"))
    )
    receive = 0.0
    pay = 0.0
    for t in totals:
        if t["payment_type"] == "receive":
            receive = float(t["total"] or 0)
        elif t["payment_type"] == "pay":
            pay = float(t["total"] or 0)
    return {"receive_total": receive, "pay_total": pay, "net_cashflow": receive - pay}


# 16. finance_unpaid_purchase_invoices
def get_finance_unpaid_purchase_invoices():
    invoices = (
        PurchaseInvoice.objects.filter(status__in=[PurchaseInvoice.Status.UNPAID, PurchaseInvoice.Status.PARTIAL])
        .select_related("vendor")
        .order_by("due_date", "-created_at")[:5]
    )
    return [
        {
            "id": str(i.id),
            "supplier_name": i.vendor.supplier_name,
            "total_amount": float(i.total_amount),
            "remaining_amount": float(i.total_amount - i.paid_amount),
            "due_date": i.due_date.isoformat() if i.due_date else None,
            "created_at": i.created_at.isoformat(),
        }
        for i in invoices
    ]


# 17. finance_unpaid_sales_invoices
def get_finance_unpaid_sales_invoices():
    invoices = (
        SalesInvoice.objects.filter(status__in=[SalesInvoice.Status.UNPAID, SalesInvoice.Status.PARTIAL])
        .select_related("customer")
        .order_by("-created_at")[:5]
    )
    return [
        {
            "id": str(i.id),
            "customer_name": i.customer.customer_name,
            "total_amount": float(i.total_amount),
            "remaining_amount": float(i.total_amount - i.paid_amount),
            "created_at": i.created_at.isoformat(),
        }
        for i in invoices
    ]


# 18. finance_depreciation_status
def get_finance_depreciation_status():
    current_period = timezone.now().strftime("%Y-%m")
    res = FixedAssetDepreciationLog.objects.filter(period=current_period).aggregate(
        count=Count("asset_id", distinct=True), total=Sum("depreciation_amount")
    )
    return {"depreciated_assets_count": res["count"] or 0, "total_depreciation_amount": float(res["total"] or 0)}


# 19. hrm_payroll_lifecycle_status
def get_hrm_payroll_lifecycle_status():
    latest_slip = SalarySlip.objects.order_by("-salary_period").first()
    if not latest_slip:
        current_period = timezone.now().strftime("%Y-%m")
        return {
            "status": "No salary slips",
            "salary_period": current_period,
            "net_pay_total": 0.0,
            "calculated_slips_count": 0,
        }

    period = latest_slip.salary_period
    slips = SalarySlip.objects.filter(salary_period=period)
    statuses = set(slips.values_list("status", flat=True))
    overall_status = "Draft"
    if "draft" in statuses:
        overall_status = "Draft"
    elif "calculated" in statuses:
        overall_status = "Calculated"
    elif "submitted" in statuses:
        overall_status = "Submitted"
    elif "approved" in statuses:
        overall_status = "Approved"
    elif "paid" in statuses:
        overall_status = "Paid"

    totals = slips.aggregate(net_pay=Sum("net_pay"), count=Count("id"))
    return {
        "status": overall_status,
        "salary_period": period,
        "net_pay_total": float(totals["net_pay"] or 0),
        "calculated_slips_count": totals["count"] or 0,
    }


# 20. hrm_pending_leave_requests
def get_hrm_pending_leave_requests():
    requests = LeaveRequest.objects.filter(status="pending").select_related("employee").order_by("-created_at")[:5]
    return [
        {
            "id": str(r.id),
            "employee_name": r.employee.full_name,
            "leave_type": r.get_leave_type_display(),
            "start_date": r.start_date.isoformat(),
            "end_date": r.end_date.isoformat(),
            "days": float(r.days),
            "created_at": r.created_at.isoformat(),
        }
        for r in requests
    ]


# 21. hrm_expiring_contracts
def get_hrm_expiring_contracts():
    today = timezone.now().date()
    thirty_days_later = today + timedelta(days=30)
    contracts = (
        EmploymentContract.objects.filter(status="active", end_date__gte=today, end_date__lte=thirty_days_later)
        .select_related("employee")
        .order_by("end_date")[:5]
    )
    return [
        {
            "id": str(c.id),
            "employee_name": c.employee.full_name,
            "contract_no": c.contract_no,
            "contract_type": c.get_contract_type_display(),
            "end_date": c.end_date.isoformat(),
            "created_at": c.created_at.isoformat(),
        }
        for c in contracts
    ]


# 22. hrm_employees_without_contract
def get_hrm_employees_without_contract():
    employees = (
        Employee.objects.filter(employment_status="active")
        .exclude(id__in=EmploymentContract.objects.filter(status="active").values("employee_id"))
        .order_by("join_date")[:5]
    )
    return [
        {
            "id": str(e.id),
            "employee_id": e.employee_id,
            "full_name": e.full_name,
            "join_date": e.join_date.isoformat() if e.join_date else None,
            "department": e.department,
        }
        for e in employees
    ]


# 23. hrm_today_attendance_rate
def get_hrm_today_attendance_rate():
    today = timezone.now().date()
    total_employees = Employee.objects.filter(employment_status="active").count()
    if total_employees == 0:
        return {"attendance_rate": 0.0, "present_count": 0, "absent_count": 0, "total_active_employees": 0}
    present_count = Attendance.objects.filter(date=today, status="working").count()
    leave_count = Attendance.objects.filter(date=today, status__in=["paid_leave", "unpaid_leave"]).count()
    absent_count = total_employees - present_count - leave_count
    rate = (present_count / total_employees) * 100.0
    return {
        "attendance_rate": round(rate, 2),
        "present_count": present_count,
        "absent_count": absent_count,
        "total_active_employees": total_employees,
    }


# 24. manufacturing_pending_wo_approval
def get_manufacturing_pending_wo_approval():
    orders = (
        WorkOrder.objects.filter(status="pending_approval")
        .select_related("production_item")
        .order_by("-created_at")[:5]
    )
    return [
        {
            "id": str(o.id),
            "name": o.name,
            "production_item_name": o.production_item.item_name,
            "quantity": float(o.quantity),
            "planned_start_date": o.planned_start_date.isoformat(),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


# 25. manufacturing_active_wos
def get_manufacturing_active_wos():
    orders = (
        WorkOrder.objects.filter(status="in_progress").select_related("production_item").order_by("-created_at")[:5]
    )
    return [
        {
            "id": str(o.id),
            "name": o.name,
            "production_item_name": o.production_item.item_name,
            "quantity": float(o.quantity),
            "produced_qty": float(o.produced_qty),
            "planned_start_date": o.planned_start_date.isoformat(),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


# 26. manufacturing_pending_declarations
def get_manufacturing_pending_declarations():
    orders = (
        WorkOrder.objects.filter(status="in_progress", produced_qty__lt=F("quantity"))
        .select_related("production_item")
        .order_by("-created_at")[:5]
    )
    return [
        {
            "id": str(o.id),
            "name": o.name,
            "production_item_name": o.production_item.item_name,
            "quantity": float(o.quantity),
            "produced_qty": float(o.produced_qty),
            "planned_start_date": o.planned_start_date.isoformat(),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


# 27. manufacturing_pending_completion
def get_manufacturing_pending_completion():
    orders = (
        WorkOrder.objects.filter(status="in_progress", produced_qty__gte=F("quantity"))
        .select_related("production_item", "target_warehouse")
        .order_by("-created_at")[:5]
    )
    return [
        {
            "id": str(o.id),
            "name": o.name,
            "production_item_name": o.production_item.item_name,
            "quantity": float(o.quantity),
            "produced_qty": float(o.produced_qty),
            "target_warehouse_name": o.target_warehouse.name if o.target_warehouse else None,
            "planned_start_date": o.planned_start_date.isoformat(),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


# Map widget_code to selector function
SELECTORS_MAP = {
    "sales_today_revenue": get_sales_today_revenue,
    "sales_draft_orders": get_sales_draft_orders,
    "sales_pending_credit_bypass": get_sales_pending_credit_bypass,
    "sales_pending_fulfillment": get_sales_pending_fulfillment,
    "purchasing_active_po_count": get_purchasing_active_po_count,
    "purchasing_draft_orders": get_purchasing_draft_orders,
    "purchasing_pending_delivery": get_purchasing_pending_delivery,
    "purchasing_pending_qc": get_purchasing_pending_qc,
    "purchasing_pending_logistic_fees": get_purchasing_pending_logistic_fees,
    "purchasing_blocked_invoices": get_purchasing_blocked_invoices,
    "inventory_pending_entry_count": get_inventory_pending_entry_count,
    "inventory_low_stock": get_warehouse_low_stock_alerts,
    "inventory_pending_entries": get_inventory_pending_entries,
    "finance_cashflow_chart": get_finance_cashflow_chart,
    "finance_cashflow_summary": get_finance_cashflow_summary,
    "finance_unpaid_purchase_invoices": get_finance_unpaid_purchase_invoices,
    "finance_unpaid_sales_invoices": get_finance_unpaid_sales_invoices,
    "finance_depreciation_status": get_finance_depreciation_status,
    "hrm_payroll_lifecycle_status": get_hrm_payroll_lifecycle_status,
    "hrm_pending_leave_requests": get_hrm_pending_leave_requests,
    "hrm_expiring_contracts": get_hrm_expiring_contracts,
    "hrm_employees_without_contract": get_hrm_employees_without_contract,
    "hrm_today_attendance_rate": get_hrm_today_attendance_rate,
    "manufacturing_pending_wo_approval": get_manufacturing_pending_wo_approval,
    "manufacturing_active_wos": get_manufacturing_active_wos,
    "manufacturing_pending_declarations": get_manufacturing_pending_declarations,
    "manufacturing_pending_completion": get_manufacturing_pending_completion,
}
