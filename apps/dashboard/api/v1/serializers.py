from rest_framework import serializers


class WidgetMetadataSerializer(serializers.Serializer):
    code = serializers.CharField()
    title = serializers.CharField()
    type = serializers.CharField()
    size = serializers.CharField()
    quick_links = serializers.ListField(child=serializers.CharField())
