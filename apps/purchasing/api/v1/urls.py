from django.urls import path

from .views import (
    APAgingReportAPIView,
    LandedCostAllocateAPIView,
    PurchaseInvoiceDetailAPIView,
    PurchaseInvoiceListAPIView,
    PurchaseInvoiceVerifyAPIView,
    PurchaseOrderApproveAPIView,
    PurchaseOrderCancelAPIView,
    PurchaseOrderDetailUpdateDeleteAPIView,
    PurchaseOrderListCreateAPIView,
    PurchaseOrderReceiveAPIView,
    ShipmentDetailAPIView,
    ShipmentListCreateAPIView,
    TechnicalCertificationListCreateAPIView,
)

urlpatterns = [
    # QC QA Certifications
    path(
        "certifications/", TechnicalCertificationListCreateAPIView.as_view(), name="technical-certification-list-create"
    ),
    # Orders
    path("orders/", PurchaseOrderListCreateAPIView.as_view(), name="purchase-order-list-create"),
    path(
        "orders/<uuid:pk>/",
        PurchaseOrderDetailUpdateDeleteAPIView.as_view(),
        name="purchase-order-detail-update-delete",
    ),
    path("orders/<uuid:pk>/receive/", PurchaseOrderReceiveAPIView.as_view(), name="purchase-order-receive"),
    path("orders/<uuid:pk>/approve/", PurchaseOrderApproveAPIView.as_view(), name="purchase-order-approve"),
    path("orders/<uuid:pk>/cancel/", PurchaseOrderCancelAPIView.as_view(), name="purchase-order-cancel"),
    # Invoices
    path("invoices/", PurchaseInvoiceListAPIView.as_view(), name="purchase-invoice-list"),
    path("invoices/<uuid:pk>/", PurchaseInvoiceDetailAPIView.as_view(), name="purchase-invoice-detail"),
    path("invoices/<uuid:pk>/verify/", PurchaseInvoiceVerifyAPIView.as_view(), name="purchase-invoice-verify"),
    # Shipments & Landed Cost
    path("shipments/", ShipmentListCreateAPIView.as_view(), name="shipment-list-create"),
    path("shipments/<uuid:pk>/", ShipmentDetailAPIView.as_view(), name="shipment-detail"),
    path("shipments/allocate/", LandedCostAllocateAPIView.as_view(), name="landed-cost-allocate"),
    # Reports
    path("reports/ap-aging/", APAgingReportAPIView.as_view(), name="ap-aging-report"),
]
