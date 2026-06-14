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
