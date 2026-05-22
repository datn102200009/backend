import pytest

from apps.purchasing.models import PurchaseInvoice, PurchaseOrder
from apps.purchasing.tests.factories import PurchaseInvoiceFactory, PurchaseOrderFactory

pytestmark = pytest.mark.django_db


class TestPurchaseOrderModel:
    def test_purchase_order_creation(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.DRAFT, total_amount=500.0)
        assert order.id is not None
        assert order.status == PurchaseOrder.Status.DRAFT
        assert order.total_amount == 500.0
        assert order.advance_paid_amount == 0
        assert str(order).startswith("Purchase Order")


class TestPurchaseInvoiceModel:
    def test_purchase_invoice_creation(self):
        invoice = PurchaseInvoiceFactory(status=PurchaseInvoice.Status.UNPAID, total_amount=1000.0)
        assert invoice.id is not None
        assert invoice.status == PurchaseInvoice.Status.UNPAID
        assert invoice.total_amount == 1000.0
        assert invoice.paid_amount == 0
        assert str(invoice).startswith("Purchase Invoice")
