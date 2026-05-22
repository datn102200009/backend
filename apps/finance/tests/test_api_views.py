import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.finance.tests.factories import CashFlowTransactionFactory
from apps.inventory.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class TestFinanceAPIViews:
    @pytest.fixture
    def authenticated_client(self):
        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_get_cash_flow_list(self, authenticated_client):
        CashFlowTransactionFactory.create_batch(2)
        url = reverse("cash-flow-list-create")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_unauthenticated_access(self):
        client = APIClient()
        url = reverse("cash-flow-list-create")
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
