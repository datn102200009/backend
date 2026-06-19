import pytest

from apps.finance.selectors import cash_flow_list
from apps.finance.tests.factories import CashFlowTransactionFactory

pytestmark = pytest.mark.django_db


class TestFinanceSelectors:
    def test_cash_flow_list(self):
        CashFlowTransactionFactory.create_batch(3)
        transactions = cash_flow_list()
        assert transactions.count() == 3

    def test_invoice_selectors_integration(self):
        """Smoke test: finance selectors có thể import và resolve PurchaseInvoice/SalesInvoice."""
        from apps.finance.selectors import purchase_invoice_list, sales_invoice_list

        assert callable(purchase_invoice_list)
        assert callable(sales_invoice_list)
        assert purchase_invoice_list().model.__name__ == "PurchaseInvoice"
        assert sales_invoice_list().model.__name__ == "SalesInvoice"

    def test_sales_invoice_list_sorting(self):
        from django.utils import timezone

        from apps.finance.selectors import sales_invoice_list
        from apps.sales.models import SalesInvoice
        from apps.sales.tests.factories import SalesInvoiceFactory

        # Status: unpaid (1) -> partial (2) -> paid (3) -> cancelled (4)
        inv_cancelled = SalesInvoiceFactory(status=SalesInvoice.Status.CANCELLED)
        inv_paid = SalesInvoiceFactory(status=SalesInvoice.Status.PAID)
        inv_partial = SalesInvoiceFactory(status=SalesInvoice.Status.PARTIAL)
        inv_unpaid = SalesInvoiceFactory(status=SalesInvoice.Status.UNPAID)

        results = list(sales_invoice_list())
        inv_ids = [inv.id for inv in results]

        assert inv_ids == [
            inv_unpaid.id,
            inv_partial.id,
            inv_paid.id,
            inv_cancelled.id,
        ]

        # Kiểm tra sắp xếp thứ cấp: cùng trạng thái sắp xếp theo -created_at, sau đó là id.
        now = timezone.now()
        SalesInvoice.objects.filter(id=inv_unpaid.id).update(created_at=now - timezone.timedelta(days=2))

        inv_unpaid_new = SalesInvoiceFactory(status=SalesInvoice.Status.UNPAID)
        SalesInvoice.objects.filter(id=inv_unpaid_new.id).update(created_at=now)

        results2 = list(sales_invoice_list())
        unpaid_ids = [inv.id for inv in results2 if inv.status == SalesInvoice.Status.UNPAID]
        assert unpaid_ids == [inv_unpaid_new.id, inv_unpaid.id]

    def test_purchase_invoice_list_sorting(self):
        from django.utils import timezone

        from apps.finance.selectors import purchase_invoice_list
        from apps.purchasing.models import PurchaseInvoice
        from apps.purchasing.tests.factories import PurchaseInvoiceFactory

        # Status: unpaid (1) -> partial (2) -> paid (3) -> cancelled (4)
        inv_cancelled = PurchaseInvoiceFactory(status=PurchaseInvoice.Status.CANCELLED)
        inv_paid = PurchaseInvoiceFactory(status=PurchaseInvoice.Status.PAID)
        inv_partial = PurchaseInvoiceFactory(status=PurchaseInvoice.Status.PARTIAL)
        inv_unpaid = PurchaseInvoiceFactory(status=PurchaseInvoice.Status.UNPAID)

        results = list(purchase_invoice_list())
        inv_ids = [inv.id for inv in results]

        assert inv_ids == [
            inv_unpaid.id,
            inv_partial.id,
            inv_paid.id,
            inv_cancelled.id,
        ]

        # Kiểm tra sắp xếp thứ cấp: cùng trạng thái sắp xếp theo -created_at, sau đó là id.
        now = timezone.now()
        PurchaseInvoice.objects.filter(id=inv_unpaid.id).update(created_at=now - timezone.timedelta(days=2))

        inv_unpaid_new = PurchaseInvoiceFactory(status=PurchaseInvoice.Status.UNPAID)
        PurchaseInvoice.objects.filter(id=inv_unpaid_new.id).update(created_at=now)

        results2 = list(purchase_invoice_list())
        unpaid_ids = [inv.id for inv in results2 if inv.status == PurchaseInvoice.Status.UNPAID]
        assert unpaid_ids == [inv_unpaid_new.id, inv_unpaid.id]
