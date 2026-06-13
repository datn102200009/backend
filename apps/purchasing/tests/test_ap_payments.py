import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.xlib.exceptions import ValidationException
from apps.inventory.tests.factories import ItemFactory, SupplierFactory, UserFactory, WarehouseFactory
from apps.purchasing.models import PurchaseInvoice
from apps.purchasing.selectors import get_supplier_ap_aging
from apps.purchasing.services import purchase_order_approve, purchase_order_create

pytestmark = pytest.mark.django_db


class TestAPPaymentsAndAging:
    @pytest.fixture
    def setup_data(self):
        user = UserFactory()
        vendor = SupplierFactory()
        item = ItemFactory()
        warehouse = WarehouseFactory()
        return user, vendor, item, warehouse

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
