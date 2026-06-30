import datetime
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone

from apps.finance.models import CashFlowTransaction, FixedAsset, FixedAssetDepreciationLog, SalarySlip
from apps.hrm.models import Attendance, EmploymentContract, LeaveRequest
from apps.inventory.models import StockEntry, StockLedger
from apps.master_data.models import BOMItem, Employee, Item, Warehouse, WorkOrder
from apps.purchasing.models import PurchaseInvoice, PurchaseOrder, Shipment
from apps.sales.models import SalesInvoice, SalesOrder


class DashboardList(list):
    def __init__(self, items, total_count=None):
        super().__init__(items)
        self.total_count = total_count if total_count is not None else len(items)


class DashboardDict(dict):
    def __init__(self, data, total_count=None):
        super().__init__(data)
        self.total_count = total_count if total_count is not None else 0


def format_num(val):
    if val is None:
        return "0"
    val = Decimal(str(val)) if not isinstance(val, Decimal) else val
    if val % 1 == 0:
        return str(int(val))
    return f"{float(val):.1f}"


# 1. sales_today_revenue (Doanh thu 7 ngày gần nhất)
def get_sales_today_revenue():
    today = timezone.localdate()
    start_date = today - timedelta(days=6)

    orders = (
        SalesOrder.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=today,
        )
        .exclude(status__in=[SalesOrder.Status.DRAFT, SalesOrder.Status.CANCELLED])
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(total=Sum("total_amount"))
    )

    revenue_map = {o["date"]: o["total"] for o in orders if o["date"] is not None}

    points = []
    for i in range(7):
        current_date = start_date + timedelta(days=i)
        revenue = revenue_map.get(current_date) or Decimal("0")
        points.append(
            {
                "date": current_date.isoformat(),
                "revenue": str(revenue),
            }
        )

    return {"points": points}


def _build_items_summary(order) -> str:
    """
    Tạo chuỗi tóm tắt sản phẩm của đơn hàng.
    Định dạng: "SP1: SL1, SP2: SL2" hoặc "SP1: SL1, SP2: SL2 và +N sản phẩm khác".
    """
    lines = list(order.lines.all())
    if not lines:
        return ""

    shown = lines[:2]
    parts = []
    for line in shown:
        item_name = line.item.item_name if line.item else "Sản phẩm"
        qty = line.quantity
        qty_str = str(qty)
        if "." in qty_str:
            qty_str = qty_str.rstrip("0").rstrip(".")
        parts.append(f"{item_name}: {qty_str}")

    summary = ", ".join(parts)
    total_lines = len(lines)
    if total_lines > 2:
        summary += f" và +{total_lines - 2} sản phẩm khác"

    return summary


