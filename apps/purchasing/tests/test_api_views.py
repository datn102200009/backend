import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.inventory.tests.factories import UserFactory
from apps.purchasing.tests.factories import PurchaseOrderFactory

pytestmark = pytest.mark.django_db


class TestPurchaseAPIViews:
    @pytest.fixture
    def authenticated_client(self):
        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_get_orders_list(self, authenticated_client):
        PurchaseOrderFactory.create_batch(2)
        url = reverse("purchase-order-list-create")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_unauthenticated_access(self):
        client = APIClient()
        url = reverse("purchase-order-list-create")
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_invoices_list_paginated_by_default(self, authenticated_client):
        from apps.purchasing.tests.factories import PurchaseInvoiceFactory

        PurchaseInvoiceFactory.create_batch(3)
        url = reverse("purchase-invoice-list")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "count" in response.data
        assert "results" in response.data
        assert "total_pages" in response.data
        assert response.data["count"] == 3
        assert len(response.data["results"]) == 3

    def test_get_invoices_list_pagination_limit(self, authenticated_client):
        from apps.purchasing.tests.factories import PurchaseInvoiceFactory

        PurchaseInvoiceFactory.create_batch(3)
        url = reverse("purchase-invoice-list")
        response = authenticated_client.get(f"{url}?limit=2")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        assert len(response.data["results"]) == 2

    def test_purchase_order_cancel_api_permission_check(self, authenticated_client, mock_permission_checker):
        order = PurchaseOrderFactory(status="pending")
        url = reverse("purchase-order-cancel", kwargs={"pk": order.id})

        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "purchasing.cancel_order")

    def test_purchase_order_cancel_api_permission_denied(self, authenticated_client, mock_permission_checker):
        from apps.common.xlib.exceptions import PermissionException

        mock_permission_checker.side_effect = PermissionException("Không có quyền")

        order = PurchaseOrderFactory(status="pending")
        url = reverse("purchase-order-cancel", kwargs={"pk": order.id})

        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {"error": "Không có quyền"}

    def test_purchase_order_receive_api_returns_invoice_payload(self, authenticated_client):
        """Đảm bảo cross-module import PurchaseInvoiceSerializer vẫn hoạt động sau khi tài liệu hóa."""
        import uuid
        from unittest.mock import patch

        from apps.purchasing.tests.factories import PurchaseInvoiceFactory, PurchaseOrderFactory

        order = PurchaseOrderFactory(status="approved")
        invoice = PurchaseInvoiceFactory(order=order)

        with patch("apps.purchasing.api.v1.views.purchase_order_receive_goods") as mock_receive:
            mock_receive.return_value = invoice

            url = reverse("purchase-order-receive", kwargs={"pk": order.id})
            data = {"target_warehouse_id": str(uuid.uuid4())}

            response = authenticated_client.post(url, data, format="json")
            assert response.status_code == status.HTTP_200_OK
            mock_receive.assert_called_once_with(
                user=authenticated_client.handler._force_user,
                order_id=str(order.id),
                target_warehouse_id=data["target_warehouse_id"],
            )
            assert "total_amount" in response.data
            assert "id" in response.data


class TestShipmentAPIViews:
    @pytest.fixture
    def setup_data(self):
        from decimal import Decimal

        from apps.inventory.tests.factories import ItemFactory, WarehouseFactory
        from apps.purchasing.tests.factories import PurchaseOrderFactory

        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)

        item = ItemFactory()
        warehouse = WarehouseFactory()
        po = PurchaseOrderFactory(status="pending")
        # Ensure the PO has lines
        from apps.purchasing.models import PurchaseOrderLine

        po_line = PurchaseOrderLine.objects.create(
            order=po,
            item=item,
            quantity=Decimal("10.00"),
            unit_price=Decimal("100.00"),
        )

        return user, client, item, warehouse, po, po_line

    def test_shipment_complete_success(self, setup_data, mock_permission_checker):
        from decimal import Decimal

        from apps.purchasing.models import Shipment

        user, client, item, warehouse, po, po_line = setup_data

        # Create shipment
        from apps.purchasing.services import shipment_create_from_po, shipment_update

        shipment = shipment_create_from_po(
            user=user,
            shipment_num="SH-API-TEST-01",
            name="API Test Shipment",
            purchase_order_id=str(po.id),
        )
        shipment_update(user=user, shipment_id=str(shipment.id), status="inspecting")

        url = reverse("shipment-complete", kwargs={"pk": shipment.id})
        data = {
            "total_logistic_fees": "15000.00",
            "details": [
                {
                    "po_line_id": str(po_line.id),
                    "item_id": str(item.id),
                    "quantity": "10.00",
                    "target_warehouse_id": str(warehouse.id),
                }
            ],
        }

        response = client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK
        mock_permission_checker.assert_any_call(user, "purchasing.allocate_landed_cost")

        shipment.refresh_from_db()
        assert shipment.status == Shipment.Status.PENDING_APPROVAL
        assert shipment.total_logistic_fees == Decimal("15000.00")

    def test_shipment_complete_invalid_status(self, setup_data):
        user, client, item, warehouse, po, po_line = setup_data

        from apps.purchasing.services import shipment_create_from_po

        shipment = shipment_create_from_po(
            user=user,
            shipment_num="SH-API-TEST-02",
            name="API Test Shipment Draft",
            purchase_order_id=str(po.id),
        )

        url = reverse("shipment-complete", kwargs={"pk": shipment.id})
        data = {
            "total_logistic_fees": "0.00",
            "details": [
                {
                    "po_line_id": str(po_line.id),
                    "item_id": str(item.id),
                    "quantity": "10.00",
                    "target_warehouse_id": str(warehouse.id),
                }
            ],
        }

        response = client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_shipment_complete_quantity_exceeds_po(self, setup_data):
        user, client, item, warehouse, po, po_line = setup_data

        from apps.purchasing.services import shipment_create_from_po, shipment_update

        shipment = shipment_create_from_po(
            user=user,
            shipment_num="SH-API-TEST-03",
            name="API Test Shipment Exceed",
            purchase_order_id=str(po.id),
        )
        shipment_update(user=user, shipment_id=str(shipment.id), status="inspecting")

        url = reverse("shipment-complete", kwargs={"pk": shipment.id})
        data = {
            "total_logistic_fees": "0.00",
            "details": [
                {
                    "po_line_id": str(po_line.id),
                    "item_id": str(item.id),
                    "quantity": "15.00",
                    "target_warehouse_id": str(warehouse.id),
                }
            ],
        }

        response = client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_shipment_complete_missing_warehouse(self, setup_data):
        user, client, item, warehouse, po, po_line = setup_data

        from apps.purchasing.services import shipment_create_from_po, shipment_update

        shipment = shipment_create_from_po(
            user=user,
            shipment_num="SH-API-TEST-04",
            name="API Test Shipment Missing WH",
            purchase_order_id=str(po.id),
        )
        shipment_update(user=user, shipment_id=str(shipment.id), status="inspecting")

        url = reverse("shipment-complete", kwargs={"pk": shipment.id})
        data = {
            "total_logistic_fees": "0.00",
            "details": [
                {
                    "po_line_id": str(po_line.id),
                    "item_id": str(item.id),
                    "quantity": "10.00",
                    "target_warehouse_id": None,
                }
            ],
        }

        response = client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
