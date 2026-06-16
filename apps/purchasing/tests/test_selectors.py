import pytest

from apps.finance.selectors import purchase_invoice_list
from apps.inventory.tests.factories import StockEntryFactory
from apps.purchasing.selectors import purchase_order_detail, purchase_order_list
from apps.purchasing.tests.factories import PurchaseInvoiceFactory, PurchaseOrderFactory, PurchaseOrderLineFactory

pytestmark = pytest.mark.django_db


class TestPurchasingSelectors:
    def test_purchase_order_list(self):
        PurchaseOrderFactory.create_batch(3)
        orders = purchase_order_list()
        assert orders.count() == 3

    def test_purchase_order_list_sorting(self):
        from django.utils import timezone

        from apps.purchasing.models import PurchaseOrder

        # 1. pending
        # 2. paid_unshipped
        # 3. shipped_unpaid
        # 4. cancel_pending
        # 5. draft
        # 6. completed
        # 7. cancelled
        po_cancelled = PurchaseOrderFactory(status=PurchaseOrder.Status.CANCELLED)
        po_completed = PurchaseOrderFactory(status=PurchaseOrder.Status.COMPLETED)
        po_draft = PurchaseOrderFactory(status=PurchaseOrder.Status.DRAFT)
        po_cancel_pending = PurchaseOrderFactory(status=PurchaseOrder.Status.CANCEL_PENDING)
        po_shipped_unpaid = PurchaseOrderFactory(status=PurchaseOrder.Status.SHIPPED_UNPAID)
        po_paid_unshipped = PurchaseOrderFactory(status=PurchaseOrder.Status.PAID_UNSHIPPED)
        po_pending = PurchaseOrderFactory(status=PurchaseOrder.Status.PENDING)

        results = list(purchase_order_list())
        po_ids = [po.id for po in results]

        # Mong đợi thứ tự: pending -> paid_unshipped -> shipped_unpaid -> cancel_pending -> draft -> completed -> cancelled
        assert po_ids == [
            po_pending.id,
            po_paid_unshipped.id,
            po_shipped_unpaid.id,
            po_cancel_pending.id,
            po_draft.id,
            po_completed.id,
            po_cancelled.id,
        ]

        # Kiểm tra sắp xếp thứ cấp: cùng trạng thái sắp xếp theo -created_at, sau đó là id.
        now = timezone.now()
        PurchaseOrder.objects.filter(id=po_pending.id).update(created_at=now - timezone.timedelta(days=2))

        po_pending_new = PurchaseOrderFactory(status=PurchaseOrder.Status.PENDING)
        PurchaseOrder.objects.filter(id=po_pending_new.id).update(created_at=now)

        results2 = list(purchase_order_list())
        pending_ids = [po.id for po in results2 if po.status == PurchaseOrder.Status.PENDING]
        assert pending_ids == [po_pending_new.id, po_pending.id]

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

    def test_shipment_list_sorting(self):
        from django.utils import timezone

        from apps.purchasing.models import Shipment
        from apps.purchasing.selectors import shipment_list
        from apps.purchasing.tests.factories import ShipmentFactory

        # Status: inspecting (1) -> draft (2) -> completed (3)
        s_completed = ShipmentFactory(status=Shipment.Status.COMPLETED)
        s_draft = ShipmentFactory(status=Shipment.Status.DRAFT)
        s_inspecting = ShipmentFactory(status=Shipment.Status.INSPECTING)

        results = list(shipment_list())
        s_ids = [s.id for s in results]

        # Mong đợi thứ tự: inspecting -> draft -> completed
        assert s_ids == [
            s_inspecting.id,
            s_draft.id,
            s_completed.id,
        ]

        # Kiểm tra sắp xếp thứ cấp: cùng trạng thái sắp xếp theo -created_at, sau đó là id.
        now = timezone.now()
        Shipment.objects.filter(id=s_inspecting.id).update(created_at=now - timezone.timedelta(days=2))

        s_inspecting_new = ShipmentFactory(status=Shipment.Status.INSPECTING)
        Shipment.objects.filter(id=s_inspecting_new.id).update(created_at=now)

        results2 = list(shipment_list())
        inspecting_ids = [s.id for s in results2 if s.status == Shipment.Status.INSPECTING]
        assert inspecting_ids == [s_inspecting_new.id, s_inspecting.id]
