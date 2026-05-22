import pytest

from apps.sales.selectors import sales_invoice_list, sales_order_list
from apps.sales.tests.factories import SalesInvoiceFactory, SalesOrderFactory

pytestmark = pytest.mark.django_db


class TestSalesSelectors:
    def test_sales_order_list(self):
        SalesOrderFactory.create_batch(3)
        orders = sales_order_list()
        assert orders.count() == 3

    def test_sales_invoice_list(self):
        SalesInvoiceFactory.create_batch(2)
        invoices = sales_invoice_list()
        assert invoices.count() == 2
