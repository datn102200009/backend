from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from apps.common.xlib.exceptions import ValidationException
from apps.inventory.tests.factories import ItemFactory, SupplierFactory, UserFactory
from apps.purchasing.models import PurchaseOrder
from apps.purchasing.services import purchase_order_create, purchase_order_delete, purchase_order_update

pytestmark = pytest.mark.django_db


class TestPurchaseOrderServices:
    @pytest.fixture
    def setup_data(self):
        user = UserFactory()
        vendor = SupplierFactory()
        item = ItemFactory()
        return user, vendor, item

    def test_purchase_order_create(self, setup_data):
        user, vendor, item = setup_data
        lines = [{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}]

        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=lines)

        assert order.id is not None
        assert order.status == PurchaseOrder.Status.DRAFT
        assert order.total_amount == Decimal("500.00")
        assert order.lines.count() == 1

    def test_purchase_order_update(self, setup_data):
        user, vendor, item = setup_data

        # Create initially
        order = purchase_order_create(
            user=user,
            vendor_id=str(vendor.id),
            lines=[{"item_id": str(item.id), "quantity": Decimal("10.00"), "unit_price": Decimal("50.00")}],
        )

        # Update
        updated_lines = [{"item_id": str(item.id), "quantity": Decimal("20.00"), "unit_price": Decimal("50.00")}]
        updated_order = purchase_order_update(
            user=user,
            order_id=str(order.id),
            vendor_id=str(vendor.id),
            status=PurchaseOrder.Status.PENDING,
            lines=updated_lines,
        )

        assert updated_order.status == PurchaseOrder.Status.PENDING
        assert updated_order.total_amount == Decimal("1000.00")

    def test_purchase_order_update_invalid_status(self, setup_data):
        user, vendor, item = setup_data
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=[])

        # Mock status to COMPLETED
        order.status = PurchaseOrder.Status.COMPLETED
        order.save()

        with pytest.raises(ValidationException):
            purchase_order_update(
                user=user,
                order_id=str(order.id),
                vendor_id=str(vendor.id),
                status=PurchaseOrder.Status.PENDING,
                lines=[],
            )

    def test_purchase_order_delete(self, setup_data):
        user, vendor, item = setup_data
        order = purchase_order_create(user=user, vendor_id=str(vendor.id), lines=[])

        purchase_order_delete(user=user, order_id=str(order.id))

        assert not PurchaseOrder.objects.filter(id=order.id).exists()
