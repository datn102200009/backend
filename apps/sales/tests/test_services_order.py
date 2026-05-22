from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from apps.common.xlib.exceptions import ValidationException
from apps.inventory.models import StockLedger
from apps.inventory.tests.factories import CustomerFactory, ItemFactory, UserFactory, WarehouseFactory
from apps.sales.models import SalesOrder
from apps.sales.services import sales_order_create, sales_order_delete, sales_order_update

pytestmark = pytest.mark.django_db


class TestSalesOrderServices:
    @pytest.fixture
    def setup_data(self):
        user = UserFactory()
        customer = CustomerFactory()
        item = ItemFactory()
        warehouse = WarehouseFactory()

        # Tạo tồn kho khả dụng để pass Validation
        StockLedger.objects.create(
            item=item,
            warehouse=warehouse,
            posting_date="2023-01-01",
            actual_quantity=Decimal("100.00"),
            voucher_number="TEST-IN",
            voucher_type="Stock In",
        )

        return user, customer, item, warehouse

    def test_sales_order_create(self, setup_data):
        user, customer, item, warehouse = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]

        order = sales_order_create(user=user, customer_id=str(customer.id), lines=lines)

        assert order.id is not None
        assert order.status == SalesOrder.Status.DRAFT
        assert order.total_amount == Decimal("500.00")
        assert order.lines.count() == 1

    def test_sales_order_update(self, setup_data):
        user, customer, item, warehouse = setup_data

        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
        )

        updated_lines = [{"item_id": str(item.id), "quantity": Decimal("20.00"), "unit_price": Decimal("50.00")}]
        updated_order = sales_order_update(
            user=user,
            order_id=str(order.id),
            customer_id=str(customer.id),
            status=SalesOrder.Status.DRAFT,
            lines=updated_lines,
        )

        assert updated_order.status == SalesOrder.Status.DRAFT
        assert updated_order.total_amount == Decimal("1000.00")

    def test_sales_order_delete(self, setup_data):
        user, customer, item, warehouse = setup_data
        order = sales_order_create(
            user=user,
            customer_id=str(customer.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
        )

        sales_order_delete(user=user, order_id=str(order.id))

        assert not SalesOrder.objects.filter(id=order.id).exists()
