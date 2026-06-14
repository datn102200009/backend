from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import QuerySet

from apps.purchasing.models import PurchaseInvoice, PurchaseOrder


def purchase_order_list() -> QuerySet:
    """
    Returns a queryset of PurchaseOrder, optimized with select_related.
    """
    return (
        PurchaseOrder.objects.select_related("vendor")
        .prefetch_related("invoices", "stock_entries")
        .order_by("-created_at", "id")
    )


def purchase_order_detail(*, order_id: str) -> PurchaseOrder:
    """
    Returns a single PurchaseOrder instance, optimized with related lines, invoices, stock_entries.
    """
    return (
        PurchaseOrder.objects.select_related("vendor")
        .prefetch_related(
            "lines__item",
            "lines__item__stock_uom",
            "invoices",
            "stock_entries",
            "stock_entries__details",
            "stock_entries__details__item",
            "stock_entries__details__target_warehouse",
            "shipments__stock_entries",
        )
        .get(id=order_id)
    )


def get_supplier_ap_aging(*, supplier_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Tính tuổi nợ AP của các nhà cung cấp sử dụng gom nhóm ở mức Database.
    Tránh load dữ liệu lớn lên memory Python.
    """
    import datetime

    from django.db.models import Case, DecimalField, F, Sum, Value, When
    from django.utils import timezone

    today = timezone.now().date()

    qs = PurchaseInvoice.objects.filter(
        status__in=[
            PurchaseInvoice.Status.UNPAID,
            PurchaseInvoice.Status.PARTIAL,
        ]
    )
    if supplier_id:
        qs = qs.filter(vendor_id=supplier_id)

    limit_30_days = today - datetime.timedelta(days=30)

    # Biểu thức tính nợ theo từng bracket
    not_due_expr = Case(
        When(due_date__isnull=True, then=F("total_amount") - F("paid_amount")),
        When(due_date__gte=today, then=F("total_amount") - F("paid_amount")),
        default=Value(0),
        output_field=DecimalField(max_digits=15, decimal_places=2),
    )

    overdue_1_30_expr = Case(
        When(due_date__lt=today, due_date__gte=limit_30_days, then=F("total_amount") - F("paid_amount")),
        default=Value(0),
        output_field=DecimalField(max_digits=15, decimal_places=2),
    )

    overdue_above_30_expr = Case(
        When(due_date__lt=limit_30_days, then=F("total_amount") - F("paid_amount")),
        default=Value(0),
        output_field=DecimalField(max_digits=15, decimal_places=2),
    )

    report = (
        qs.values("vendor_id", "vendor__name", "vendor__supplier_name")
        .annotate(
            total_unpaid=Sum(
                F("total_amount") - F("paid_amount"), output_field=DecimalField(max_digits=15, decimal_places=2)
            ),
            not_due=Sum(not_due_expr, output_field=DecimalField(max_digits=15, decimal_places=2)),
            overdue_1_30=Sum(overdue_1_30_expr, output_field=DecimalField(max_digits=15, decimal_places=2)),
            overdue_above_30=Sum(overdue_above_30_expr, output_field=DecimalField(max_digits=15, decimal_places=2)),
        )
        .order_by("vendor__supplier_name")
    )

    # Convert to list and clean decimals/floats for JSON response
    result = []
    for item in report:
        result.append(
            {
                "vendor_id": str(item["vendor_id"]),
                "vendor_code": item["vendor__name"],
                "vendor_name": item["vendor__supplier_name"],
                "total_unpaid": item["total_unpaid"] or Decimal("0.00"),
                "not_due": item["not_due"] or Decimal("0.00"),
                "overdue_1_30": item["overdue_1_30"] or Decimal("0.00"),
                "overdue_above_30": item["overdue_above_30"] or Decimal("0.00"),
            }
        )
    return result
