from django.urls import path

from .views import CustomerDetailUpdateDeleteAPIView, CustomerListCreateAPIView

urlpatterns = [
    path("customers/", CustomerListCreateAPIView.as_view(), name="customer-list-create"),
    path("customers/<uuid:pk>/", CustomerDetailUpdateDeleteAPIView.as_view(), name="customer-detail-update-delete"),
]
