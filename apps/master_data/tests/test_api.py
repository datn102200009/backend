from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.inventory.tests.factories import ItemFactory, RoleFactory, UserFactory
from apps.master_data.models import Item


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(api_client):
    user = UserFactory(role=RoleFactory())
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
@patch("apps.common.xlib.permissions.PermissionChecker.check_permission", return_value=True)
class TestItemAPI:

    def test_list_items(self, mock_check, auth_client):
        ItemFactory.create_batch(5)
        url = "/api/v1/master-data/items/list/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] >= 5

    def test_list_items_pagination_limit_dos(self, mock_check, auth_client):
        ItemFactory.create_batch(105)
        url = "/api/v1/master-data/items/list/?limit=1000"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Check that it's capped at 100
        assert len(response.data["results"]) == 100
        assert response.data["count"] >= 105

    def test_create_item(self, mock_check, auth_client):
        url = "/api/v1/master-data/items/create/"
        data = {
            "item_code": "API-001",
            "item_name": "API Item",
            "minimum_threshold": "15.0",
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["item_code"] == "API-001"
        assert Item.objects.filter(item_code="API-001").exists()

    def test_update_item(self, mock_check, auth_client):
        item = ItemFactory(item_code="API-UPD-001", item_name="Old")
        url = f"/api/v1/master-data/items/{item.item_code}/update/"
        data = {
            "item_name": "New",
            "minimum_threshold": "25.0",
        }

        response = auth_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["item_name"] == "New"

        item.refresh_from_db()
        assert item.item_name == "New"

    def test_delete_item(self, mock_check, auth_client):
        item = ItemFactory(item_code="API-DEL-001")
        url = f"/api/v1/master-data/items/{item.item_code}/delete/"

        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Item.objects.filter(item_code="API-DEL-001").exists()


@pytest.mark.django_db
class TestItemAPISecurity:

    def test_authentication_required(self):
        client = APIClient()
        url = "/api/v1/master-data/items/list/"
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_authorization_forbidden(self, mock_check, auth_client):
        from apps.common.xlib.exceptions import PermissionException

        mock_check.side_effect = PermissionException("You do not have permission")

        url = "/api/v1/master-data/items/list/"
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("rest_framework.throttling.UserRateThrottle.wait", return_value=60)
    @patch("rest_framework.throttling.UserRateThrottle.allow_request", return_value=False)
    @patch(
        "apps.common.xlib.permissions.PermissionChecker.check_permission",
        return_value=True,
    )
    def test_rate_limiting(self, mock_check, mock_allow, mock_wait, auth_client):
        url = "/api/v1/master-data/items/create/"
        response = auth_client.post(url, {"item_code": "R", "item_name": "N"})
        # 429 Too Many Requests
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
