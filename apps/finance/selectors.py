"""
Selectors for finance app.

All read operations and complex queries should be defined here.
Always optimize with select_related() and prefetch_related() to avoid N+1 queries.
"""

from django.db.models import QuerySet

from apps.finance.models import CashFlowTransaction, FixedAsset, FixedAssetDepreciationLog


def cash_flow_list() -> QuerySet:
    """
    Returns a queryset of CashFlowTransaction, optimized with select_related.
    """
    return CashFlowTransaction.objects.select_related(
        "purchase_order", "sales_order", "purchase_invoice", "sales_invoice"
    ).order_by("-payment_date", "-created_at", "id")


def cash_flow_detail(*, transaction_id: str) -> CashFlowTransaction:
    """
    Returns a single CashFlowTransaction instance.
    """
    return CashFlowTransaction.objects.select_related(
        "purchase_order", "sales_order", "purchase_invoice", "sales_invoice"
    ).get(id=transaction_id)


def fixed_asset_list() -> QuerySet:
    """
    Returns a queryset of FixedAsset, ordered by creation date.
    """
    return FixedAsset.objects.all().order_by("-created_at")


def fixed_asset_detail(*, asset_id: str) -> FixedAsset:
    """
    Returns a single FixedAsset instance.
    """
    return FixedAsset.objects.prefetch_related("depreciation_logs").get(id=asset_id)


def depreciation_log_list(*, period: str = None, asset_id: str = None) -> QuerySet:
    """
    Returns a queryset of FixedAssetDepreciationLog, filtered by period or asset.
    """
    qs = FixedAssetDepreciationLog.objects.select_related("asset")
    if period:
        qs = qs.filter(period=period)
    if asset_id:
        qs = qs.filter(asset_id=asset_id)
    return qs.order_by("-created_at", "id")
