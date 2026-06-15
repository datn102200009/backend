"""
Selectors for finance app.

All read operations and complex queries should be defined here.
Always optimize with select_related() and prefetch_related() to avoid N+1 queries.

ARCHITECTURE NOTE (2026-06):
PurchaseInvoice và SalesInvoice vẫn được định nghĩa ở apps.purchasing.models và
apps.sales.models (tương ứng) do các ràng buộc FK với PurchaseOrder/SalesOrder
và các business rule nghiệp vụ mua/bán. apps/finance đóng vai trò "shell"
(cung cấp selectors, serializers, services cho view CashFlow/Reporting) và
import model từ purchasing/sales theo quy ước một chiều:
    purchasing/sales (data) -> finance (shell)
KHÔNG được import ngược lại từ finance vào purchasing/sales để tránh vòng phụ thuộc.
Khi schema PurchaseInvoice/SalesInvoice thay đổi, cần đồng bộ serializers/selectors
tại finance tương ứng.
"""

from django.db.models import Case, IntegerField, QuerySet, Value, When

from apps.finance.models import CashFlowTransaction, FixedAsset, FixedAssetDepreciationLog
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice


def cash_flow_list(*, status: str = None) -> QuerySet:
    """
    Returns a queryset of CashFlowTransaction, optimized with select_related.
    """
    qs = CashFlowTransaction.objects.select_related(
        "purchase_order", "sales_order", "purchase_invoice", "sales_invoice"
    )
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("-payment_date", "-created_at", "id")


def cash_flow_detail(*, transaction_id: str) -> CashFlowTransaction:
    """
    Returns a single CashFlowTransaction instance.
    """
    return CashFlowTransaction.objects.select_related(
        "purchase_order", "sales_order", "purchase_invoice", "sales_invoice"
    ).get(id=transaction_id)


def fixed_asset_list(*, status_filter: list[str] | None = None, depreciation_method: str | None = None) -> QuerySet:
    """
    Returns a queryset of FixedAsset.
    - status priority order: pending_receive (1) -> pending_dispose (2) -> idle (3) -> active (4) -> disposed (5)
    - then -updated_at
    - status_filter: optional list of statuses to include
    - depreciation_method: optional depreciation method to filter
    """
    qs = FixedAsset.objects.all()

    if status_filter:
        qs = qs.filter(status__in=status_filter)

    if depreciation_method:
        qs = qs.filter(depreciation_method=depreciation_method)

    qs = qs.annotate(
        status_priority=Case(
            When(status="pending_receive", then=Value(1)),
            When(status="pending_dispose", then=Value(2)),
            When(status="idle", then=Value(3)),
            When(status="active", then=Value(4)),
            When(status="disposed", then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )
    ).order_by("status_priority", "-updated_at")

    return qs


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


def sales_invoice_list() -> QuerySet:
    """Di chuyển từ apps.sales.selectors."""
    from apps.sales.models import SalesInvoice

    return (
        SalesInvoice.objects.select_related("customer", "order")
        .annotate(
            status_priority=Case(
                When(status="unpaid", then=Value(1)),
                When(status="partial", then=Value(2)),
                When(status="paid", then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        )
        .order_by("status_priority", "-created_at", "id")
    )


def sales_invoice_detail(*, invoice_id: str) -> SalesInvoice:
    """Di chuyển từ apps.sales.selectors."""
    from apps.sales.models import SalesInvoice

    return SalesInvoice.objects.select_related("customer", "order").prefetch_related("lines__item").get(id=invoice_id)


def purchase_invoice_list() -> QuerySet:
    """Di chuyển từ apps.purchasing.selectors."""
    from apps.purchasing.models import PurchaseInvoice

    return (
        PurchaseInvoice.objects.select_related("vendor", "order")
        .annotate(
            status_priority=Case(
                When(status="unpaid", then=Value(1)),
                When(status="partial", then=Value(2)),
                When(status="paid", then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        )
        .order_by("status_priority", "-created_at", "id")
    )


def purchase_invoice_detail(*, invoice_id: str) -> PurchaseInvoice:
    """Di chuyển từ apps.purchasing.selectors."""
    from apps.purchasing.models import PurchaseInvoice

    return PurchaseInvoice.objects.select_related("vendor", "order").prefetch_related("lines__item").get(id=invoice_id)
