from unittest.mock import patch

import pytest

from apps.assistant.llm.tool_handlers import (
    get_customer_debt_handler,
    get_inventory_balance_handler,
    get_item_detail_handler,
    list_leave_requests_handler,
    list_sales_orders_handler,
    search_items_handler,
)
from apps.common.xlib.exceptions import PermissionException, ValidationException
from apps.inventory.tests.factories import CustomerFactory, ItemFactory, UserFactory, WarehouseFactory
from apps.sales.tests.factories import SalesOrderFactory


@pytest.mark.django_db
class TestChatbotToolHandlers:
    def setup_method(self):
        self.user = UserFactory()

    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_search_items_handler_returns_dict(self, mock_check):
        mock_check.return_value = None
        ItemFactory(item_code="ITEM-001", item_name="Sản phẩm test")

        args = {"query": "test"}
        result = search_items_handler(args, self.user)

        assert "count" in result
        assert "items" in result
        assert result["count"] > 0
        assert result["items"][0]["item_code"] == "ITEM-001"

    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_get_item_detail_handler(self, mock_check):
        mock_check.return_value = None
        ItemFactory(item_code="ITEM-002", item_name="Detail item")

        args = {"item_code": "ITEM-002"}
        result = get_item_detail_handler(args, self.user)
        assert result["item_code"] == "ITEM-002"
        assert result["item_name"] == "Detail item"

    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_get_inventory_balance_handler_with_invalid_item(self, mock_check):
        mock_check.return_value = None
        args = {"item_code": "INVALID-ITEM"}
        result = get_inventory_balance_handler(args, self.user)
        assert "error" in result
        assert "Không tìm thấy sản phẩm" in result["error"]

    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_list_sales_orders_handler_filter_by_status(self, mock_check):
        mock_check.return_value = None
        customer = CustomerFactory()
        SalesOrderFactory(customer=customer, status="completed")
        SalesOrderFactory(customer=customer, status="pending")

        args = {"status": "completed"}
        result = list_sales_orders_handler(args, self.user)
        assert "count" in result
        assert "orders" in result
        assert result["count"] == 1
        assert result["orders"][0]["status"] == "completed"

    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_get_customer_debt_handler_returns_decimal_string(self, mock_check):
        mock_check.return_value = None
        customer = CustomerFactory()

        args = {"customer_id": str(customer.id)}
        result = get_customer_debt_handler(args, self.user)
        assert "customer_id" in result
        assert "current_debt" in result
        assert isinstance(result["current_debt"], str)

    def test_handler_without_permission_raises_PermissionException(self):
        args = {"query": "test"}
        with pytest.raises(PermissionException):
            search_items_handler(args, self.user)

    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_list_leave_requests_handler(self, mock_check):
        mock_check.return_value = None
        from apps.hrm.tests.factories import LeaveRequestFactory

        LeaveRequestFactory(status="approved")

        args = {"status": "approved"}
        result = list_leave_requests_handler(args, self.user)
        assert "count" in result
        assert "requests" in result
        assert result["count"] == 1
        assert result["requests"][0]["status"] == "approved"