# 2. sales_draft_orders
def get_sales_draft_orders():
    orders_qs = (
        SalesOrder.objects.filter(status=SalesOrder.Status.DRAFT)
        .select_related("customer")
        .prefetch_related("lines__item")
        .order_by("-created_at")
    )
    total_count = orders_qs.count()
    results = [
        {
            "id": str(o.id),
            "customer_name": o.customer.customer_name,
            "total_amount": str(o.total_amount),
            "items_summary": _build_items_summary(o),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders_qs[:5]
    ]
    return {
        "total_count": total_count,
        "top_items": results,
    }


# 3. sales_pending_credit_bypass
def get_sales_pending_credit_bypass():
    from apps.sales.services import validate_sales_order_credit

    orders_qs = (
        SalesOrder.objects.filter(status=SalesOrder.Status.PENDING_CREDIT_APPROVAL)
        .select_related("customer")
        .order_by("-created_at")
    )
    total_count = orders_qs.count()
    res = []
    for o in orders_qs[:5]:
        _, reason = validate_sales_order_credit(str(o.id))
        res.append(
            {
                "id": str(o.id),
                "customer_name": o.customer.customer_name,
                "total_amount": str(o.total_amount),
                "reason": reason,
                "created_at": o.created_at.isoformat(),
            }
        )
    return {
        "total_count": total_count,
        "top_items": res,
    }


# 4. sales_pending_fulfillment
def get_sales_pending_fulfillment():
    orders_qs = (
        SalesOrder.objects.filter(status=SalesOrder.Status.PENDING)
        .select_related("customer")
        .prefetch_related("lines__item")
        .order_by("-created_at")
    )
    total_count = orders_qs.count()
    results = [
        {
            "id": str(o.id),
            "customer_name": o.customer.customer_name,
            "total_amount": str(o.total_amount),
            "items_summary": _build_items_summary(o),
            "receipt_fulfillment_rate": str(o.receipt_fulfillment_rate),
            "payment_fulfillment_rate": str(o.payment_fulfillment_rate),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders_qs[:5]
    ]
    return {
        "total_count": total_count,
        "top_items": results,
    }


# 5. purchasing_active_po_count (Đơn mua hàng hoạt động)
def get_purchasing_active_po_count():
    orders_qs = PurchaseOrder.objects.filter(
        status__in=[
            PurchaseOrder.Status.PENDING,
            PurchaseOrder.Status.PAID_UNSHIPPED,
            PurchaseOrder.Status.SHIPPED_UNPAID,
        ]
    )
    total_count = orders_qs.count()
    total_pending_amount = orders_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

    top_pos = orders_qs.select_related("vendor").prefetch_related("lines__item").order_by("-created_at")[:5]
    top_items = [
        {
            "id": str(o.id),
            "supplier_name": o.vendor.supplier_name,
            "total_amount": str(o.total_amount),
            "items_summary": _build_items_summary(o),
            "expected_delivery_date": o.expected_delivery_date.isoformat() if o.expected_delivery_date else None,
            "receipt_fulfillment_rate": str(o.receipt_fulfillment_rate),
            "payment_fulfillment_rate": str(o.payment_fulfillment_rate),
            "created_at": o.created_at.isoformat(),
        }
        for o in top_pos
    ]

    return {
        "total_count": total_count,
        "top_items": top_items,
        "active_po_count": total_count,
        "total_pending_amount": f"{total_pending_amount:.2f}",
    }


# 6. purchasing_draft_orders
def get_purchasing_draft_orders():
    orders_qs = (
        PurchaseOrder.objects.filter(status=PurchaseOrder.Status.DRAFT)
        .select_related("vendor")
        .prefetch_related("lines__item")
        .order_by("-created_at")
    )
    total_count = orders_qs.count()
    results = [
        {
            "id": str(o.id),
            "supplier_name": o.vendor.supplier_name,
            "total_amount": str(o.total_amount),
            "items_summary": _build_items_summary(o),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders_qs[:5]
    ]
    return {
        "total_count": total_count,
        "top_items": results,
    }


# 9. purchasing_pending_logistic_fees (Lô Hàng Đang Tiếp Nhận)
def get_purchasing_pending_logistic_fees():
    from django.db.models import Case, IntegerField, Value, When

    # Lấy cả DRAFT và INSPECTING, ưu tiên INSPECTING lên trước
    shipments_qs = (
        Shipment.objects.filter(status__in=[Shipment.Status.DRAFT, Shipment.Status.INSPECTING])
        .annotate(
            status_priority=Case(
                When(status=Shipment.Status.INSPECTING, then=Value(0)),  # ưu tiên 1
                When(status=Shipment.Status.DRAFT, then=Value(1)),  # ưu tiên 2
                default=Value(2),
                output_field=IntegerField(),
            )
        )
        .order_by("status_priority", "-created_at")
    )
    total_count = shipments_qs.count()
    results = [
        {
            "id": str(s.id),
            "shipment_num": s.shipment_num,
            "name": s.name,
            "status": s.status,
            "purchase_order_id": str(s.purchase_order_id) if s.purchase_order_id else None,
            "purchase_order_name": str(s.purchase_order_id)[:8].upper() if s.purchase_order_id else None,
            "remarks": s.remarks,
            "created_at": s.created_at.isoformat(),
        }
        for s in shipments_qs[:5]
    ]
    return {
        "total_count": total_count,
        "top_items": results,
    }


# 9b. purchasing_pending_approval_shipments (Lô Hàng Chờ Duyệt Chi Phí)
def get_purchasing_pending_approval_shipments():
    shipments_qs = Shipment.objects.filter(status=Shipment.Status.PENDING_APPROVAL).order_by("-created_at")
    total_count = shipments_qs.count()
    results = [
        {
            "id": str(s.id),
            "shipment_num": s.shipment_num,
            "name": s.name,
            "status": s.status,
            "purchase_order_id": str(s.purchase_order_id) if s.purchase_order_id else None,
            "purchase_order_name": str(s.purchase_order_id)[:8].upper() if s.purchase_order_id else None,
            "remarks": s.remarks,
            "created_at": s.created_at.isoformat(),
        }
        for s in shipments_qs[:5]
    ]
    return {
        "total_count": total_count,
        "top_items": results,
    }


# 12. inventory_low_stock (Optimized implementation from approved plan)
def get_warehouse_low_stock_alerts():
    today = timezone.now()
    thirty_days_ago = today - timedelta(days=30)

    # 1. Lọc danh sách Kho Khả dụng bằng whitelist tên kho
    WAREHOUSE_NVL_NAMES = ("Kho Nguyên Vật Liệu",)  # Phân loại: NVL
    WAREHOUSE_TP_NAMES = ("Kho Thành Phẩm",)  # Phân loại: THANH_PHAM
    ALLOWED_WAREHOUSE_NAMES = WAREHOUSE_NVL_NAMES + WAREHOUSE_TP_NAMES

    active_warehouses = Warehouse.objects.filter(
        is_active=True,
        is_group=False,
        name__in=ALLOWED_WAREHOUSE_NAMES,
    )
    warehouse_ids = list(active_warehouses.values_list("id", flat=True))
    if not warehouse_ids:
        return {
            "items": [],
            "product_distribution": {},
            "warehouses": [],
            "total_count": 0,
        }

    # 2. Lấy số dư hiện tại của từng cặp (Item, Warehouse)
    balances = (
        StockLedger.objects.filter(warehouse_id__in=warehouse_ids)
        .values("item_id", "warehouse_id")
        .annotate(total_balance=Sum("actual_quantity"))
        .filter(total_balance__gt=0)
    )

    if not balances:
        return {
            "items": [],
            "product_distribution": {},
            "warehouses": [{"id": str(wh.id), "name": wh.name} for wh in active_warehouses],
            "total_count": 0,
        }

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

    # 4. Cache thông tin Master Data và lấy nhu cầu từ các WorkOrder draft (pending_approval) quy đổi theo BOM
    item_ids = [b["item_id"] for b in balances]
    items_map = {item.id: item for item in Item.objects.filter(id__in=item_ids).select_related("stock_uom")}
    warehouses_map = {wh.id: wh for wh in active_warehouses}

    wo_demands = BOMItem.objects.filter(item_id__in=item_ids, parent__work_orders__status="pending_approval").annotate(
        wo_qty=F("parent__work_orders__quantity"), bom_qty=F("parent__quantity"), wo_id=F("parent__work_orders__id")
    )

    component_demand_map = {}
    for demand in wo_demands:
        comp_id = demand.item_id
        wo_qty = demand.wo_qty
        bom_qty = demand.bom_qty if demand.bom_qty else Decimal("1.0")
        if bom_qty == 0:
            bom_qty = Decimal("1.0")

        needed = (demand.quantity * wo_qty) / bom_qty

        if comp_id not in component_demand_map:
            component_demand_map[comp_id] = {"total_demand": Decimal("0.00"), "wo_ids": set()}
        component_demand_map[comp_id]["total_demand"] += needed
        component_demand_map[comp_id]["wo_ids"].add(demand.wo_id)

    product_distribution = {}

    for b in balances:
        item_id_str = str(b["item_id"])
        wh_id_str = str(b["warehouse_id"])
        bal_str = str(b["total_balance"])
        if item_id_str not in product_distribution:
            product_distribution[item_id_str] = {}
        product_distribution[item_id_str][wh_id_str] = bal_str

    # Group balances by item
    item_balances = {}
    for b in balances:
        item_id = b["item_id"]
        if item_id not in item_balances:
            item_balances[item_id] = []
        item_balances[item_id].append(b)

    items_list = []
    for item_id, b_list in item_balances.items():
        item = items_map.get(item_id)
        if not item:
            continue

        item_id_str = str(item_id)
        total_balance = sum(b["total_balance"] for b in b_list)

        # Ngưỡng tối thiểu tồn kho của Item
        threshold = item.minimum_threshold
        if threshold is None:
            uom_name = item.stock_uom.name.lower() if item.stock_uom else ""
            threshold = Decimal("10.0")
            if uom_name in ["tấn", "ton", "kg"]:
                threshold = Decimal("0.5")
            elif uom_name in ["cái", "piece", "pcs"]:
                threshold = Decimal("200.0")

        min_days_left = None
        dos_status = "normal"
        dos_reason = ""
        dos_shortage = Decimal("0.00")

        for b in b_list:
            wh_id = b["warehouse_id"]
            balance = b["total_balance"]
            warehouse = warehouses_map.get(wh_id)
            if not warehouse:
                continue

            issued = consumption_map.get((item_id, wh_id), Decimal("0.00"))
            adc = issued / Decimal("30.0")

            if adc > 0:
                days_left_dec = balance / adc
                days_left = float(days_left_dec)
                days_left_str = format_num(days_left)
                if min_days_left is None or days_left < min_days_left:
                    min_days_left = days_left

                if days_left_dec <= Decimal("7.0"):
                    wh_shortage = max(Decimal("0"), Decimal("1") - (days_left_dec / Decimal("7.0")))
                    dos_shortage = max(dos_shortage, wh_shortage)
                    if days_left <= 3.0:
                        if dos_status != "critical":
                            dos_status = "critical"
                            dos_reason = f"Khẩn cấp (Còn {days_left_str} ngày dùng tại {warehouse.name})"
                    elif days_left <= 7.0:
                        if dos_status == "normal":
                            dos_status = "warning"
                            dos_reason = f"Cảnh báo (Còn {days_left_str} ngày dùng tại {warehouse.name})"

        # Xây dựng cảnh báo below_threshold_alert dựa trên TỔNG tồn kho
        # - Dưới 100% ngưỡng: cảnh báo đỏ (critical)
        # - Từ 100% - 150% ngưỡng: cảnh báo vàng (warning)
        below_threshold_active = total_balance < (threshold * Decimal("1.5"))
        below_threshold_level = "normal"
        below_threshold_reason = ""
        below_threshold_ratio = Decimal("0.00")
        if below_threshold_active:
            if total_balance < threshold:
                below_threshold_level = "critical"
                below_threshold_label = "Dưới ngưỡng tối thiểu"
                below_threshold_ratio = max(Decimal("0"), Decimal("1") - (total_balance / threshold))
            else:
                below_threshold_level = "warning"
                below_threshold_label = "Cận ngưỡng tối thiểu"
                below_threshold_ratio = max(Decimal("0"), Decimal("1.5") - (total_balance / threshold))
            below_threshold_reason = (
                f"{below_threshold_label}: tổng tồn kho {format_num(total_balance)}/{format_num(threshold)} {item.stock_uom.name if item.stock_uom else ''} "
                f"trên toàn bộ hệ thống"
            )

        # Xây dựng cảnh báo projected_shortage_alert (cảnh báo vàng)
        demand_info = component_demand_map.get(item_id, {"total_demand": Decimal("0.00"), "wo_ids": set()})
        total_wo_demand_for_item = demand_info["total_demand"]
        wo_count = len(demand_info["wo_ids"])

        projected_shortage = max(Decimal("0"), total_wo_demand_for_item - total_balance)
        projected_shortage_active = total_wo_demand_for_item > total_balance
        projected_shortage_level = "warning" if projected_shortage_active else "normal"
        projected_shortage_reason = ""
        projected_ratio = Decimal("0.00")
        if projected_shortage_active:
            projected_shortage_reason = (
                f"Sẽ thiếu ~{format_num(projected_shortage)} {item.stock_uom.name if item.stock_uom else ''} "
                f"nếu duyệt tất cả {wo_count} lệnh sản xuất chờ duyệt "
                f"(nhu cầu: {format_num(total_wo_demand_for_item)} {item.stock_uom.name if item.stock_uom else ''}) "
            )
            projected_ratio = (
                projected_shortage / (total_balance + projected_shortage)
                if (total_balance + projected_shortage) > 0
                else Decimal("0.00")
            )

        # Determine highest_status and highest_reason for backward compatibility
        highest_status = "normal"
        highest_reason = ""
        if dos_status == "critical":
            highest_status = "critical"
            highest_reason = dos_reason
        elif below_threshold_active and below_threshold_level == "critical":
            highest_status = "critical"
            highest_reason = below_threshold_reason
        elif below_threshold_active and below_threshold_level == "warning":
            highest_status = "warning"
            highest_reason = below_threshold_reason
        elif dos_status == "warning":
            highest_status = "warning"
            highest_reason = dos_reason
        elif projected_shortage_active:
            highest_status = "warning"
            highest_reason = projected_shortage_reason

        max_shortage_ratio = max(dos_shortage, below_threshold_ratio, projected_ratio)

        # Build unified alerts array — sorted by severity (critical trước warning)
        # Trong cùng mức severity, thứ tự: dos → below_threshold → projected_shortage
        alerts = []
        if dos_status == "critical":
            alerts.append({"category": "dos", "level": "critical", "reason": dos_reason})
        if below_threshold_active and below_threshold_level == "critical":
            alerts.append({"category": "below_threshold", "level": "critical", "reason": below_threshold_reason})
        if below_threshold_active and below_threshold_level == "warning":
            alerts.append({"category": "below_threshold", "level": "warning", "reason": below_threshold_reason})
        if dos_status == "warning":
            alerts.append({"category": "dos", "level": "warning", "reason": dos_reason})
        if projected_shortage_active:
            alerts.append({"category": "projected_shortage", "level": "warning", "reason": projected_shortage_reason})

        items_list.append(
            {
                "id": item_id_str,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "uom": item.stock_uom.name if item.stock_uom else "",
                "status": highest_status,
                "reason": highest_reason,
                "alerts": alerts,
                "shortage_ratio": max_shortage_ratio,
                "total_balance": total_balance,
                "days_left": min_days_left if min_days_left is not None else 9999.0,
            }
        )

    items_list.sort(
        key=lambda x: (
            0 if x["status"] == "critical" else (1 if x["status"] == "warning" else 2),
            -x["shortage_ratio"],
            x["total_balance"],
        )
    )

    for item in items_list:
        item.pop("days_left", None)
        item["shortage_ratio"] = f"{item['shortage_ratio']:.3f}"
        item["total_balance"] = f"{item['total_balance']:.2f}"

    warehouses_list = [{"id": str(wh.id), "name": wh.name} for wh in active_warehouses]

    return {
        "items": items_list,
        "product_distribution": product_distribution,
        "warehouses": warehouses_list,
        "total_count": len(items_list),
    }


def _build_route_desc(e):
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
    return route_desc


# 13. inventory_pending_entries
def get_inventory_pending_entries(purpose=None):
    from django.db.models import Prefetch

    from apps.inventory.models import StockEntryDetail

    entries_qs = (
        StockEntry.objects.filter(status="draft")
        .select_related("purchase_order", "sales_order", "work_order", "shipment")
        .prefetch_related(
            Prefetch(
                "details", queryset=StockEntryDetail.objects.select_related("source_warehouse", "target_warehouse")
            )
        )
    )
    if purpose and purpose != "all":
        entries_qs = entries_qs.filter(purpose=purpose)

    entries_qs = entries_qs.order_by("-created_at")
    total_count = entries_qs.count()

    results = []
    for e in entries_qs[:5]:
        route_desc = _build_route_desc(e)
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
    return {
        "total_count": total_count,
        "top_items": results,
    }


# 14. finance_cashflow_overview (Tổng quan & Xu hướng dòng tiền)
def get_finance_cashflow_overview():
    from apps.finance.models import CashFlowTransaction

    today = timezone.localdate()
    start_date = today - timedelta(days=28)

    # 1. Summary - dùng aggregate với Sum để tránh load full queryset
    month_txs_agg = CashFlowTransaction.objects.filter(
        payment_date__gte=start_date, payment_date__lte=today, status="posted"
    ).aggregate(
        receive_total=Sum(
            "amount",
            filter=Q(payment_type="receive"),
            default=Decimal("0"),
        ),
        pay_total=Sum(
            "amount",
            filter=Q(payment_type="pay"),
            default=Decimal("0"),
        ),
        tx_count=Count("id"),
    )

    receive_total = month_txs_agg["receive_total"] or Decimal("0")
    pay_total = month_txs_agg["pay_total"] or Decimal("0")
    tx_count = month_txs_agg["tx_count"]

    # Đảm bảo Decimal, fix trường hợp DB trả về None hoặc float
    receive_total = Decimal(str(receive_total)) if receive_total is not None else Decimal("0")
    pay_total = Decimal(str(pay_total)) if pay_total is not None else Decimal("0")

    net_cashflow = receive_total - pay_total

    summary = {
        "receive_total": f"{receive_total:.2f}",
        "pay_total": f"{pay_total:.2f}",
        "net_cashflow": f"{net_cashflow:.2f}",
        "tx_count": tx_count,
        "period_label": "4 tuần gần nhất",
    }

    current_week_monday = today - timedelta(days=today.weekday())
    chart_start_date = current_week_monday - timedelta(weeks=3)

    # 2. Weekly data - aggregate với Sum trước, KHÔNG cast float trong Python
    txs_agg = (
        CashFlowTransaction.objects.filter(payment_date__gte=chart_start_date, payment_date__lte=today, status="posted")
        .annotate(week=TruncWeek("payment_date"))
        .values("week", "payment_type")
        .annotate(total=Sum("amount"))
        .order_by("week")
    )

    weeks_data = {}
    for i in range(4):
        w_start_monday = current_week_monday - timedelta(weeks=3 - i)
        w_end_sunday = w_start_monday + timedelta(days=6)
        label = f"{w_start_monday.strftime('%d/%m')} - {w_end_sunday.strftime('%d/%m')}"
        weeks_data[w_start_monday] = {
            "week_label": label,
            "receive": Decimal("0"),
            "pay": Decimal("0"),
        }

    for t in txs_agg:
        w_date = t["week"]
        if w_date in weeks_data:
            ptype = t["payment_type"]
            total = t["total"] or Decimal("0")
            if not isinstance(total, Decimal):
                total = Decimal(str(total))
            if ptype == "receive":
                weeks_data[w_date]["receive"] = total
            elif ptype == "pay":
                weeks_data[w_date]["pay"] = total

    weeks_list = [
        {
            "week_label": w["week_label"],
            "receive": float(w["receive"]),
            "pay": float(w["pay"]),
        }
        for w in weeks_data.values()
    ]

    return {"summary": summary, "weeks": weeks_list}


# 16. finance_unpaid_purchase_invoices
def get_finance_unpaid_purchase_invoices():
    from django.db.models import Case, DecimalField, ExpressionWrapper, Value, When, fields

    today = timezone.localdate()
    invoices_qs = (
        PurchaseInvoice.objects.filter(status__in=[PurchaseInvoice.Status.UNPAID, PurchaseInvoice.Status.PARTIAL])
        .select_related("vendor")
        .annotate(
            remaining_amount=ExpressionWrapper(
                F("total_amount") - F("paid_amount"),
                output_field=DecimalField(max_digits=20, decimal_places=2),
            ),
            overdue_duration=Case(
                When(due_date__isnull=True, then=Value(timedelta(0))),
                When(due_date__gte=today, then=Value(timedelta(0))),
                default=ExpressionWrapper(Value(today) - F("due_date"), output_field=fields.DurationField()),
            ),
        )
        .filter(remaining_amount__gt=0)
        .order_by("-overdue_duration", "-remaining_amount")
    )

    fresh_sum = Decimal("0")
    fresh_count = 0
    aging_sum = Decimal("0")
    aging_count = 0
    overdue_sum = Decimal("0")
    overdue_count = 0
    critical_sum = Decimal("0")
    critical_count = 0

    top_overdue_list = []

    for i in invoices_qs:
        rem = i.remaining_amount
        overdue_days = i.overdue_duration.days

        if overdue_days <= 30:
            fresh_sum += rem
            fresh_count += 1
        elif overdue_days <= 60:
            aging_sum += rem
            aging_count += 1
        elif overdue_days <= 90:
            overdue_sum += rem
            overdue_count += 1
        else:
            critical_sum += rem
            critical_count += 1

        top_overdue_list.append(
            {
                "id": str(i.id),
                "supplier_name": i.vendor.supplier_name,
                "remaining_amount": f"{rem:.2f}",
                "due_date": i.due_date.isoformat() if i.due_date else None,
                "created_at": i.created_at.isoformat(),
                "overdue_days": overdue_days,
            }
        )

    total_outstanding = fresh_sum + aging_sum + overdue_sum + critical_sum
    total_count = invoices_qs.count()

    data_payload = {
        "buckets": [
            {"label": "0-30 ngày", "value": f"{fresh_sum:.2f}", "count": fresh_count, "color_key": "fresh"},
            {"label": "31-60 ngày", "value": f"{aging_sum:.2f}", "count": aging_count, "color_key": "aging"},
            {"label": "61-90 ngày", "value": f"{overdue_sum:.2f}", "count": overdue_count, "color_key": "overdue"},
            {"label": "> 90 ngày", "value": f"{critical_sum:.2f}", "count": critical_count, "color_key": "critical"},
        ],
        "total_outstanding": f"{total_outstanding:.2f}",
        "total_count": total_count,
        "top_overdue": top_overdue_list[:5],
    }
    return DashboardDict(data_payload, total_count)


# 17. finance_unpaid_sales_invoices
def get_finance_unpaid_sales_invoices():
    from django.db.models import Case, DecimalField, ExpressionWrapper, Value, When, fields
    from django.db.models.functions import TruncDate

    today = timezone.localdate()
    invoices_qs = (
        SalesInvoice.objects.filter(status__in=[SalesInvoice.Status.UNPAID, SalesInvoice.Status.PARTIAL])
        .select_related("customer")
        .annotate(
            remaining_amount=ExpressionWrapper(
                F("total_amount") - F("paid_amount"),
                output_field=DecimalField(max_digits=20, decimal_places=2),
            ),
            created_date=TruncDate("created_at"),
            overdue_duration=Case(
                When(created_date__gte=today, then=Value(timedelta(0))),
                default=ExpressionWrapper(Value(today) - F("created_date"), output_field=fields.DurationField()),
            ),
        )
        .filter(remaining_amount__gt=0)
        .order_by("-overdue_duration", "-remaining_amount")
    )

    fresh_sum = Decimal("0")
    fresh_count = 0
    aging_sum = Decimal("0")
    aging_count = 0
    overdue_sum = Decimal("0")
    overdue_count = 0
    critical_sum = Decimal("0")
    critical_count = 0

    top_overdue_list = []

    for i in invoices_qs:
        rem = i.remaining_amount
        overdue_days = i.overdue_duration.days

        if overdue_days <= 30:
            fresh_sum += rem
            fresh_count += 1
        elif overdue_days <= 60:
            aging_sum += rem
            aging_count += 1
        elif overdue_days <= 90:
            overdue_sum += rem
            overdue_count += 1
        else:
            critical_sum += rem
            critical_count += 1

        top_overdue_list.append(
            {
                "id": str(i.id),
                "customer_name": i.customer.customer_name,
                "remaining_amount": f"{rem:.2f}",
                "due_date": i.created_date.isoformat(),
                "created_at": i.created_at.isoformat(),
                "overdue_days": overdue_days,
            }
        )

    total_outstanding = fresh_sum + aging_sum + overdue_sum + critical_sum
    total_count = invoices_qs.count()

    data_payload = {
        "buckets": [
            {"label": "0-30 ngày", "value": f"{fresh_sum:.2f}", "count": fresh_count, "color_key": "fresh"},
            {"label": "31-60 ngày", "value": f"{aging_sum:.2f}", "count": aging_count, "color_key": "aging"},
            {"label": "61-90 ngày", "value": f"{overdue_sum:.2f}", "count": overdue_count, "color_key": "overdue"},
            {"label": "> 90 ngày", "value": f"{critical_sum:.2f}", "count": critical_count, "color_key": "critical"},
        ],
        "total_outstanding": f"{total_outstanding:.2f}",
        "total_count": total_count,
        "top_overdue": top_overdue_list[:5],
    }
    return DashboardDict(data_payload, total_count)


# 18. finance_depreciation_status (Khấu hao tài sản cố định)
def get_finance_depreciation_status():
    current_period = timezone.now().strftime("%Y-%m")

    depreciated_logs = FixedAssetDepreciationLog.objects.filter(period=current_period)
    depreciated_asset_ids = set(depreciated_logs.values_list("asset_id", flat=True))

    waiting_assets = FixedAsset.objects.filter(is_active=True, status="active", remaining_life_months__gt=0).exclude(
        id__in=depreciated_asset_ids
    )
    pending_assets_count = waiting_assets.count()
    is_done = pending_assets_count == 0

    from django.db.models import Prefetch

    from apps.master_data.models import WorkOrderFixedAsset

    all_assets = (
        FixedAsset.objects.filter(is_active=True)
        .prefetch_related(
            Prefetch(
                "work_order_links",
                queryset=WorkOrderFixedAsset.objects.only("id"),
            )
        )
        .order_by("-created_at")
    )
    total_count = all_assets.count()

    items_list = []
    for asset in all_assets:
        depreciable_value = asset.original_value - asset.salvage_value
        remaining = depreciable_value - asset.accumulated_depreciation
        if remaining < 0:
            remaining = Decimal("0.00")

        alerts = []
        if asset.status == "disposed":
            alerts.append(
                {
                    "category": "disposed",
                    "level": "normal",
                    "reason": f"Tài sản đã thanh lý vào ngày {asset.disposal_date.strftime('%d/%m/%Y') if asset.disposal_date else ''}.",
                }
            )
        else:
            if remaining <= Decimal("0.00"):
                alerts.append(
                    {"category": "fully_depreciated", "level": "critical", "reason": "Tài sản đã khấu hao hết giá trị."}
                )
            elif asset.remaining_life_months is not None and asset.remaining_life_months <= 2:
                alerts.append(
                    {
                        "category": "near_end",
                        "level": "warning",
                        "reason": f"Còn {asset.remaining_life_months} tháng là hết hạn sử dụng.",
                    }
                )

        items_list.append(
            {
                "id": str(asset.id),
                "asset_code": asset.asset_code,
                "asset_name": asset.asset_name,
                "depreciation_method": asset.depreciation_method,
                "original_value": f"{asset.original_value:.2f}",
                "salvage_value": f"{asset.salvage_value:.2f}",
                "accumulated_depreciation": f"{asset.accumulated_depreciation:.2f}",
                "remaining_value": f"{remaining:.2f}",
                "status": asset.status,
                "alerts": alerts,
            }
        )

    return {
        "items": items_list,
        "total_count": total_count,
        "current_period": current_period,
        "is_done": is_done,
        "depreciated_assets_count": len(depreciated_asset_ids),
        "pending_assets_count": pending_assets_count,
    }


# 19. hrm_payroll_lifecycle_status (Bảng lương nhân sự)
def get_hrm_payroll_lifecycle_status():
    from django.db.models import Count, Sum

    aggregates = (
        SalarySlip.objects.values("salary_period", "status")
        .annotate(count=Count("id"), total_net_pay=Sum("net_pay"))
        .order_by("-salary_period")
    )

    period_groups = {}
    for row in aggregates:
        period = row["salary_period"]
        if not period:
            continue
        if period not in period_groups:
            period_groups[period] = []
        period_groups[period].append(row)

    pending_periods = []
    status_weights = {"draft": 0, "calculated": 1, "pending_finance_review": 2, "approved": 3}
    status_labels = {
        "draft": "Bản nháp",
        "calculated": "Đã tính toán",
        "pending_finance_review": "Chờ phê duyệt",
        "approved": "Chờ thanh toán",
    }

    for period, rows in period_groups.items():
        statuses = {r["status"] for r in rows}

        if not statuses or (len(statuses) == 1 and "paid" in statuses):
            continue

        active_statuses = [s for s in statuses if s != "paid"]
        if not active_statuses:
            continue

        highest_status = max(active_statuses, key=lambda s: status_weights.get(s, -1))

        net_pay_total = sum(r["total_net_pay"] or Decimal("0") for r in rows)
        slip_count = sum(r["count"] for r in rows)

        pending_periods.append(
            {
                "id": period,
                "salary_period": period,
                "status": highest_status,
                "status_label": status_labels.get(highest_status, "Bản nháp"),
                "net_pay_total": f"{net_pay_total:.2f}",
                "slip_count": slip_count,
            }
        )

    # Sort:
    # 1. Sort by salary_period DESC
    pending_periods.sort(key=lambda x: x["salary_period"], reverse=True)
    # 2. Stable sort: approved status comes first
    pending_periods.sort(key=lambda x: 0 if x["status"] == "approved" else 1)

    return {
        "total_count": len(pending_periods),
        "top_items": pending_periods,
        "is_empty": len(pending_periods) == 0,
    }


# 20. hrm_pending_leave_requests
def get_hrm_pending_leave_requests():
    requests_qs = LeaveRequest.objects.filter(status="pending").select_related("employee").order_by("-created_at")
    total_count = requests_qs.count()
    results = [
        {
            "id": str(r.id),
            "employee_name": r.employee.full_name,
            "leave_type": r.get_leave_type_display(),
            "start_date": r.start_date.isoformat(),
            "end_date": r.end_date.isoformat(),
            "days": str(r.days),
            "created_at": r.created_at.isoformat(),
        }
        for r in requests_qs[:5]
    ]
    return {
        "total_count": total_count,
        "top_items": results,
    }


# 21. hrm_expiring_contracts
def get_hrm_expiring_contracts():
    from django.db.models import ExpressionWrapper, Value, fields

    today = timezone.localdate()
    thirty_days_later = today + timedelta(days=30)
    seven_days_later = today + timedelta(days=7)

    contracts_qs = (
        EmploymentContract.objects.filter(status="active", end_date__gte=today, end_date__lte=thirty_days_later)
        .select_related("employee")
        .annotate(days_left_dur=ExpressionWrapper(F("end_date") - Value(today), output_field=fields.DurationField()))
        .order_by("end_date")
    )
    expiring_count = contracts_qs.count()
    critical_count = contracts_qs.filter(end_date__lte=seven_days_later).count()

    top_items = []
    for c in contracts_qs[:5]:
        days_left = c.days_left_dur.days
        top_items.append(
            {
                "id": str(c.id),
                "employee_id": str(c.employee.id) if c.employee else None,
                "employee_name": c.employee.full_name,
                "contract_no": c.contract_no,
                "contract_type": c.get_contract_type_display(),
                "end_date": c.end_date.isoformat(),
                "days_left": days_left,
            }
        )

    return {
        "total_count": expiring_count,
        "top_items": top_items,
        "expiring_count": expiring_count,
        "critical_count": critical_count,
    }


# 23. hrm_today_attendance_rate (Nhân viên vắng mặt hôm nay)
def get_hrm_today_attendance_rate():
    today = timezone.localdate()
    total_active_employees = Employee.objects.filter(employment_status="active").count()
    working_count = Attendance.objects.filter(date=today, status="working").count()
    absent_count = total_active_employees - working_count

    if total_active_employees > 0:
        # Sử dụng Decimal để tránh floating point error
        attendance_rate = (Decimal(working_count) / Decimal(total_active_employees)) * Decimal("100")
        # Làm tròn 2 chữ số thập phân cho display
        attendance_rate = attendance_rate.quantize(Decimal("0.01"))
    else:
        attendance_rate = Decimal("100.00")

    return DashboardDict(
        {
            "attendance_rate": attendance_rate,
            "present_count": working_count,
            "absent_count": absent_count,
            "total_active_employees": total_active_employees,
        },
        total_active_employees,
    )


# 24. manufacturing_pending_wo_approval
def get_manufacturing_pending_wo_approval():
    orders_qs = WorkOrder.objects.filter(status="pending_approval")
    total_count = orders_qs.count()

    top_orders_qs = list(orders_qs.select_related("production_item__stock_uom").order_by("planned_start_date")[:5])

    top_items = []
    for wo in top_orders_qs:
        top_items.append(
            {
                "id": str(wo.id),
                "code": wo.name,
                "name": wo.name,
                "production_item_name": wo.production_item.item_name,
                "product_name": wo.production_item.item_name,
                "quantity": str(wo.quantity),
                "planned_start_date": wo.planned_start_date.isoformat() if wo.planned_start_date else None,
                "days_to_start": (wo.planned_start_date - timezone.localdate()).days if wo.planned_start_date else 0,
            }
        )

    return {
        "total_count": total_count,
        "top_items": top_items,
    }


# 25. manufacturing_active_wos
def get_manufacturing_active_wos():
    today = timezone.localdate()
    orders_qs = (
        WorkOrder.objects.filter(status="in_progress")
        .select_related("production_item", "target_warehouse")
        .order_by("-created_at")
    )
    total_count = orders_qs.count()
    results = []
    for o in orders_qs[:5]:
        qty = o.quantity
        prod = o.produced_qty
        pct = float((prod / qty) * 100) if qty > 0 else 0.0
        days_left = None
        if o.planned_end_date is not None:
            days_left = (o.planned_end_date - today).days
        results.append(
            {
                "id": str(o.id),
                "name": o.name,
                "production_item_name": o.production_item.item_name,
                "quantity": str(qty),
                "produced_qty": str(prod),
                "progress_pct": pct,
                "planned_start_date": o.planned_start_date.isoformat(),
                "planned_end_date": o.planned_end_date.isoformat() if o.planned_end_date else None,
                "days_left": days_left,
                "target_warehouse_name": o.target_warehouse.name if o.target_warehouse else None,
                "created_at": o.created_at.isoformat(),
            }
        )
    return DashboardList(results, total_count)


# 27. manufacturing_pending_completion
def get_manufacturing_pending_completion():
    orders_qs = WorkOrder.objects.filter(status="pending_production_complete").select_related(
        "production_item", "target_warehouse"
    )
    pending_completion_count = orders_qs.count()
    total_produced_qty = orders_qs.aggregate(total=Sum("produced_qty"))["total"] or Decimal("0")

    top_items = [
        {
            "id": str(wo.id),
            "name": wo.name,
            "production_item_name": wo.production_item.item_name,
            "quantity": str(wo.quantity),
            "produced_qty": str(wo.produced_qty),
            "target_warehouse_name": wo.target_warehouse.name if wo.target_warehouse else "Kho thành phẩm",
        }
        for wo in orders_qs[:5]
    ]

    return {
        "total_count": pending_completion_count,
        "top_items": top_items,
        "pending_completion_count": pending_completion_count,
        "total_produced_qty": f"{total_produced_qty:.2f}",
    }


def get_finance_pending_cashflow_approval():
    """
    Widget: Lệnh Duyệt Giao Dịch (CashFlow pending_approval).
    Tối ưu: chỉ lấy 5 dòng đầu, đếm tổng trong queryset count().

    PERFORMANCE NOTE:
    Đã select_related các FK sau: purchase_order, sales_order,
    purchase_invoice, sales_invoice, fixed_asset.
    Khi mở rộng payload, cần update select_related tương ứng để tránh N+1.
    Ví dụ: nếu cần tx.purchase_order.vendor.name, cần thêm "purchase_order__vendor".
    """
    qs = (
        CashFlowTransaction.objects.filter(status="pending_approval")
        .select_related(
            "purchase_order",
            "sales_order",
            "purchase_invoice",
            "sales_invoice",
            "fixed_asset",
        )
        .order_by("-payment_date", "-created_at", "id")
    )
    total_count = qs.count()
    items = [
        {
            "id": str(tx.id),
            "name": tx.name,
            "payment_type": tx.payment_type,
            "amount": str(tx.amount),
            "payment_date": tx.payment_date.isoformat() if tx.payment_date else None,
            "category": tx.category or "",
            "payment_method": tx.payment_method,
            "purchase_order_id": str(tx.purchase_order_id) if tx.purchase_order_id else None,
            "sales_order_id": str(tx.sales_order_id) if tx.sales_order_id else None,
            "fixed_asset_code": tx.fixed_asset.asset_code if tx.fixed_asset else None,
            "created_at": tx.created_at.isoformat(),
        }
        for tx in qs[:5]
    ]
    return {"total_count": total_count, "top_items": items}


# Map widget_code to selector function
SELECTORS_MAP = {
    "sales_today_revenue": get_sales_today_revenue,
    "sales_draft_orders": get_sales_draft_orders,
    "sales_pending_credit_bypass": get_sales_pending_credit_bypass,
    "sales_pending_fulfillment": get_sales_pending_fulfillment,
    "purchasing_active_po_count": get_purchasing_active_po_count,
    "purchasing_draft_orders": get_purchasing_draft_orders,
    "purchasing_pending_logistic_fees": get_purchasing_pending_logistic_fees,
    "purchasing_pending_approval_shipments": get_purchasing_pending_approval_shipments,
    "inventory_low_stock": get_warehouse_low_stock_alerts,
    "inventory_pending_entries": get_inventory_pending_entries,
    "finance_cashflow_overview": get_finance_cashflow_overview,
    "finance_unpaid_purchase_invoices": get_finance_unpaid_purchase_invoices,
    "finance_unpaid_sales_invoices": get_finance_unpaid_sales_invoices,
    "finance_depreciation_status": get_finance_depreciation_status,
    "hrm_payroll_lifecycle_status": get_hrm_payroll_lifecycle_status,
    "hrm_pending_leave_requests": get_hrm_pending_leave_requests,
    "hrm_expiring_contracts": get_hrm_expiring_contracts,
    "hrm_today_attendance_rate": get_hrm_today_attendance_rate,
    "manufacturing_pending_wo_approval": get_manufacturing_pending_wo_approval,
    "manufacturing_active_wos": get_manufacturing_active_wos,
    "manufacturing_pending_completion": get_manufacturing_pending_completion,
    "finance_pending_cashflow_approval": get_finance_pending_cashflow_approval,
}
