from django.db.models import QuerySet

from apps.purchasing.models import PurchaseInvoice, PurchaseOrder


def purchase_order_list() -> QuerySet:
    """
    Returns a queryset of PurchaseOrder, optimized with select_related.
    """
    return PurchaseOrder.objects.select_related("vendor").order_by("-created_at")


def purchase_order_detail(*, order_id: str) -> PurchaseOrder:
    """
    Returns a single PurchaseOrder instance, optimized with related lines.
    """
    return PurchaseOrder.objects.select_related("vendor").prefetch_related("lines__item").get(id=order_id)


def purchase_invoice_list() -> QuerySet:
    """
    Returns a queryset of PurchaseInvoice, optimized with select_related.
    """
    return PurchaseInvoice.objects.select_related("vendor", "order").order_by("-created_at")


def purchase_invoice_detail(*, invoice_id: str) -> PurchaseInvoice:
    """
    Returns a single PurchaseInvoice instance, optimized with related lines.
    """
    return PurchaseInvoice.objects.select_related("vendor", "order").prefetch_related("lines__item").get(id=invoice_id)
