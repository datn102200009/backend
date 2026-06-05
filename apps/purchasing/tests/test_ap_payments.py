import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.xlib.exceptions import ValidationException
from apps.inventory.tests.factories import ItemFactory, SupplierFactory, UserFactory, WarehouseFactory
from apps.purchasing.models import PurchaseInvoice
from apps.purchasing.selectors import get_supplier_ap_aging
from apps.purchasing.services import (
    pay_purchase_invoice,
    purchase_order_approve,
    purchase_order_create,
    verify_4_way_matching,
)

pytestmark = pytest.mark.django_db


class TestAPPaymentsAndAging:
    @pytest.fixture
    def setup_data(self):
        user = UserFactory()
        vendor = SupplierFactory()
        item = ItemFactory()
        warehouse = WarehouseFactory()
        return user, vendor, item, warehouse

    def test_pay_purchase_invoice_success(self, setup_data):
        user, vendor, item, warehouse = setup_data

        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        invoice = order.invoices.first()
        assert invoice.status == PurchaseInvoice.Status.UNPAID

        # Pay part of the invoice
        tx = pay_purchase_invoice(
            user=user,
            invoice_id=str(invoice.id),
            amount=Decimal("200.00"),
            payment_method="bank_transfer",
        )

        assert tx.payment_type == "pay"
        assert tx.amount == Decimal("200.00")
        assert tx.purchase_invoice == invoice

        invoice.refresh_from_db()
        assert invoice.status == PurchaseInvoice.Status.PARTIAL
        assert invoice.paid_amount == Decimal("200.00")

        # Pay the rest
        pay_purchase_invoice(
            user=user,
            invoice_id=str(invoice.id),
            amount=Decimal("300.00"),
            payment_method="bank_transfer",
        )

        invoice.refresh_from_db()
        assert invoice.status == PurchaseInvoice.Status.PAID
        assert invoice.paid_amount == Decimal("500.00")

    def test_pay_invoice_with_mismatch_succeeds(self, setup_data):
        user, vendor, item, warehouse = setup_data

        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))

        invoice = order.invoices.first()

        # Mismatch unit price to trigger warning in block_reason
        inv_line = invoice.lines.first()
        inv_line.unit_price = Decimal("60.00")
        inv_line.save()

        verify_4_way_matching(invoice_id=str(invoice.id))
        invoice.refresh_from_db()
        assert invoice.status == PurchaseInvoice.Status.UNPAID
        assert "Chênh lệch đơn giá" in invoice.block_reason

        # Pay invoice with warning -> should succeed normally
        tx = pay_purchase_invoice(
            user=user,
            invoice_id=str(invoice.id),
            amount=Decimal("100.00"),
            payment_method="bank_transfer",
        )
        assert tx is not None
        invoice.refresh_from_db()
        assert invoice.status == PurchaseInvoice.Status.PARTIAL

    def test_supplier_ap_aging_selector(self, setup_data):
        user, vendor, item, warehouse = setup_data
        today = timezone.now().date()

        # Create three invoices with different due dates for this supplier
        # Invoice 1: Not due yet (due today)
        po1 = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("2.00"), "unit_price": Decimal("100.00")}],
        )
        purchase_order_approve(user=user, order_id=str(po1.id))
        inv1 = po1.invoices.first()
        inv1.due_date = today
        inv1.save()

        # Invoice 2: Overdue by 10 days
        po2 = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("3.00"), "unit_price": Decimal("100.00")}],
        )
        purchase_order_approve(user=user, order_id=str(po2.id))
        inv2 = po2.invoices.first()
        inv2.due_date = today - datetime.timedelta(days=10)
        inv2.save()

        # Invoice 3: Overdue by 45 days
        po3 = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("4.00"), "unit_price": Decimal("100.00")}],
        )
        purchase_order_approve(user=user, order_id=str(po3.id))
        inv3 = po3.invoices.first()
        inv3.due_date = today - datetime.timedelta(days=45)
        inv3.save()

        # Query aging report
        report = get_supplier_ap_aging(supplier_id=str(vendor.id))

        assert len(report) == 1
        data = report[0]
        assert data["vendor_name"] == vendor.supplier_name
        assert data["not_due"] == Decimal("200.00")
        assert data["overdue_1_30"] == Decimal("300.00")
        assert data["overdue_above_30"] == Decimal("400.00")
        assert data["total_unpaid"] == Decimal("900.00")
