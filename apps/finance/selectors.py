"""
Selectors for finance app.

All read operations and complex queries should be defined here.
Always optimize with select_related() and prefetch_related() to avoid N+1 queries.
"""

from django.db.models import QuerySet

from apps.finance.models import CashFlowTransaction


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
