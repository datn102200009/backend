from django.urls import path

from apps.dashboard.api.v1.views import WidgetBatchDataView, WidgetDataDetailView, WidgetMetadataListView

urlpatterns = [
    path("widgets/", WidgetMetadataListView.as_view(), name="widget-metadata-list"),
    path("widgets/batch-data/", WidgetBatchDataView.as_view(), name="widget-batch-data"),
    path("widgets/<str:widget_code>/", WidgetDataDetailView.as_view(), name="widget-data-detail"),
]
