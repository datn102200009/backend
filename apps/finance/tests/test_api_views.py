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

    def test_get_cash_flow_list(self, mock_permission_checker, authenticated_client):
        CashFlowTransactionFactory.create_batch(2)
        url = reverse("cash-flow-list-create")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.view_cash_flow")

    def test_get_cash_flow_detail(self, mock_permission_checker, authenticated_client):
        tx = CashFlowTransactionFactory()
        url = reverse("cash-flow-detail", kwargs={"pk": tx.id})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(tx.id)
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.view_cash_flow")

    def test_unauthenticated_access(self):
        client = APIClient()
        url = reverse("cash-flow-list-create")
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
