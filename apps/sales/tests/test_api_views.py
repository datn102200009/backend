import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.inventory.tests.factories import UserFactory
from apps.sales.tests.factories import SalesOrderFactory

pytestmark = pytest.mark.django_db


class TestSalesAPIViews:
    @pytest.fixture
    def authenticated_client(self):
        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_get_orders_list(self, authenticated_client):
        SalesOrderFactory.create_batch(2)
        url = reverse("sales-order-list-create")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_unauthenticated_access(self):
        client = APIClient()
        url = reverse("sales-order-list-create")
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_sales_order_cancel_api_permission_check(self, authenticated_client, mock_permission_checker):
        order = SalesOrderFactory(status="pending")
        url = reverse("sales-order-cancel", kwargs={"pk": order.id})

        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "sales.cancel_order")

    def test_sales_order_cancel_api_permission_denied(self, authenticated_client, mock_permission_checker):
        from apps.common.xlib.exceptions import PermissionException

        mock_permission_checker.side_effect = PermissionException("Không có quyền")

        order = SalesOrderFactory(status="pending")
        url = reverse("sales-order-cancel", kwargs={"pk": order.id})

        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {"error": "Không có quyền"}
