from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.xlib.permissions import PermissionChecker
from apps.dashboard.api.v1.serializers import WidgetMetadataSerializer
from apps.dashboard.registry import WIDGETS_REGISTRY
from apps.dashboard.selectors import SELECTORS_MAP


class WidgetMetadataListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        allowed_widgets = []
        for code, config in WIDGETS_REGISTRY.items():
            if PermissionChecker.has_permission(user, config["permission"]):
                allowed_widgets.append(
                    {
                        "code": code,
                        "title": config["title"],
                        "type": config["type"],
                        "size": config["size"],
                        "quick_links": config["quick_links"],
                    }
                )

        serializer = WidgetMetadataSerializer(allowed_widgets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WidgetBatchDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        widget_codes_str = request.query_params.get("widgets", "")
        if widget_codes_str:
            widget_codes = [c.strip() for c in widget_codes_str.split(",") if c.strip()]
        else:
            # Auto-detect all allowed widgets
            widget_codes = [
                code
                for code, config in WIDGETS_REGISTRY.items()
                if PermissionChecker.has_permission(user, config["permission"])
            ]

        response_data = {}
        for code in widget_codes:
            config = WIDGETS_REGISTRY.get(code)
            if not config:
                response_data[code] = {"success": False, "error": f"Widget '{code}' does not exist in registry."}
                continue

            # Check permission
            if not PermissionChecker.has_permission(user, config["permission"]):
                response_data[code] = {
                    "success": False,
                    "error": f"User does not have permission: {config['permission']}",
                }
                continue

            selector_func = SELECTORS_MAP.get(code)
            if not selector_func:
                response_data[code] = {"success": False, "error": f"Selector for widget '{code}' is not implemented."}
                continue

            # Isolated execution block to prevent partial failures from crashing other widgets
            try:
                data = selector_func()
                total_count = getattr(data, "total_count", None)
                if total_count is None:
                    if isinstance(data, list):
                        total_count = len(data)
                    elif isinstance(data, dict):
                        if "total_count" in data:
                            total_count = data["total_count"]
                        elif "weeks" in data:
                            total_count = len(data["weeks"])

                widget_res = {"success": True, "data": data}
                if total_count is not None:
                    widget_res["total_count"] = total_count
                response_data[code] = widget_res
            except Exception as e:
                response_data[code] = {"success": False, "error": str(e)}

        return Response(response_data, status=status.HTTP_200_OK)


class WidgetDataDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, widget_code, *args, **kwargs):
        config = WIDGETS_REGISTRY.get(widget_code)
        if not config:
            return Response({"error": f"Widget '{widget_code}' not found"}, status=status.HTTP_404_NOT_FOUND)

        PermissionChecker.check_permission(request.user, config["permission"])

        selector_func = SELECTORS_MAP.get(widget_code)
        if not selector_func:
            return Response(
                {"error": f"Selector for widget '{widget_code}' is not implemented."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        # For single widget retrieval, let the exception propagate to the custom exception handler,
        # or handle it gracefully to return a standardized success/failure JSON matching the batch shape.
        try:
            sel_kwargs = {}
            if widget_code == "inventory_pending_entries":
                purpose = request.query_params.get("purpose")
                if purpose:
                    sel_kwargs["purpose"] = purpose

            data = selector_func(**sel_kwargs)
            total_count = getattr(data, "total_count", None)
            if total_count is None:
                if isinstance(data, list):
                    total_count = len(data)
                elif isinstance(data, dict):
                    if "total_count" in data:
                        total_count = data["total_count"]
                    elif "weeks" in data:
                        total_count = len(data["weeks"])

            res_payload = {"success": True, "data": data}
            if total_count is not None:
                res_payload["total_count"] = total_count
            return Response(res_payload, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
