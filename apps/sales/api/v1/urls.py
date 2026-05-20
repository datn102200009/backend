from django.urls import path

from .views import (
    SalesInvoiceDetailAPIView,
    SalesInvoiceListAPIView,
    SalesOrderApproveAPIView,
    SalesOrderDeliverAPIView,
    SalesOrderDetailUpdateDeleteAPIView,
    SalesOrderListCreateAPIView,
)

urlpatterns = [
    # Orders
    path("orders/", SalesOrderListCreateAPIView.as_view(), name="sales-order-list-create"),
    path("orders/<uuid:pk>/", SalesOrderDetailUpdateDeleteAPIView.as_view(), name="sales-order-detail-update-delete"),
    path("orders/<uuid:pk>/deliver/", SalesOrderDeliverAPIView.as_view(), name="sales-order-deliver"),
    path("orders/<uuid:pk>/approve/", SalesOrderApproveAPIView.as_view(), name="sales-order-approve"),
    # Invoices
    path("invoices/", SalesInvoiceListAPIView.as_view(), name="sales-invoice-list"),
    path("invoices/<uuid:pk>/", SalesInvoiceDetailAPIView.as_view(), name="sales-invoice-detail"),
]
