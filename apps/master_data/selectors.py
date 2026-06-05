"""
Selectors for master_data app.

All read operations and complex queries should be defined here.
Always optimize with select_related() and prefetch_related() to avoid N+1 queries.
"""

from typing import Optional

from django.db.models import Q, QuerySet

from apps.master_data.models import UOM, Item, Warehouse


def uom_list() -> QuerySet[UOM]:
    return UOM.objects.all().order_by("name")


def warehouse_list() -> QuerySet[Warehouse]:
    return Warehouse.objects.all().order_by("name")


def item_list(*, search: Optional[str] = None, status: Optional[str] = None) -> QuerySet[Item]:
    """
    Get a list of items with optional filtering.
    Optimized with select_related for item_group and stock_uom.
    """
    qs = Item.objects.select_related("item_group", "stock_uom").order_by("-created_at", "id")

    if search:
        qs = qs.filter(Q(item_code__icontains=search) | Q(item_name__icontains=search))

    if status:
        qs = qs.filter(status=status)

    return qs


def item_get_detail(*, item_code: str) -> Item:
    """
    Get a single item by item_code.
    """
    return Item.objects.select_related("item_group", "stock_uom").get(item_code=item_code)
