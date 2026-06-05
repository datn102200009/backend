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


class TestTechnicalCertificationAPIViews:
    @pytest.fixture
    def setup_data(self):
        from apps.inventory.tests.factories import ItemFactory, StockEntryFactory
        from apps.purchasing.tests.factories import ShipmentFactory

        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)

        item = ItemFactory()
        shipment = ShipmentFactory(status="draft")
        stock_entry = StockEntryFactory(purpose="receipt")
        stock_entry.shipment = shipment
        stock_entry.save()

        return user, client, item, shipment, stock_entry

    def test_create_certification_permission_check(self, setup_data, mock_permission_checker):
        user, client, item, shipment, stock_entry = setup_data
        url = reverse("technical-certification-list-create")

        # 1. Test List
        client.get(url)
        mock_permission_checker.assert_any_call(user, "purchasing.manage_qc")

        # 2. Test Create
        data = {
            "item_id": str(item.id),
            "stock_entry_id": str(stock_entry.id),
            "cert_type": "QA Check",
            "result": "PASSED",
            "remarks": "Passed all specs",
        }
        client.post(url, data)
        mock_permission_checker.assert_any_call(user, "purchasing.manage_qc")

    def test_create_certification_blocked_in_draft_shipment(self, setup_data):
        user, client, item, shipment, stock_entry = setup_data
        url = reverse("technical-certification-list-create")

        # Shipment is in 'draft' state, should fail with 400 Bad Request
        data = {
            "item_id": str(item.id),
            "stock_entry_id": str(stock_entry.id),
            "cert_type": "QA Check",
            "result": "PASSED",
            "remarks": "Passed all specs",
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Không được phép thực hiện kiểm định QA/QC sớm" in response.data["error"]

    def test_create_certification_success_when_arrived(self, setup_data):
        user, client, item, shipment, stock_entry = setup_data
        url = reverse("technical-certification-list-create")

        shipment.status = "arrived"
        shipment.save()

        data = {
            "item_id": str(item.id),
            "stock_entry_id": str(stock_entry.id),
            "cert_type": "QA Check",
            "result": "PASSED",
            "remarks": "Passed all specs",
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["result"] == "PASSED"
