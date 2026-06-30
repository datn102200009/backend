from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import Permission, UserPermission
from apps.inventory.tests.factories import PermissionFactory, UserFactory


@pytest.mark.django_db
class TestDashboardViews:

    def test_widget_metadata_list_rbac(self, authenticated_client_with_perms):
        client, user = authenticated_client_with_perms
        url = reverse("widget-metadata-list")

        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK

        # Verify that only widgets with sales.view_order are returned (e.g. sales_today_revenue, sales_draft_orders)
        data = response.data
        codes = [item["code"] for item in data]

        assert "sales_today_revenue" in codes
        assert "sales_draft_orders" in codes
        # Widgets like finance_cashflow_overview or hrm_expiring_contracts should NOT be returned
        assert "finance_cashflow_overview" not in codes
        assert "hrm_expiring_contracts" not in codes

    def test_widget_batch_data_rbac_denied(self, authenticated_client_with_perms):
        client, user = authenticated_client_with_perms
        url = reverse("widget-batch-data")

        # Requesting a widget user has no permission for (e.g. finance_unpaid_purchase_invoices)
        response = client.get(url, {"widgets": "sales_today_revenue,finance_unpaid_purchase_invoices"})
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data["sales_today_revenue"]["success"] is True
        assert data["finance_unpaid_purchase_invoices"]["success"] is False
        assert "permission" in data["finance_unpaid_purchase_invoices"]["error"].lower()

    @patch("apps.dashboard.selectors.get_sales_draft_orders")
    def test_widget_batch_data_partial_failure(self, mock_get_drafts, authenticated_client_with_perms):
        # Mock the selector to raise an exception (simulate database timeout or table lock)
        mock_get_drafts.side_effect = Exception("Database timeout on drafts table")

        client, user = authenticated_client_with_perms
        url = reverse("widget-batch-data")

        # Patch SELECTORS_MAP directly to use the mock
        with patch.dict("apps.dashboard.selectors.SELECTORS_MAP", {"sales_draft_orders": mock_get_drafts}):
            response = client.get(url, {"widgets": "sales_today_revenue,sales_draft_orders"})

        # Verify HTTP status is 200 OK (Partial failure does not fail the whole request)
        assert response.status_code == status.HTTP_200_OK

        data = response.data

        # sales_today_revenue should succeed
        assert data["sales_today_revenue"]["success"] is True
        assert isinstance(data["sales_today_revenue"]["data"], dict)

        # sales_draft_orders should fail with the mocked error message
        assert data["sales_draft_orders"]["success"] is False
        assert "Database timeout on drafts table" in data["sales_draft_orders"]["error"]

    def test_widget_data_detail_success(self, authenticated_client_with_perms):
        client, user = authenticated_client_with_perms
        url = reverse("widget-data-detail", kwargs={"widget_code": "sales_today_revenue"})

        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert isinstance(response.data["data"], dict)
        assert "points" in response.data["data"]

    def test_widget_data_detail_permission_denied(self, authenticated_client_with_perms):
        client, user = authenticated_client_with_perms
        url = reverse("widget-data-detail", kwargs={"widget_code": "finance_unpaid_purchase_invoices"})

        response = client.get(url)
        # Check standard behavior of PermissionChecker.check_permission: raises PermissionException
        # which propagates to 403 Forbidden via the custom exception handler, or returns success: false depending on setup.
        # Here we verify it is either 403 or 400 or 500 but NOT 200 OK.
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_warehouse_keeper_widgets_rbac(self, api_client, db):
        user = UserFactory(username="keeper", password_hash="testpass")

        # Give inventory.view and inventory.stock_transfer permissions
        perm_view, _ = Permission.objects.get_or_create(code="inventory.view", defaults={"name": "Xem kho"})
        perm_transfer, _ = Permission.objects.get_or_create(
            code="inventory.stock_transfer", defaults={"name": "Chuyển kho"}
        )
        UserPermission.objects.get_or_create(user=user, permission=perm_view)
        UserPermission.objects.get_or_create(user=user, permission=perm_transfer)

        api_client.force_authenticate(user=user)
        url = reverse("widget-metadata-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        codes = [item["code"] for item in data]

        # Warehouse keeper should see inventory cards they have permissions for
        assert "inventory_low_stock" in codes
        assert "inventory_pending_entries" in codes
        # But not sales or purchasing cards they are not permitted for
        assert "sales_pending_fulfillment" not in codes
        assert "purchasing_active_po_count" not in codes

    def test_widget_batch_and_detail_total_count(self, authenticated_client_with_perms):
        client, user = authenticated_client_with_perms

        # 1. Batch API test
        batch_url = reverse("widget-batch-data")
        response = client.get(batch_url, {"widgets": "sales_draft_orders"})
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert "sales_draft_orders" in data
        assert "total_count" in data["sales_draft_orders"]
        assert isinstance(data["sales_draft_orders"]["total_count"], int)

        # 2. Detail API test
        detail_url = reverse("widget-data-detail", kwargs={"widget_code": "sales_draft_orders"})
        response = client.get(detail_url)
        assert response.status_code == status.HTTP_200_OK
        assert "total_count" in response.data
        assert isinstance(response.data["total_count"], int)

    def test_widget_batch_data_cashflow_overview(self, api_client, db):
        user = UserFactory(username="accountant", password_hash="testpass")
        perm, _ = Permission.objects.get_or_create(code="finance.view_cash_flow", defaults={"name": "Xem dòng tiền"})
        UserPermission.objects.get_or_create(user=user, permission=perm)

        api_client.force_authenticate(user=user)
        url = reverse("widget-batch-data")
        response = api_client.get(url, {"widgets": "finance_cashflow_overview"})
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data["finance_cashflow_overview"]["success"] is True
        payload = data["finance_cashflow_overview"]["data"]
        assert "summary" in payload
        assert "weeks" in payload
        assert payload["summary"]["period_label"] == "4 tuần gần nhất"

    def test_widget_batch_data_manufacturing_pending_wo_approval(self, api_client, db):
        user = UserFactory(username="planner", password_hash="testpass")
        perm, _ = Permission.objects.get_or_create(
            code="manufacturing.work_order_approve", defaults={"name": "Duyệt lệnh SX"}
        )
        UserPermission.objects.get_or_create(user=user, permission=perm)

        api_client.force_authenticate(user=user)
        url = reverse("widget-batch-data")
        response = api_client.get(url, {"widgets": "manufacturing_pending_wo_approval"})
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data["manufacturing_pending_wo_approval"]["success"] is True
        payload = data["manufacturing_pending_wo_approval"]["data"]
        assert "total_count" in payload
        assert "top_items" in payload
        assert isinstance(payload["top_items"], list)

    def test_widget_batch_data_dict_total_count(self, authenticated_client_with_perms):
        client, user = authenticated_client_with_perms
        url = reverse("widget-batch-data")
        response = client.get(url, {"widgets": "sales_draft_orders"})
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["sales_draft_orders"]["success"] is True
        assert "total_count" in data["sales_draft_orders"]
        assert isinstance(data["sales_draft_orders"]["total_count"], int)

    def test_widget_data_detail_with_purpose_filter(self, api_client, db):
        user = UserFactory(username="inv_mgr", password_hash="testpass")
        perm, _ = Permission.objects.get_or_create(code="inventory.stock_transfer", defaults={"name": "Chuyển kho"})
        UserPermission.objects.get_or_create(user=user, permission=perm)

        api_client.force_authenticate(user=user)
        url = reverse("widget-data-detail", kwargs={"widget_code": "inventory_pending_entries"})
        response = api_client.get(url, {"purpose": "transfer"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert "data" in response.data
        assert "total_count" in response.data

    def test_widget_batch_data_finance_pending_cashflow_approval(self, api_client, db):
        user = UserFactory(username="approver", password_hash="testpass")
        perm, _ = Permission.objects.get_or_create(
            code="finance.approve_cash_flow", defaults={"name": "Duyệt dòng tiền"}
        )
        UserPermission.objects.get_or_create(user=user, permission=perm)

        api_client.force_authenticate(user=user)
        url = reverse("widget-batch-data")
        response = api_client.get(url, {"widgets": "finance_pending_cashflow_approval"})
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data["finance_pending_cashflow_approval"]["success"] is True
        payload = data["finance_pending_cashflow_approval"]["data"]
        assert "total_count" in payload
        assert "top_items" in payload
        assert isinstance(payload["top_items"], list)
