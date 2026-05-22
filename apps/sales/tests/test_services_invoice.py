from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.common.xlib.exceptions import ValidationException
from apps.inventory.models import StockLedger
from apps.inventory.services import stock_entry_update, stock_issue_approve
from apps.inventory.tests.factories import CustomerFactory, ItemFactory, UserFactory, WarehouseFactory
from apps.sales.models import SalesInvoice, SalesOrder
from apps.sales.services import sales_order_approve, sales_order_create

pytestmark = pytest.mark.django_db


class TestSalesInvoiceServices:
    @pytest.fixture
    def setup_data(self):
        user = UserFactory()
        customer = CustomerFactory()
        item = ItemFactory()
        warehouse = WarehouseFactory()

        StockLedger.objects.create(
            item=item,
            warehouse=warehouse,
            posting_date="2023-01-01",
            actual_quantity=Decimal("100.00"),
            voucher_number="TEST-IN",
            voucher_type="Stock In",
        )
        return user, customer, item, warehouse

    def test_sales_order_approve_workflow(self, setup_data):
        user, customer, item, warehouse = setup_data

        # 1. Create order (no warehouse needed)
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = sales_order_create(user=user, customer_id=str(customer.id), lines=lines)

        # 2. Approve order
        order = sales_order_approve(user=user, order_id=str(order.id))

        assert order.status == SalesOrder.Status.PENDING

        invoice = order.invoices.first()
        assert invoice is not None
        assert invoice.status == SalesInvoice.Status.UNPAID
        assert invoice.total_amount == Decimal("500.00")

        stock_entry = order.stock_entries.first()
        assert stock_entry is not None
        assert stock_entry.status == "draft"

        # 3. Verify stock detail source_warehouse is None initially
        detail = stock_entry.details.first()
        assert detail.source_warehouse is None

        # 4. Warehouse staff updates source warehouse
        stock_entry_update(
            user=user,
            stock_entry_id=str(stock_entry.id),
            details=[{"detail_id": str(detail.id), "source_warehouse_id": str(warehouse.id)}],
        )
        detail.refresh_from_db()
        assert detail.source_warehouse == warehouse

        # 5. Approve stock entry
        stock_issue_approve(user=user, stock_entry_id=str(stock_entry.id))

        # 6. Verify order status becomes SHIPPED_UNPAID
        order.refresh_from_db()
        assert order.status == SalesOrder.Status.SHIPPED_UNPAID

    def test_sales_order_approve_already_approved(self, setup_data):
        user, customer, item, warehouse = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]
        order = sales_order_create(user=user, customer_id=str(customer.id), lines=lines)

        sales_order_approve(user=user, order_id=str(order.id))

        with pytest.raises(ValidationException):
            sales_order_approve(user=user, order_id=str(order.id))
