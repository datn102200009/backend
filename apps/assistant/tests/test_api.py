from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.inventory.tests.factories import UserFactory


@pytest.mark.django_db
class TestChatbotAPI:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("assistant_v1:chat_message_send")

    def test_send_message_requires_auth(self):
        response = self.client.post(self.url, {"content": "Hello"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("apps.assistant.services.chat_send_message")
    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_send_message_returns_sse_stream(self, mock_check, mock_chat):
        mock_check.return_value = None
        user = UserFactory()
        self.client.force_authenticate(user=user)

        mock_chat.return_value = [
            {"event": "message_start", "role": "assistant"},
            {"event": "content_delta", "delta": "Mock response"},
            {"event": "message_done", "finish_reason": "stop"},
        ]

        response = self.client.post(self.url, {"content": "Hello"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/event-stream"

        # Đọc dữ liệu stream
        content = b"".join(response.streaming_content).decode("utf-8")
        assert "event: message_start" in content
        assert "event: content_delta" in content
        assert "event: message_done" in content
