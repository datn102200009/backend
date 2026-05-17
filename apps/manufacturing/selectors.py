"""
Selectors for manufacturing app.

All read operations and complex queries should be defined here.
Always optimize with select_related() and prefetch_related() to avoid N+1 queries.
"""

from decimal import Decimal
from typing import Optional

from django.db.models import Q, QuerySet, Sum

from apps.inventory.models import StockLedger
from apps.master_data.models import BOM, WorkOrder

# ======================== BOM Selectors ========================


def bom_list(
    *,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> QuerySet:
    """
    Lấy danh sách BOM với filter và search.

    Args:
        search: Tìm kiếm theo tên BOM hoặc mã sản phẩm
        is_active: Lọc theo trạng thái hoạt động

    Returns:
        Optimized QuerySet
    """
    qs = BOM.objects.select_related("item").prefetch_related("items__item").order_by("-created_at")

    if is_active is not None:
        qs = qs.filter(is_active=is_active)

    if search:
        qs = qs.filter(
            Q(name__icontains=search) | Q(item__item_code__icontains=search) | Q(item__item_name__icontains=search)
        )

    return qs


def bom_detail(*, bom_id: str) -> Optional[BOM]:
    """
    Lấy chi tiết một BOM kèm danh sách linh kiện.

    Args:
        bom_id: ID của BOM

    Returns:
        BOM object hoặc None
    """
    return (
        BOM.objects.select_related("item", "item__stock_uom").prefetch_related("items__item").filter(id=bom_id).first()
    )


# ======================== Work Order Selectors ========================


def work_order_list(
    *,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> QuerySet:
    """
    Lấy danh sách Work Order với filter.

    Args:
        status: Lọc theo trạng thái (draft, released, started, completed, cancelled)
        search: Tìm kiếm theo tên WO hoặc mã sản phẩm

    Returns:
        Optimized QuerySet
    """
    qs = WorkOrder.objects.select_related(
        "bom",
        "production_item",
    ).order_by("-created_at")

    if status:
        qs = qs.filter(status=status)

    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(production_item__item_code__icontains=search)
            | Q(production_item__item_name__icontains=search)
        )

    return qs


def work_order_detail(*, work_order_id: str) -> Optional[WorkOrder]:
    """
    Lấy chi tiết một Work Order.

    Args:
        work_order_id: ID của Work Order

    Returns:
        WorkOrder object hoặc None
    """
    return (
        WorkOrder.objects.select_related(
            "bom",
            "bom__item",
            "production_item",
        )
        .filter(id=work_order_id)
        .first()
    )


def get_material_preview(*, bom_id: str, quantity: int, source_warehouse_id: str) -> list[dict]:
    """
    Tính toán nguyên liệu cần thiết và kiểm tra tồn kho.

    Args:
        bom_id: ID của BOM
        quantity: Số lượng sản phẩm cần sản xuất
        source_warehouse_id: ID của kho nguồn

    Returns:
        List các dictionary chứa thông tin nguyên liệu và số lượng thiếu (nếu có).
    """
    bom = bom_detail(bom_id=bom_id)
    if not bom:
        return []

    item_ids = [item.item_id for item in bom.items.all()]

    # Lấy tồn kho hiện tại
    stock_balances = (
        StockLedger.objects.filter(
            warehouse_id=source_warehouse_id,
            item_id__in=item_ids,
        )
        .values("item_id")
        .annotate(total_qty=Sum("actual_quantity"))
    )

    balance_map = {str(item["item_id"]): item["total_qty"] or Decimal("0.0") for item in stock_balances}

    preview = []
    for bom_item in bom.items.all():
        required_qty = bom_item.quantity * Decimal(str(quantity))
        available_qty = balance_map.get(str(bom_item.item_id), Decimal("0.0"))
        missing_qty = max(Decimal("0.0"), required_qty - available_qty)

        preview.append(
            {
                "item_id": str(bom_item.item_id),
                "item_code": bom_item.item.item_code,
                "item_name": bom_item.item.item_name,
                "required_qty": float(required_qty),
                "available_qty": float(available_qty),
                "missing_qty": float(missing_qty),
            }
        )

    return preview
