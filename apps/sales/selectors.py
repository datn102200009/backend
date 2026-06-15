import re
from datetime import timedelta
from decimal import Decimal

from django.db.models import Case, F, IntegerField, QuerySet, Sum, Value, When
from django.utils import timezone

from apps.crm.models import Customer
from apps.sales.models import SalesInvoice, SalesOrder


def sales_order_list() -> QuerySet:
    """
    Returns a queryset of SalesOrder, optimized with select_related.
    Sắp xếp theo độ ưu tiên trạng thái:
    1. pending
    2. pending_credit_approval
    3. paid_unshipped
    4. shipped_unpaid
    5. cancel_pending
    6. draft
    7. completed
    8. cancelled
    Sau đó sắp xếp theo -created_at, id.
    """
    return (
        SalesOrder.objects.select_related("customer")
        .annotate(
            status_priority=Case(
                When(status="pending", then=Value(1)),
                When(status="pending_credit_approval", then=Value(2)),
                When(status="paid_unshipped", then=Value(3)),
                When(status="shipped_unpaid", then=Value(4)),
                When(status="cancel_pending", then=Value(5)),
                When(status="draft", then=Value(6)),
                When(status="completed", then=Value(7)),
                default=Value(8),
                output_field=IntegerField(),
            )
        )
        .order_by("status_priority", "-created_at", "id")
    )


def sales_order_detail(*, order_id: str) -> SalesOrder:
    """
    Returns a single SalesOrder instance, optimized with related lines.
    """
    return SalesOrder.objects.select_related("customer").prefetch_related("lines__item").get(id=order_id)


def parse_payment_terms_to_days(payment_terms: str) -> int:
    """
    Phân tích chuỗi điều khoản thanh toán (ví dụ: "NET30", "NET45", "30") để lấy số ngày thanh toán.
    Mặc định trả về 30 ngày nếu rỗng hoặc phân tích thất bại.
    """
    if not payment_terms:
        return 30
    match = re.search(r"\d+", payment_terms)
    if match:
        return int(match.group())
    return 30


def get_customer_current_debt(customer_id: str) -> Decimal:
    """
    Tính tổng nợ phải thu hiện tại của khách hàng dựa trên các hóa đơn chưa thanh toán đầy đủ (UNPAID hoặc PARTIAL).
    Sử dụng aggregate để tối ưu hóa truy vấn khi dữ liệu lớn.
    """
    result = SalesInvoice.objects.filter(
        customer_id=customer_id, status__in=[SalesInvoice.Status.UNPAID, SalesInvoice.Status.PARTIAL]
    ).aggregate(net_debt=Sum(F("total_amount") - F("paid_amount")))
    return result["net_debt"] or Decimal("0.00")


def check_customer_overdue_debts(customer_id: str, max_days: int = 30) -> bool:
    """
    Kiểm tra xem khách hàng có bất kỳ hóa đơn nào đã quá hạn quá max_days ngày (kể từ ngày đến hạn) hay không.
    Sử dụng filter và exists() để tối ưu hiệu năng đối với cơ sở dữ liệu lớn.
    """
    customer = Customer.objects.filter(id=customer_id).first()
    if not customer:
        return False

    payment_terms_days = parse_payment_terms_to_days(customer.payment_terms)
    # cutoff_date = timezone.now() - (payment_terms_days + max_days)
    cutoff_date = timezone.now() - timedelta(days=payment_terms_days + max_days)
    return SalesInvoice.objects.filter(
        customer_id=customer_id,
        status__in=[SalesInvoice.Status.UNPAID, SalesInvoice.Status.PARTIAL],
        created_at__lt=cutoff_date,
    ).exists()
