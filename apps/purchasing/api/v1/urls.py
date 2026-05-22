from django.urls import path

from .views import (
    PurchaseInvoiceDetailAPIView,
    PurchaseInvoiceListAPIView,
    PurchaseOrderApproveAPIView,
    PurchaseOrderDetailUpdateDeleteAPIView,
    PurchaseOrderListCreateAPIView,
    PurchaseOrderReceiveAPIView,
)

urlpatterns = [
    # Orders
    path("orders/", PurchaseOrderListCreateAPIView.as_view(), name="purchase-order-list-create"),
    path(
        "orders/<uuid:pk>/",
        PurchaseOrderDetailUpdateDeleteAPIView.as_view(),
        name="purchase-order-detail-update-delete",
    ),
    path("orders/<uuid:pk>/receive/", PurchaseOrderReceiveAPIView.as_view(), name="purchase-order-receive"),
    path("orders/<uuid:pk>/approve/", PurchaseOrderApproveAPIView.as_view(), name="purchase-order-approve"),
    # Invoices
    path("invoices/", PurchaseInvoiceListAPIView.as_view(), name="purchase-invoice-list"),
    path("invoices/<uuid:pk>/", PurchaseInvoiceDetailAPIView.as_view(), name="purchase-invoice-detail"),
]
