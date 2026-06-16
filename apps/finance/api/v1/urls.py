from django.urls import path

from .salary_slip_views import (
    SalarySlipApproveAPIView,
    SalarySlipBulkApprovePayAPIView,
    SalarySlipPayAPIView,
    SalarySlipRejectAPIView,
)
from .views import (
    CashFlowApproveAPIView,
    CashFlowDetailAPIView,
    CashFlowListCreateAPIView,
    CashFlowRejectAPIView,
    DepreciationLogListAPIView,
    DepreciationRunAPIView,
    FixedAssetDetailAPIView,
    FixedAssetListCreateAPIView,
    FixedAssetRequestDisposeAPIView,
    PurchaseInvoiceDetailAPIView,
    PurchaseInvoiceListAPIView,
    PurchaseInvoicePayAPIView,
    SalesInvoiceCollectAPIView,
    SalesInvoiceDetailAPIView,
    SalesInvoiceListAPIView,
)

urlpatterns = [
    path("cash-flows/", CashFlowListCreateAPIView.as_view(), name="cash-flow-list-create"),
    path("cash-flows/<uuid:pk>/", CashFlowDetailAPIView.as_view(), name="cash-flow-detail"),
    path("cash-flows/<uuid:pk>/approve/", CashFlowApproveAPIView.as_view(), name="cash-flow-approve"),
    path("cash-flows/<uuid:pk>/reject/", CashFlowRejectAPIView.as_view(), name="cash-flow-reject"),
    path("fixed-assets/", FixedAssetListCreateAPIView.as_view(), name="fixed-asset-list-create"),
    path("fixed-assets/depreciation/", DepreciationRunAPIView.as_view(), name="depreciation-run"),
    path("fixed-assets/depreciation-logs/", DepreciationLogListAPIView.as_view(), name="depreciation-log-list"),
    path("fixed-assets/<uuid:pk>/", FixedAssetDetailAPIView.as_view(), name="fixed-asset-detail"),
    path(
        "fixed-assets/<uuid:pk>/request-dispose/",
        FixedAssetRequestDisposeAPIView.as_view(),
        name="fixed-asset-request-dispose",
    ),
    # Purchase Invoices
    path("invoices/purchase/", PurchaseInvoiceListAPIView.as_view(), name="purchase-invoice-list"),
    path("invoices/purchase/<uuid:pk>/", PurchaseInvoiceDetailAPIView.as_view(), name="purchase-invoice-detail"),
    path("invoices/purchase/<uuid:pk>/pay/", PurchaseInvoicePayAPIView.as_view(), name="purchase-invoice-pay"),
    # Sales Invoices
    path("invoices/sales/", SalesInvoiceListAPIView.as_view(), name="sales-invoice-list"),
    path("invoices/sales/<uuid:pk>/", SalesInvoiceDetailAPIView.as_view(), name="sales-invoice-detail"),
    path("invoices/sales/<uuid:pk>/collect/", SalesInvoiceCollectAPIView.as_view(), name="sales-invoice-collect"),
    # Salary Slips (Finance Approval & Payment)
    path(
        "salary-slips/bulk-approve-pay/", SalarySlipBulkApprovePayAPIView.as_view(), name="salary-slip-bulk-approve-pay"
    ),
    path("salary-slips/<uuid:id>/approve/", SalarySlipApproveAPIView.as_view(), name="salary-slip-approve"),
    path("salary-slips/<uuid:id>/reject/", SalarySlipRejectAPIView.as_view(), name="salary-slip-reject"),
    path("salary-slips/<uuid:id>/pay/", SalarySlipPayAPIView.as_view(), name="salary-slip-pay"),
]
