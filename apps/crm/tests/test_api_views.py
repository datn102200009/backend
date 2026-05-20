import pytest
from django.urls import reverse
from rest_framework import status

from apps.crm.models import Customer
from apps.inventory.tests.factories import CustomerFactory, UserFactory


@pytest.mark.django_db
class TestCustomerAPIViews:
    def test_list_customers(self):
        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        CustomerFactory(name="C001", customer_name="Customer 1")
        CustomerFactory(name="C002", customer_name="Customer 2")

        url = reverse("customer-list-create")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_create_customer(self):
        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        url = reverse("customer-list-create")
        payload = {
            "name": "C001",
            "customer_name": "Customer 1",
            "customer_group": "Retail",
            "contact_email": "c1@example.com",
            "contact_phone": "0987654321",
            "address": "123 Street",
        }
        response = client.post(url, payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "C001"
        assert response.data["customer_name"] == "Customer 1"

    def test_get_customer_detail(self):
        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        customer = CustomerFactory(name="C001", customer_name="Customer 1")
        url = reverse("customer-detail-update-delete", kwargs={"pk": customer.id})
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "C001"

    def test_update_customer(self):
        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        customer = CustomerFactory(name="C001", customer_name="Customer 1")
        url = reverse("customer-detail-update-delete", kwargs={"pk": customer.id})
        payload = {"name": "C001-NEW", "customer_name": "Customer 1 Updated"}
        response = client.put(url, payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "C001-NEW"
        assert response.data["customer_name"] == "Customer 1 Updated"

    def test_delete_customer(self):
        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        customer = CustomerFactory()
        url = reverse("customer-detail-update-delete", kwargs={"pk": customer.id})
        response = client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_list_customers_no_permission(self, mock_permission_checker):
        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        from apps.common.xlib.exceptions import PermissionException

        mock_permission_checker.side_effect = PermissionException("No view permission")

        url = reverse("customer-list-create")
        response = client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "No view permission"

    def test_get_customer_not_found(self):
        import uuid

        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        url = reverse("customer-detail-update-delete", kwargs={"pk": uuid.uuid4()})
        response = client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
