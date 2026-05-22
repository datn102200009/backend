import pytest

from apps.sales.models import SalesInvoice, SalesOrder
from apps.sales.tests.factories import SalesInvoiceFactory, SalesOrderFactory

pytestmark = pytest.mark.django_db


class TestSalesOrderModel:
    def test_sales_order_creation(self):
        order = SalesOrderFactory(status=SalesOrder.Status.DRAFT, total_amount=500.0)
        assert order.id is not None
        assert order.status == SalesOrder.Status.DRAFT
        assert order.total_amount == 500.0
        assert order.advance_paid_amount == 0
        assert str(order).startswith("Sales Order")


class TestSalesInvoiceModel:
    def test_sales_invoice_creation(self):
        invoice = SalesInvoiceFactory(status=SalesInvoice.Status.UNPAID, total_amount=1000.0)
        assert invoice.id is not None
        assert invoice.status == SalesInvoice.Status.UNPAID
        assert invoice.total_amount == 1000.0
        assert invoice.paid_amount == 0
        assert str(invoice).startswith("Sales Invoice")
