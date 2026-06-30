# flake8: noqa
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    required_permission: str
    parameters_schema: dict
    handler: Callable = field(repr=False)


# ===== TOOL_HANDLERS — import từ tool_handlers.py =====
from apps.assistant.llm.tool_handlers import (
    get_business_workflow_handler,
    get_customer_debt_handler,
    get_document_detail_handler,
    get_inventory_balance_handler,
    get_item_detail_handler,
    list_boms_handler,
    list_cash_flows_handler,
    list_customers_handler,
    list_fixed_assets_handler,
    list_leave_requests_handler,
    list_purchase_orders_handler,
    list_sales_orders_handler,
    list_stock_entries_handler,
    list_suppliers_handler,
    list_system_logs_handler,
    list_work_orders_handler,
    search_employees_handler,
    search_items_handler,
    search_warehouses_handler,
)

TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "search_items": ToolDefinition(
        name="search_items",
        description="Tìm kiếm sản phẩm/vật tư theo tên hoặc mã. Trả về danh sách tối đa 20 kết quả.",
        required_permission="master_data.view_item",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "maxLength": 100, "description": "Từ khoá tìm kiếm (mã hoặc tên)"},
                "status": {"type": "string", "enum": ["active", "inactive"], "description": "Lọc theo trạng thái"},
            },
            "required": ["query"],
        },
        handler=search_items_handler,
    ),
    "get_item_detail": ToolDefinition(
        name="get_item_detail",
        description="Lấy chi tiết 1 sản phẩm/vật tư theo mã: tên, UOM, nhóm, ngưỡng tồn tối thiểu.",
        required_permission="master_data.view_item",
        parameters_schema={
            "type": "object",
            "properties": {
                "item_code": {"type": "string", "maxLength": 50},
            },
            "required": ["item_code"],
        },
        handler=get_item_detail_handler,
    ),
    "get_inventory_balance": ToolDefinition(
        name="get_inventory_balance",
        description="Xem số lượng tồn kho hiện tại của 1 sản phẩm tại 1 kho cụ thể.",
        required_permission="inventory.view_inventory",
        parameters_schema={
            "type": "object",
            "properties": {
                "item_code": {"type": "string", "maxLength": 50},
                "warehouse_code": {
                    "type": "string",
                    "maxLength": 50,
                    "description": "Optional. Nếu không truyền sẽ trả về tất cả kho.",
                },
            },
            "required": ["item_code"],
        },
        handler=get_inventory_balance_handler,
    ),
    "search_warehouses": ToolDefinition(
        name="search_warehouses",
        description="Liệt kê các kho trong hệ thống.",
        required_permission="inventory.view_warehouse",
        parameters_schema={"type": "object", "properties": {}, "required": []},
        handler=search_warehouses_handler,
    ),
    "list_stock_entries": ToolDefinition(
        name="list_stock_entries",
        description="Liệt kê phiếu nhập/xuất kho theo trạng thái (draft, submitted, cancelled).",
        required_permission="inventory.view_stockentry",
        parameters_schema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "dynamic_choices": ("inventory", "StockEntry", "status"),
                    "default": "submitted",
                },
                "purpose": {"type": "string", "dynamic_choices": ("inventory", "StockEntry", "purpose")},
                "start_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Optional. Ngày bắt đầu lọc (YYYY-MM-DD)",
                },
                "end_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Optional. Ngày kết thúc lọc (YYYY-MM-DD)",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
        },
        handler=list_stock_entries_handler,
    ),
    "search_employees": ToolDefinition(
        name="search_employees",
        description="Tìm nhân viên theo tên hoặc mã. Trả về thông tin công khai (không bao gồm lương).",
        required_permission="hrm.view_employee",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "maxLength": 100, "description": "Tên hoặc mã NV"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
            "required": ["query"],
        },
        handler=search_employees_handler,
    ),
    "list_leave_requests": ToolDefinition(
        name="list_leave_requests",
        description="Liệt kê đơn nghỉ phép. Có thể lọc theo trạng thái hoặc nhân viên cụ thể.",
        required_permission="hrm.view_leaverequest",
        parameters_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "dynamic_choices": ("hrm", "LeaveRequest", "status")},
                "employee_code": {"type": "string", "maxLength": 50},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
        },
        handler=list_leave_requests_handler,
    ),
    "list_sales_orders": ToolDefinition(
        name="list_sales_orders",
        description="Liệt kê đơn bán hàng theo trạng thái hoặc khách hàng.",
        required_permission="sales.view_salesorder",
        parameters_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "dynamic_choices": ("sales", "SalesOrder", "status")},
                "customer_id": {"type": "string", "format": "uuid"},
                "start_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Optional. Ngày bắt đầu lọc (YYYY-MM-DD)",
                },
                "end_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Optional. Ngày kết thúc lọc (YYYY-MM-DD)",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
        },
        handler=list_sales_orders_handler,
    ),
    "get_customer_debt": ToolDefinition(
        name="get_customer_debt",
        description="Xem công nợ hiện tại (số tiền khách hàng đang nợ) của 1 khách hàng cụ thể.",
        required_permission="crm.view_customer",
        parameters_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "format": "uuid"},
            },
            "required": ["customer_id"],
        },
        handler=get_customer_debt_handler,
    ),
    "list_customers": ToolDefinition(
        name="list_customers",
        description="Liệt kê danh sách khách hàng (tên, mã, nhóm, hạn mức tín dụng).",
        required_permission="crm.view_customer",
        parameters_schema={
            "type": "object",
            "properties": {
                "search": {"type": "string", "maxLength": 100},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
        },
        handler=list_customers_handler,
    ),
    "list_purchase_orders": ToolDefinition(
        name="list_purchase_orders",
        description="Liệt kê đơn mua hàng theo trạng thái hoặc nhà cung cấp.",
        required_permission="purchasing.view_purchaseorder",
        parameters_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "dynamic_choices": ("purchasing", "PurchaseOrder", "status")},
                "supplier_id": {"type": "string", "format": "uuid"},
                "start_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Optional. Ngày bắt đầu lọc (YYYY-MM-DD)",
                },
                "end_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Optional. Ngày kết thúc lọc (YYYY-MM-DD)",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
        },
        handler=list_purchase_orders_handler,
    ),
    "list_suppliers": ToolDefinition(
        name="list_suppliers",
        description="Liệt kê danh sách nhà cung cấp.",
        required_permission="procurement.view_supplier",
        parameters_schema={
            "type": "object",
            "properties": {
                "search": {"type": "string", "maxLength": 100},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
        },
        handler=list_suppliers_handler,
    ),
    "list_work_orders": ToolDefinition(
        name="list_work_orders",
        description="Liệt kê lệnh sản xuất theo trạng thái (pending, in_progress, completed, cancelled).",
        required_permission="manufacturing.view_workorder",
        parameters_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "dynamic_choices": ("master_data", "WorkOrder", "status")},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
        },
        handler=list_work_orders_handler,
    ),
    "list_boms": ToolDefinition(
        name="list_boms",
        description="Liệt kê danh sách BOM (Bill of Materials) đang active.",
        required_permission="manufacturing.view_bom",
        parameters_schema={
            "type": "object",
            "properties": {
                "search": {"type": "string", "maxLength": 100},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
        },
        handler=list_boms_handler,
    ),
    "list_cash_flows": ToolDefinition(
        name="list_cash_flows",
        description="Liệt kê giao dịch thu/chi theo trạng thái (draft, approved, posted).",
        required_permission="finance.view_cashflow",
        parameters_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "dynamic_choices": ("finance", "CashFlowTransaction", "status")},
                "start_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Optional. Ngày bắt đầu lọc (YYYY-MM-DD)",
                },
                "end_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Optional. Ngày kết thúc lọc (YYYY-MM-DD)",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
        },
        handler=list_cash_flows_handler,
    ),
    "list_fixed_assets": ToolDefinition(
        name="list_fixed_assets",
        description="Liệt kê tài sản cố định theo trạng thái (active, disposed, fully_depreciated).",
        required_permission="finance.view_fixedasset",
        parameters_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "dynamic_choices": ("finance", "FixedAsset", "status")},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
        },
        handler=list_fixed_assets_handler,
    ),
    "get_document_detail": ToolDefinition(
        name="get_document_detail",
        description="Lấy chi tiết đầy đủ thông tin của một tài liệu hoặc thực thể trong hệ thống (đơn mua/bán hàng, phiếu kho, hóa đơn, sản phẩm, nhân viên, nhật ký hoạt động...) theo ID.",
        required_permission="common.use_chatbot",
        parameters_schema={
            "type": "object",
            "properties": {
                "model_name": {
                    "type": "string",
                    "enum": [
                        "purchase_order",
                        "sales_order",
                        "stock_entry",
                        "purchase_invoice",
                        "sales_invoice",
                        "cash_flow",
                        "item",
                        "employee",
                        "warehouse",
                        "supplier",
                        "customer",
                        "work_order",
                        "bom",
                        "leave_request",
                        "system_log",
                    ],
                    "description": "Tên loại đối tượng cần lấy chi tiết",
                },
                "document_id": {
                    "type": "string",
                    "description": "ID dạng UUID hoặc Mã định danh (Code/Name) của đối tượng",
                },
            },
            "required": ["model_name", "document_id"],
        },
        handler=get_document_detail_handler,
    ),
    "get_business_workflow": ToolDefinition(
        name="get_business_workflow",
        description="Lấy tài liệu hướng dẫn quy trình nghiệp vụ (workflow) và thao tác giao diện thực tế của hệ thống ERP Xuân Hòa.",
        required_permission="common.use_chatbot",
        parameters_schema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": [
                        "system_accounts",
                        "manufacturing_bom",
                        "inventory",
                        "purchasing_sales",
                        "finance_accounting",
                        "hrm_payroll",
                    ],
                    "description": "Chủ đề nghiệp vụ cần tra cứu quy trình",
                }
            },
            "required": ["topic"],
        },
        handler=get_business_workflow_handler,
    ),
    "list_system_logs": ToolDefinition(
        name="list_system_logs",
        description="Liệt kê nhật ký hoạt động hệ thống (system logs). Hỗ trợ tìm kiếm theo từ khoá (mã đơn hàng, tên người thực hiện...), lọc theo khoảng ngày, lọc theo hành động.",
        required_permission="common.use_chatbot",
        parameters_schema={
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "Từ khoá tìm kiếm (ví dụ: tên người thực hiện, mã đơn hàng, UUID, hành động...)",
                },
                "action": {
                    "type": "string",
                    "description": "Lọc theo hành động (ví dụ: create, update, delete, approve...)",
                },
                "start_date": {"type": "string", "format": "date", "description": "Ngày bắt đầu lọc (YYYY-MM-DD)"},
                "end_date": {"type": "string", "format": "date", "description": "Ngày kết thúc lọc (YYYY-MM-DD)"},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 20,
                    "description": "Số lượng bản ghi tối đa trả về",
                },
            },
        },
        handler=list_system_logs_handler,
    ),
}


def list_tools_for_llm() -> list[dict]:
    """Trả về JSON Schema cho tool format, tự động resolve dynamic choices từ Django Model."""
    import copy

    from django.apps import apps

    tools = []
    for t in TOOL_REGISTRY.values():
        # Copy schema để không ghi đè làm hỏng định nghĩa gốc trong memory
        schema = copy.deepcopy(t.parameters_schema)
        properties = schema.get("properties", {})

        for prop_name, prop_data in properties.items():
            if isinstance(prop_data, dict) and "dynamic_choices" in prop_data:
                app_label, model_name, field_name = prop_data["dynamic_choices"]
                try:
                    model = apps.get_model(app_label, model_name)
                    field = model._meta.get_field(field_name)
                    if field and field.choices:
                        prop_data["enum"] = [c[0] for c in field.choices]
                except Exception:
                    # Fallback/bỏ qua nếu không load được Model (vd trong unit test chưa setup app)
                    pass
                # Xoá marker dynamic_choices để không làm lỗi JSON schema gửi cho LLM
                del prop_data["dynamic_choices"]

        tools.append(
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": schema,
                },
            }
        )
    return tools
