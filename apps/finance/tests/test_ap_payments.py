from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.xlib.exceptions import PermissionException
from apps.finance.services import pay_purchase_invoice
from apps.inventory.tests.factories import ItemFactory, SupplierFactory, UserFactory, WarehouseFactory
from apps.purchasing.models import PurchaseInvoice
from apps.purchasing.services import purchase_order_approve, purchase_order_create, verify_4_way_matching

pytestmark = pytest.mark.django_db


class TestAPPayments:
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

    def test_pay_purchase_invoice_api_success(self, mock_permission_checker, setup_data):
        user, vendor, item, warehouse = setup_data

        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))
        invoice = order.invoices.first()

        client = APIClient()
        client.force_authenticate(user=user)
        url = reverse("purchase-invoice-pay", kwargs={"pk": invoice.id})

        response = client.post(url, {"amount": "200.00", "payment_method": "bank_transfer"})
        assert response.status_code == status.HTTP_200_OK

        invoice.refresh_from_db()
        assert invoice.status == PurchaseInvoice.Status.PARTIAL
        assert invoice.paid_amount == Decimal("200.00")
        mock_permission_checker.assert_any_call(user, "finance.pay_invoice")

    def test_pay_purchase_invoice_api_forbidden(self, mock_permission_checker, setup_data):
        user, vendor, item, warehouse = setup_data

        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)
        order = purchase_order_approve(user=user, order_id=str(order.id))
        invoice = order.invoices.first()

        # Override the mock to raise PermissionException only for the actual API call checking
        mock_permission_checker.side_effect = PermissionException("No permission")

        client = APIClient()
        client.force_authenticate(user=user)
        url = reverse("purchase-invoice-pay", kwargs={"pk": invoice.id})

        response = client.post(url, {"amount": "200.00", "payment_method": "bank_transfer"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
