import pytest

from apps.purchasing.selectors import purchase_invoice_list, purchase_order_list
from apps.purchasing.tests.factories import PurchaseInvoiceFactory, PurchaseOrderFactory

pytestmark = pytest.mark.django_db


class TestPurchasingSelectors:
    def test_purchase_order_list(self):
        PurchaseOrderFactory.create_batch(3)
        orders = purchase_order_list()
        assert orders.count() == 3

    def test_purchase_invoice_list(self):
        PurchaseInvoiceFactory.create_batch(2)
        invoices = purchase_invoice_list()
        assert invoices.count() == 2
