import pytest

from apps.finance.selectors import sales_invoice_list
from apps.sales.selectors import sales_order_list
from apps.sales.tests.factories import SalesInvoiceFactory, SalesOrderFactory

pytestmark = pytest.mark.django_db


class TestSalesSelectors:
    def test_sales_order_list(self):
        SalesOrderFactory.create_batch(3)
        orders = sales_order_list()
        assert orders.count() == 3

    def test_sales_order_list_sorting(self):
        from django.utils import timezone

        from apps.sales.models import SalesOrder

        # 1. pending
        # 2. pending_credit_approval
        # 3. paid_unshipped
        # 4. shipped_unpaid
        # 5. cancel_pending
        # 6. draft
        # 7. completed
        # 8. cancelled
        so_cancelled = SalesOrderFactory(status=SalesOrder.Status.CANCELLED)
        so_completed = SalesOrderFactory(status=SalesOrder.Status.COMPLETED)
        so_draft = SalesOrderFactory(status=SalesOrder.Status.DRAFT)
        so_cancel_pending = SalesOrderFactory(status=SalesOrder.Status.CANCEL_PENDING)
        so_shipped_unpaid = SalesOrderFactory(status=SalesOrder.Status.SHIPPED_UNPAID)
        so_paid_unshipped = SalesOrderFactory(status=SalesOrder.Status.PAID_UNSHIPPED)
        so_pending_credit = SalesOrderFactory(status=SalesOrder.Status.PENDING_CREDIT_APPROVAL)
        so_pending = SalesOrderFactory(status=SalesOrder.Status.PENDING)

        results = list(sales_order_list())
        so_ids = [so.id for so in results]

        assert so_ids == [
            so_pending.id,
            so_pending_credit.id,
            so_paid_unshipped.id,
            so_shipped_unpaid.id,
            so_cancel_pending.id,
            so_draft.id,
            so_completed.id,
            so_cancelled.id,
        ]

        # Kiểm tra sắp xếp thứ cấp: cùng trạng thái sắp xếp theo -created_at, sau đó là id.
        now = timezone.now()
        SalesOrder.objects.filter(id=so_pending.id).update(created_at=now - timezone.timedelta(days=2))

        so_pending_new = SalesOrderFactory(status=SalesOrder.Status.PENDING)
        SalesOrder.objects.filter(id=so_pending_new.id).update(created_at=now)

        results2 = list(sales_order_list())
        pending_ids = [so.id for so in results2 if so.status == SalesOrder.Status.PENDING]
        assert pending_ids == [so_pending_new.id, so_pending.id]

    def test_sales_invoice_list(self):
        SalesInvoiceFactory.create_batch(2)
        invoices = sales_invoice_list()
        assert invoices.count() == 2
