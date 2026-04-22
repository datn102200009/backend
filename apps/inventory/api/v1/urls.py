"""
URL routing for inventory API v1.
"""

from django.urls import path

from apps.inventory.api.v1 import views

app_name = "inventory_v1"

urlpatterns = [
    # Stock In (Nhập Kho)
    path(
        "stock-in/create/",
        views.stock_in_create_view,
        name="stock_in_create",
    ),
    path(
        "stock-in/<str:stock_entry_id>/approve/",
        views.stock_in_approve_view,
        name="stock_in_approve",
    ),
    # Stock Issue (Xuất Kho)
    path(
        "stock-issue/create/",
        views.stock_issue_for_manufacturing_view,
        name="stock_issue_create",
    ),
    path(
        "stock-issue/<str:stock_entry_id>/approve/",
        views.stock_issue_approve_view,
        name="stock_issue_approve",
    ),
    # Stock Transfer (Chuyển Kho)
    path(
        "stock-transfer/create/",
        views.stock_transfer_create_view,
        name="stock_transfer_create",
    ),
    path(
        "stock-transfer/<str:stock_entry_id>/approve/",
        views.stock_transfer_approve_view,
        name="stock_transfer_approve",
    ),
    # Stock Ledger & List
    path(
        "stock-ledger/balance/",
        views.stock_ledger_balance_view,
        name="stock_ledger_balance",
    ),
    path(
        "stock-entry/list/",
        views.stock_entry_list_view,
        name="stock_entry_list",
    ),
]
