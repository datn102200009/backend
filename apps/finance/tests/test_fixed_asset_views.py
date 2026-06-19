from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.xlib.exceptions import PermissionException
from apps.finance.tests.factories import FixedAssetDepreciationLogFactory, FixedAssetFactory
from apps.inventory.tests.factories import ItemFactory, SupplierFactory, UserFactory

pytestmark = pytest.mark.django_db


class TestFixedAssetAPIViews:
    @pytest.fixture
    def authenticated_client(self):
        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    # --- GET /fixed-assets/ ---
    def test_get_fixed_assets_list_success(self, mock_permission_checker, authenticated_client):
        FixedAssetFactory.create_batch(3)
        url = reverse("fixed-asset-list-create")
        response = authenticated_client.get(url, {"limit": "2", "page": "1"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        assert len(response.data["results"]) == 2
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.view_fixed_asset")

    def test_get_fixed_assets_list_validation_error(self, mock_permission_checker, authenticated_client):
        url = reverse("fixed-asset-list-create")
        response = authenticated_client.get(url, {"limit": "abc"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

    # --- POST /fixed-assets/ ---
    def test_post_fixed_asset_success(self, mock_permission_checker, authenticated_client):
        SupplierFactory(name="NCC_TSCĐ")
        ItemFactory(item_code="FA_PLACEHOLDER")
        url = reverse("fixed-asset-list-create")
        payload = {
            "asset_name": "Khuôn Mẫu A",
            "original_value": "50000000.00",
            "depreciation_method": "straight_line",
            "useful_life_months": 12,
            "vendor_name": "NCC_TSCĐ",
            "payment_method": "bank_transfer",
        }
        response = authenticated_client.post(url, payload)
        assert response.status_code == status.HTTP_201_CREATED

        # Verify decimal types are returned as string
        assert isinstance(response.data["original_value"], str)
        assert response.data["original_value"] == "50000000.00"
        assert response.data["remaining_value"] == "50000000.00"
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.create_fixed_asset")

    def test_post_fixed_asset_permission_denied(self, mock_permission_checker, authenticated_client):
        mock_permission_checker.side_effect = PermissionException("No permission")
        url = reverse("fixed-asset-list-create")
        payload = {
            "asset_code": "ASSET-VIEW-002",
            "asset_name": "Khuôn Mẫu B",
            "original_value": "50000000.00",
            "depreciation_method": "straight_line",
            "useful_life_months": 12,
            "vendor_name": "NCC_TSCĐ",
        }
        response = authenticated_client.post(url, payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # --- GET /fixed-assets/<uuid:pk>/ ---
    def test_get_fixed_asset_detail(self, mock_permission_checker, authenticated_client):
        asset = FixedAssetFactory()
        url = reverse("fixed-asset-detail", kwargs={"pk": asset.id})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(asset.id)
        assert isinstance(response.data["original_value"], str)
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.view_fixed_asset")

    # --- PATCH /fixed-assets/<uuid:pk>/ ---
    def test_patch_fixed_asset_success(self, mock_permission_checker, authenticated_client):
        asset = FixedAssetFactory(asset_name="Tên cũ", status="idle")
        url = reverse("fixed-asset-detail", kwargs={"pk": asset.id})
        response = authenticated_client.patch(url, {"asset_name": "Tên mới"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["asset_name"] == "Tên mới"
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.update_fixed_asset")

    def test_patch_fixed_asset_permission_denied(self, mock_permission_checker, authenticated_client):
        mock_permission_checker.side_effect = PermissionException("No permission")
        asset = FixedAssetFactory(status="idle")
        url = reverse("fixed-asset-detail", kwargs={"pk": asset.id})
        response = authenticated_client.patch(url, {"asset_name": "Tên mới"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patch_fixed_asset_blocked_for_non_idle(self, mock_permission_checker, authenticated_client):
        asset = FixedAssetFactory(status="active")
        url = reverse("fixed-asset-detail", kwargs={"pk": asset.id})
        response = authenticated_client.patch(url, {"asset_name": "Tên mới"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data or "detail" in response.data or "non_field_errors" in response.data

    # --- DELETE /fixed-assets/<uuid:pk>/ ---
    def test_delete_fixed_asset_blocked(self, mock_permission_checker, authenticated_client):
        asset = FixedAssetFactory()
        url = reverse("fixed-asset-detail", kwargs={"pk": asset.id})
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "không thể xóa" in response.data["error"]
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.delete_fixed_asset")

    def test_delete_fixed_asset_permission_denied(self, mock_permission_checker, authenticated_client):
        mock_permission_checker.side_effect = PermissionException("No permission")
        asset = FixedAssetFactory()
        url = reverse("fixed-asset-detail", kwargs={"pk": asset.id})
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # --- POST /fixed-assets/depreciation/ ---
    def test_post_run_depreciation_success(self, mock_permission_checker, authenticated_client):
        FixedAssetFactory(
            original_value=Decimal("12000.00"),
            salvage_value=Decimal("2000.00"),
            depreciation_method="straight_line",
            useful_life_months=10,
            remaining_life_months=10,
            accumulated_depreciation=Decimal("0.00"),
        )
        url = reverse("depreciation-run")
        response = authenticated_client.post(url, {"period": "2026-06"})
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) == 1
        assert response.data[0]["depreciation_amount"] == "1200.00"
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.run_depreciation")

    def test_post_run_depreciation_permission_denied(self, mock_permission_checker, authenticated_client):
        mock_permission_checker.side_effect = PermissionException("No permission")
        url = reverse("depreciation-run")
        response = authenticated_client.post(url, {"period": "2026-06"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # --- GET /fixed-assets/depreciation-logs/ ---
    def test_get_depreciation_logs_success(self, mock_permission_checker, authenticated_client):
        FixedAssetDepreciationLogFactory.create_batch(2, period="2026-06")
        url = reverse("depreciation-log-list")
        response = authenticated_client.get(url, {"period": "2026-06", "limit": "5"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.view_fixed_asset")

    def test_get_depreciation_logs_validation_error(self, mock_permission_checker, authenticated_client):
        url = reverse("depreciation-log-list")
        response = authenticated_client.get(url, {"limit": "-5"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_post_request_dispose_success(self, mock_permission_checker, authenticated_client):
        asset = FixedAssetFactory(status="idle")
        url = reverse("fixed-asset-request-dispose", kwargs={"pk": asset.id})
        payload = {"disposal_value": "1500.00", "remarks": "Request dispose"}
        response = authenticated_client.post(url, payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "pending_dispose"
        assert response.data["disposal_value"] == "1500.00"
        assert response.data["disposal_date"] is None
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.update_fixed_asset")

    def test_get_fixed_assets_list_assignable(self, mock_permission_checker, authenticated_client):
        FixedAssetFactory(status="idle")
        FixedAssetFactory(status="active")
        url = reverse("fixed-asset-list-create")
        response = authenticated_client.get(url, {"assignable": "true"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["status"] == "idle"

    def test_post_fixed_asset_uop_success(self, mock_permission_checker, authenticated_client):
        SupplierFactory(name="NCC_TSCĐ")
        ItemFactory(item_code="FA_PLACEHOLDER")
        url = reverse("fixed-asset-list-create")
        payload = {
            "asset_name": "Khuôn Mẫu UOP",
            "original_value": "50000000.00",
            "salvage_value": "5000000.00",
            "depreciation_method": "unit_of_production",
            "designed_capacity": "10000.00",
            "purchase_date": "2026-06-15",
            "vendor_name": "NCC_TSCĐ",
            "payment_method": "bank_transfer",
        }
        response = authenticated_client.post(url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["useful_life_months"] is None
        assert response.data["remaining_life_months"] is None
        assert response.data["designed_capacity"] == "10000.00"

    def test_post_fixed_asset_uop_rejects_life_months(self, mock_permission_checker, authenticated_client):
        url = reverse("fixed-asset-list-create")
        payload = {
            "asset_name": "Khuôn Mẫu UOP Fail",
            "original_value": "50000000.00",
            "depreciation_method": "unit_of_production",
            "useful_life_months": 12,
            "designed_capacity": "10000.00",
            "purchase_date": "2026-06-15",
            "vendor_name": "NCC_TSCĐ",
        }
        response = authenticated_client.post(url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "useful_life_months" in response.data or "non_field_errors" in response.data

    def test_post_fixed_asset_straight_line_requires_life_months(self, mock_permission_checker, authenticated_client):
        url = reverse("fixed-asset-list-create")
        payload = {
            "asset_name": "Khuôn Mẫu SL Fail",
            "original_value": "50000000.00",
            "depreciation_method": "straight_line",
            "purchase_date": "2026-06-15",
            "vendor_name": "NCC_TSCĐ",
        }
        response = authenticated_client.post(url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "useful_life_months" in response.data or "non_field_errors" in response.data
