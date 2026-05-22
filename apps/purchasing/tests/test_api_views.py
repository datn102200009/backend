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
