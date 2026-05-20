from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.common.xlib.exceptions import ValidationException
from apps.finance.models import CashFlowTransaction
from apps.finance.services import cash_flow_create
from apps.inventory.tests.factories import UserFactory
from apps.purchasing.tests.factories import PurchaseInvoiceFactory, PurchaseOrderFactory
from apps.sales.tests.factories import SalesInvoiceFactory, SalesOrderFactory

pytestmark = pytest.mark.django_db


class TestCashFlowServices:
    @pytest.fixture
    def user(self):
        return UserFactory()

    def test_cash_flow_purchase_order_deposit(self, user):
        po = PurchaseOrderFactory(total_amount=Decimal("1000.00"), advance_paid_amount=0)

        cash_flow_create(
            user=user,
            payment_type="pay",
            amount=Decimal("200.00"),
            payment_date="2023-10-01",
            purchase_order_id=str(po.id),
        )

        po.refresh_from_db()
        assert po.advance_paid_amount == Decimal("200.00")

    def test_cash_flow_purchase_order_overpay(self, user):
        po = PurchaseOrderFactory(total_amount=Decimal("1000.00"), advance_paid_amount=0)

        with pytest.raises(ValidationException, match="Số tiền thanh toán vượt quá giá trị"):
            cash_flow_create(
                user=user,
                payment_type="pay",
                amount=Decimal("1200.00"),
                payment_date="2023-10-01",
                purchase_order_id=str(po.id),
            )

    def test_cash_flow_sales_invoice_settlement(self, user):
        invoice = SalesInvoiceFactory(total_amount=Decimal("500.00"), paid_amount=0)

        cash_flow_create(
            user=user,
            payment_type="receive",
            amount=Decimal("500.00"),
            payment_date="2023-10-01",
            sales_invoice_id=str(invoice.id),
        )

        invoice.refresh_from_db()
        assert invoice.paid_amount == Decimal("500.00")
        assert invoice.status == "paid"
