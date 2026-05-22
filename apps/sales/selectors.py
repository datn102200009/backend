from django.db.models import QuerySet

from apps.sales.models import SalesInvoice, SalesOrder


def sales_order_list() -> QuerySet:
    """
    Returns a queryset of SalesOrder, optimized with select_related.
    """
    return SalesOrder.objects.select_related("customer").order_by("-created_at")


def sales_order_detail(*, order_id: str) -> SalesOrder:
    """
    Returns a single SalesOrder instance, optimized with related lines.
    """
    return SalesOrder.objects.select_related("customer").prefetch_related("lines__item").get(id=order_id)


def sales_invoice_list() -> QuerySet:
    """
    Returns a queryset of SalesInvoice, optimized with select_related.
    """
    return SalesInvoice.objects.select_related("customer", "order").order_by("-created_at")


def sales_invoice_detail(*, invoice_id: str) -> SalesInvoice:
    """
    Returns a single SalesInvoice instance, optimized with related lines.
    """
    return SalesInvoice.objects.select_related("customer", "order").prefetch_related("lines__item").get(id=invoice_id)
