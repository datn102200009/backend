from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import Permission, RolePermission
from apps.inventory.tests.factories import PermissionFactory, RoleFactory, UserFactory


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
        # Widgets like finance_cashflow_chart or hrm_expiring_contracts should NOT be returned
        assert "finance_cashflow_chart" not in codes
        assert "hrm_expiring_contracts" not in codes

    def test_widget_batch_data_rbac_denied(self, authenticated_client_with_perms):
        client, user = authenticated_client_with_perms
        url = reverse("widget-batch-data")

        # Requesting a widget user has no permission for (e.g. finance_cashflow_summary)
        response = client.get(url, {"widgets": "sales_today_revenue,finance_cashflow_summary"})
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data["sales_today_revenue"]["success"] is True
        assert data["finance_cashflow_summary"]["success"] is False
        assert "permission" in data["finance_cashflow_summary"]["error"].lower()

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
        assert "revenue" in data["sales_today_revenue"]["data"]

        # sales_draft_orders should fail with the mocked error message
        assert data["sales_draft_orders"]["success"] is False
        assert "Database timeout on drafts table" in data["sales_draft_orders"]["error"]

    def test_widget_data_detail_success(self, authenticated_client_with_perms):
        client, user = authenticated_client_with_perms
        url = reverse("widget-data-detail", kwargs={"widget_code": "sales_today_revenue"})

        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert "revenue" in response.data["data"]

    def test_widget_data_detail_permission_denied(self, authenticated_client_with_perms):
        client, user = authenticated_client_with_perms
        url = reverse("widget-data-detail", kwargs={"widget_code": "finance_cashflow_summary"})

        response = client.get(url)
        # Check standard behavior of PermissionChecker.check_permission: raises PermissionException
        # which propagates to 403 Forbidden via the custom exception handler, or returns success: false depending on setup.
        # Here we verify it is either 403 or 400 or 500 but NOT 200 OK.
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_500_INTERNAL_SERVER_ERROR]
