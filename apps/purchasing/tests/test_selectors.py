import pytest

from apps.inventory.tests.factories import StockEntryFactory
from apps.purchasing.selectors import purchase_invoice_list, purchase_order_detail, purchase_order_list
from apps.purchasing.tests.factories import PurchaseInvoiceFactory, PurchaseOrderFactory, PurchaseOrderLineFactory

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

    def test_purchase_order_detail_prefetches_related(self, django_assert_num_queries):
        # Create a purchase order
        order = PurchaseOrderFactory()
        # Create lines
        PurchaseOrderLineFactory.create_batch(2, order=order)
        # Create invoices
        PurchaseInvoiceFactory.create_batch(2, order=order)
        # Create stock entries
        StockEntryFactory.create_batch(2, purchase_order=order)

        # Retrieve order details and serialize them, verifying query count is low and constant (no N+1)
        with django_assert_num_queries(8):
            db_order = purchase_order_detail(order_id=str(order.id))

            from apps.purchasing.api.v1.serializers import PurchaseOrderSerializer

            serializer = PurchaseOrderSerializer(db_order)
            data = serializer.data

        assert len(data["lines"]) == 2
        assert len(data["invoices"]) == 2
        assert len(data["stock_entries"]) == 2
