"""
Selectors for inventory app.

All read operations and complex queries should be defined here.
Always optimize with select_related() and prefetch_related() to avoid N+1 queries.
"""

from decimal import Decimal
from typing import List, Optional

from django.db.models import Q, QuerySet, Sum

from apps.inventory.models import StockEntry, StockEntryDetail, StockLedger
from apps.master_data.models import BOM, Item, Warehouse

# ======================== Stock Entry Queries ========================


def stock_entry_list_by_status(
    status: str,
    purpose: Optional[str] = None,
) -> QuerySet:
    """
    Lấy danh sách phiếu stock entry theo trạng thái.

    Args:
        status: Trạng thái (draft, submitted, posted)
        purpose: Mục đích (receipt, issue, transfer, etc.) - optional

    Returns:
        Optimized QuerySet

    Ví dụ:
        stock_entry_list_by_status("draft", purpose="receipt")
    """
    qs = (
        StockEntry.objects.select_related(
            # Có thể thêm if cần
        )
        .prefetch_related(
            "details__item",
            "details__source_warehouse",
            "details__target_warehouse",
        )
        .filter(status=status)
    )

    if purpose:
        qs = qs.filter(purpose=purpose)

    return qs.order_by("-created_at")


def stock_entry_detail_list(stock_entry_id: str) -> QuerySet:
    """
    Lấy danh sách chi tiết của một phiếu stock entry.

    Args:
        stock_entry_id: ID của stock entry

    Returns:
        Optimized QuerySet
    """
    return StockEntryDetail.objects.select_related(
        "item",
        "source_warehouse",
        "target_warehouse",
    ).filter(parent_id=stock_entry_id)


# ======================== Stock Ledger Queries ========================


def stock_ledger_balance_by_item_warehouse(
    item: Item,
    warehouse: Warehouse,
) -> Decimal:
    """
    Tính tồn kho hiện tại của một item trong một warehouse.

    Args:
        item: Item object
        warehouse: Warehouse object

    Returns:
        Số lượng tồn kho

    Ví dụ:
        balance = stock_ledger_balance_by_item_warehouse(item, warehouse)
    """
    result = StockLedger.objects.filter(
        item=item,
        warehouse=warehouse,
    ).aggregate(balance=Sum("actual_quantity"))

    return result["balance"] or Decimal("0.00")


def stock_ledger_balance_by_warehouse(
    warehouse: Warehouse,
) -> QuerySet:
    """
    Lấy tồn kho của tất cả items trong một warehouse.

    Args:
        warehouse: Warehouse object

    Returns:
        QuerySet với balance cho từng item
    """
    from django.db import models as django_models
    from django.db.models import F
    from django.db.models.functions import Cast

    return (
        StockLedger.objects.filter(
            warehouse=warehouse,
        )
        .annotate(
            item_code=F("item__item_code"),
            item_name=F("item__item_name"),
            uom=F("item__stock_uom__name"),
        )
        .values(
            "item_id",
            "item_code",
            "item_name",
            "uom",
        )
        .annotate(
            total_quantity=Sum("actual_quantity"),
        )
        .filter(
            total_quantity__gt=0,
        )
    )


def stock_ledger_list_by_item(item: Item) -> QuerySet:
    """
    Lấy lịch sử giao dịch của một item.

    Args:
        item: Item object

    Returns:
        Optimized QuerySet
    """
    return (
        StockLedger.objects.select_related(
            "warehouse",
        )
        .filter(
            item=item,
        )
        .order_by("-posting_date")
    )


def stock_ledger_list_by_warehouse(warehouse: Warehouse) -> QuerySet:
    """
    Lấy lịch sử giao dịch của một warehouse.

    Args:
        warehouse: Warehouse object

    Returns:
        Optimized QuerySet
    """
    return (
        StockLedger.objects.select_related(
            "item",
        )
        .filter(
            warehouse=warehouse,
        )
        .order_by("-posting_date")
    )


# ======================== Stock Analysis ========================


