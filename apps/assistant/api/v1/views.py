import json
import logging

from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated

from apps.assistant import services as assistant_services
from apps.assistant.serializers import ChatMessageInputSerializer
from apps.assistant.throttles import ChatbotRateThrottle
from apps.common.xlib.exceptions import PermissionException, ValidationException
from apps.common.xlib.permissions import PermissionChecker

logger = logging.getLogger(__name__)


@api_view(["POST"])
@throttle_classes([ChatbotRateThrottle])
@permission_classes([IsAuthenticated])
def chat_message_send_view(request):
    user = request.user

    # 1. RBAC gate
    PermissionChecker.check_permission(user, "common.use_chatbot")

    # 2. Validate input
    serializer = ChatMessageInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    validated = serializer.validated_data
    content = validated["content"]
    history = validated.get("conversation_history", [])

    # 3. SSE stream
    def event_stream():
        try:
            for event in assistant_services.chat_send_message(
                user=user,
                user_content=content,
                conversation_history=history,
            ):
                yield f"event: {event['event']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
        except PermissionException as e:
            yield f"event: error\ndata: {json.dumps({'code': 'PERMISSION_DENIED', 'message': str(e)}, ensure_ascii=False)}\n\n"
        except ValidationException as e:
            yield f"event: error\ndata: {json.dumps({'code': 'VALIDATION_ERROR', 'message': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Chatbot internal error")
            yield f"event: error\ndata: {json.dumps({'code': 'INTERNAL_ERROR', 'message': 'Lỗi hệ thống'}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
