from unittest.mock import patch

import pytest

from apps.assistant.llm.tool_handlers import (
    get_business_workflow_handler,
    get_customer_debt_handler,
    get_document_detail_handler,
    get_inventory_balance_handler,
    get_item_detail_handler,
    list_leave_requests_handler,
    list_purchase_orders_handler,
    list_sales_orders_handler,
    search_items_handler,
)
from apps.common.xlib.exceptions import NotFoundException, PermissionException, ValidationException
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

    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_list_purchase_orders_handler_date_filtering(self, mock_check):
        mock_check.return_value = None
        import datetime

        from django.utils import timezone

        from apps.purchasing.tests.factories import PurchaseOrderFactory

        po_april = PurchaseOrderFactory()
        po_april.created_at = timezone.make_aware(datetime.datetime(2026, 4, 15, 12, 0, 0))
        po_april.save()

        po_may = PurchaseOrderFactory()
        po_may.created_at = timezone.make_aware(datetime.datetime(2026, 5, 15, 12, 0, 0))
        po_may.save()

        args = {"start_date": "2026-04-01", "end_date": "2026-04-30"}
        result = list_purchase_orders_handler(args, self.user)
        assert result["count"] == 1
        assert result["orders"][0]["id"] == str(po_april.id)
        assert "created_at" in result["orders"][0]
        assert result["orders"][0]["created_at"] == "2026-04-15"

    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_get_document_detail_handler_success(self, mock_check):
        mock_check.return_value = None
        from apps.purchasing.tests.factories import PurchaseOrderFactory

        po = PurchaseOrderFactory(status="draft", total_amount=150000.00)

        args = {"model_name": "purchase_order", "document_id": str(po.id)}
        result = get_document_detail_handler(args, self.user)
        assert result["id"] == str(po.id)
        assert result["status"] == "draft"
        assert result["total_amount"] == "150000.00"
        assert "lines" in result

    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_get_document_detail_handler_not_found(self, mock_check):
        mock_check.return_value = None
        args = {"model_name": "purchase_order", "document_id": "00000000-0000-0000-0000-000000000000"}
        with pytest.raises(NotFoundException):
            get_document_detail_handler(args, self.user)

    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_get_business_workflow_handler_success(self, mock_check):
        mock_check.return_value = None
        args = {"topic": "inventory"}
        result = get_business_workflow_handler(args, self.user)
        assert result["topic"] == "inventory"
        assert "content" in result
        assert "# Hướng Dẫn Chi Tiết Từng Bước: Quản Lý Sản Phẩm Và Giao Dịch Kho" in result["content"]

    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_get_business_workflow_handler_invalid_topic(self, mock_check):
        mock_check.return_value = None
        args = {"topic": "invalid_topic"}
        with pytest.raises(ValidationException):
            get_business_workflow_handler(args, self.user)

    def test_list_tools_for_llm_resolves_dynamic_choices(self):
        from apps.assistant.llm.tool_registry import list_tools_for_llm

        tools = list_tools_for_llm()

        # Tìm tool list_purchase_orders
        po_tool = next((t for t in tools if t["function"]["name"] == "list_purchase_orders"), None)
        assert po_tool is not None

        # Kiểm tra parameters schema xem status đã được resolve thành enum chưa
        properties = po_tool["function"]["parameters"]["properties"]
        assert "status" in properties
        status_prop = properties["status"]

        # Đảm bảo trường dynamic_choices không còn nữa và thay thế bằng enum
        assert "dynamic_choices" not in status_prop
        assert "enum" in status_prop

        # Enum của status PurchaseOrder phải chứa các giá trị thực tế của model
        expected_statuses = [
            "draft",
            "pending",
            "paid_unshipped",
            "shipped_unpaid",
            "completed",
            "cancel_pending",
            "cancelled",
        ]
        assert set(status_prop["enum"]) == set(expected_statuses)