def stock_analysis_by_warehouse(warehouse_id: str) -> QuerySet:
    """
    Phân tích tồn kho theo warehouse (tính tồn kho đơn vị, doanh số, etc.).

    Args:
        warehouse_id: ID của warehouse

    Returns:
        QuerySet với chi tiết phân tích
    """
    return (
        StockLedger.objects.filter(
            warehouse_id=warehouse_id,
        )
        .select_related(
            "item",
        )
        .values(
            "item__id",
            "item__item_code",
            "item__item_name",
        )
        .annotate(
            total_quantity=Sum("actual_quantity"),
        )
        .order_by("-total_quantity")
    )


def stock_analysis_by_item(item_id: str) -> QuerySet:
    """
    Phân tích tồn kho theo item (tìm item đó ở những warehouse nào).

    Args:
        item_id: ID của item

    Returns:
        QuerySet với chi tiết tồn kho
    """
    return (
        StockLedger.objects.filter(
            item_id=item_id,
        )
        .select_related(
            "warehouse",
        )
        .values(
            "warehouse__id",
            "warehouse__name",
        )
        .annotate(
            total_quantity=Sum("actual_quantity"),
        )
        .filter(
            total_quantity__gt=0,
        )
        .order_by("-total_quantity")
    )


# ======================== Item Management Queries ========================


def item_list_active() -> QuerySet:
    """
    Lấy danh sách tất cả sản phẩm đang hoạt động.

    Returns:
        Optimized QuerySet
    """
    return (
        Item.objects.select_related(
            "item_group",
            "stock_uom",
        )
        .filter(
            status="active",
            is_active=True,
        )
        .order_by("item_code")
    )


def item_list_by_group(item_group_id: str) -> QuerySet:
    """
    Lấy danh sách sản phẩm theo nhóm.

    Args:
        item_group_id: ID của item group

    Returns:
        Optimized QuerySet
    """
    return (
        Item.objects.select_related(
            "item_group",
            "stock_uom",
        )
        .filter(
            item_group_id=item_group_id,
            status="active",
            is_active=True,
        )
        .order_by("item_code")
    )


def item_search(search_term: str) -> QuerySet:
    """
    Tìm kiếm sản phẩm theo item_code hoặc item_name.

    Args:
        search_term: Từ khóa tìm kiếm

    Returns:
        Optimized QuerySet
    """
    return (
        Item.objects.select_related(
            "item_group",
            "stock_uom",
        )
        .filter(
            Q(item_code__icontains=search_term) | Q(item_name__icontains=search_term),
            status="active",
            is_active=True,
        )
        .order_by("item_code")
    )


def item_check_duplicate_code(item_code: str, exclude_id: Optional[str] = None) -> bool:
    """
    Kiểm tra xem item_code đã tồn tại hay không.

    Args:
        item_code: Mã sản phẩm
        exclude_id: ID để loại trừ (khi cập nhật)

    Returns:
        True nếu đã tồn tại, False nếu không
    """
    qs = Item.objects.filter(item_code=item_code)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    return qs.exists()


# ======================== BOM Queries ========================


def bom_list_active() -> QuerySet:
    """
    Lấy danh sách tất cả BOM đang hoạt động.

    Returns:
        Optimized QuerySet
    """
    return (
        BOM.objects.select_related(
            "item",
        )
        .prefetch_related(
            "items__item",
            "items__uom",
        )
        .filter(
            status="active",
            is_active=True,
        )
        .order_by("name")
    )


def bom_by_item(item_id: str) -> QuerySet:
    """
    Lấy BOM của một sản phẩm.

    Args:
        item_id: ID của item

    Returns:
        Optimized QuerySet
    """
    return (
        BOM.objects.select_related(
            "item",
        )
        .prefetch_related(
            "items__item",
            "items__uom",
        )
        .filter(
            item_id=item_id,
            status="active",
            is_active=True,
        )
    )


# ======================== Stock Validation ========================


def check_insufficient_stock_for_issue(
    item: Item,
    warehouse: Warehouse,
    required_qty: Decimal,
) -> bool:
    """
    Kiểm tra xem tồn kho có đủ để xuất hay không.

    Args:
        item: Item object
        warehouse: Warehouse object
        required_qty: Số lượng cần xuất

    Returns:
        True nếu không đủ, False nếu đủ
    """
    from apps.inventory.services import _get_available_stock

    available = _get_available_stock(item, warehouse)
    return available < required_qty
