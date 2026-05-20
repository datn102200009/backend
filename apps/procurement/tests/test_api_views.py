import pytest
from django.urls import reverse
from rest_framework import status

from apps.inventory.tests.factories import SupplierFactory, UserFactory
from apps.procurement.models import Supplier


@pytest.mark.django_db
class TestSupplierAPIViews:
    def test_list_suppliers(self):
        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        SupplierFactory(name="S001", supplier_name="Supplier 1")
        SupplierFactory(name="S002", supplier_name="Supplier 2")

        url = reverse("supplier-list-create")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_create_supplier(self):
        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        url = reverse("supplier-list-create")
        payload = {
            "name": "S001",
            "supplier_name": "Supplier 1",
            "supplier_group": "Hardware",
            "contact_email": "s1@example.com",
            "contact_phone": "0987654321",
            "address": "123 Street",
        }
        response = client.post(url, payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "S001"
        assert response.data["supplier_name"] == "Supplier 1"

    def test_get_supplier_detail(self):
        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        supplier = SupplierFactory(name="S001", supplier_name="Supplier 1")
        url = reverse("supplier-detail-update-delete", kwargs={"pk": supplier.id})
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "S001"

    def test_update_supplier(self):
        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        supplier = SupplierFactory(name="S001", supplier_name="Supplier 1")
        url = reverse("supplier-detail-update-delete", kwargs={"pk": supplier.id})
        payload = {"name": "S001-NEW", "supplier_name": "Supplier 1 Updated"}
        response = client.put(url, payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "S001-NEW"
        assert response.data["supplier_name"] == "Supplier 1 Updated"

    def test_delete_supplier(self):
        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        supplier = SupplierFactory()
        url = reverse("supplier-detail-update-delete", kwargs={"pk": supplier.id})
        response = client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_list_suppliers_no_permission(self, mock_permission_checker):
        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        from apps.common.xlib.exceptions import PermissionException

        mock_permission_checker.side_effect = PermissionException("No view permission")

        url = reverse("supplier-list-create")
        response = client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "No view permission"

    def test_get_supplier_not_found(self):
        import uuid

        from rest_framework.test import APIClient

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user=user)

        url = reverse("supplier-detail-update-delete", kwargs={"pk": uuid.uuid4()})
        response = client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
