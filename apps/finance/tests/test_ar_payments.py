from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.xlib.exceptions import PermissionException, ValidationException
from apps.finance.services import collect_sales_invoice
from apps.inventory.tests.factories import CustomerFactory, ItemFactory, UserFactory, WarehouseFactory
from apps.sales.models import SalesInvoice
from apps.sales.services import sales_order_approve, sales_order_create

pytestmark = pytest.mark.django_db


class TestARPayments:
    @pytest.fixture
    def setup_data(self):
        user = UserFactory()
        customer = CustomerFactory(credit_limit=Decimal("10000.00"))
        item = ItemFactory()
        warehouse = WarehouseFactory()
        return user, customer, item, warehouse

    def test_collect_sales_invoice_success(self, setup_data):
        user, customer, item, warehouse = setup_data

        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = sales_order_create(user=user, customer_id=str(customer.id), lines=lines)
        order = sales_order_approve(user=user, order_id=str(order.id))

        invoice = order.invoices.first()
        assert invoice.status == SalesInvoice.Status.UNPAID

        # Collect part of the invoice
        tx = collect_sales_invoice(
            user=user,
            invoice_id=str(invoice.id),
            amount=Decimal("200.00"),
            payment_method="bank_transfer",
        )

        assert tx.payment_type == "receive"
        assert tx.amount == Decimal("200.00")
        assert tx.sales_invoice == invoice
        assert tx.status == "posted"

        invoice.refresh_from_db()
        assert invoice.status == SalesInvoice.Status.PARTIAL
        assert invoice.paid_amount == Decimal("200.00")

        # Collect the rest
        tx2 = collect_sales_invoice(
            user=user,
            invoice_id=str(invoice.id),
            amount=Decimal("300.00"),
            payment_method="bank_transfer",
        )

        assert tx2.status == "posted"
        invoice.refresh_from_db()
        assert invoice.status == SalesInvoice.Status.PAID
        assert invoice.paid_amount == Decimal("500.00")

    def test_collect_sales_invoice_api_success(self, mock_permission_checker, setup_data):
        user, customer, item, warehouse = setup_data

        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = sales_order_create(user=user, customer_id=str(customer.id), lines=lines)
        order = sales_order_approve(user=user, order_id=str(order.id))
        invoice = order.invoices.first()

        client = APIClient()
        client.force_authenticate(user=user)
        url = reverse("sales-invoice-collect", kwargs={"pk": invoice.id})

        response = client.post(url, {"amount": "200.00", "payment_method": "bank_transfer"})
        assert response.status_code == status.HTTP_200_OK

        invoice.refresh_from_db()
        assert invoice.status == SalesInvoice.Status.PARTIAL
        assert invoice.paid_amount == Decimal("200.00")
        mock_permission_checker.assert_any_call(user, "finance.collect_sales_invoice")

    def test_collect_sales_invoice_api_forbidden(self, mock_permission_checker, setup_data):
        user, customer, item, warehouse = setup_data

        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = sales_order_create(user=user, customer_id=str(customer.id), lines=lines)
        order = sales_order_approve(user=user, order_id=str(order.id))
        invoice = order.invoices.first()

        # Override the mock to raise PermissionException only for the actual API call checking
        mock_permission_checker.side_effect = PermissionException("No permission")

        client = APIClient()
        client.force_authenticate(user=user)
        url = reverse("sales-invoice-collect", kwargs={"pk": invoice.id})

        response = client.post(url, {"amount": "200.00", "payment_method": "bank_transfer"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
