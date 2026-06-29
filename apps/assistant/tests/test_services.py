from unittest.mock import MagicMock, patch

import pytest

from apps.assistant.services import chat_send_message
from apps.inventory.tests.factories import ItemFactory, UserFactory


@pytest.mark.django_db
class TestChatbotServices:
    def setup_method(self):
        self.user = UserFactory()

    @patch("apps.assistant.services.chat_stream")
    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_chat_send_message_yields_message_start_first(self, mock_check, mock_stream):
        mock_check.return_value = None
        mock_stream.return_value = [
            {"event": "content_delta", "delta": "Xin chào! "},
            {"event": "content_delta", "delta": "Tôi có thể giúp gì?"},
            {"event": "message_done", "finish_reason": "stop", "usage": {"prompt_tokens": 5, "completion_tokens": 10}},
        ]

        events = list(chat_send_message(user=self.user, user_content="Hello", conversation_history=[]))

        assert events[0]["event"] == "message_start"
        assert events[0]["role"] == "assistant"
        assert events[1]["event"] == "content_delta"
        assert events[1]["delta"] == "Xin chào! "
        assert events[3]["event"] == "message_done"
        assert events[3]["finish_reason"] == "stop"

    @patch("apps.assistant.services.chat_stream")
    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_chat_send_message_handles_tool_call_loop(self, mock_check, mock_stream):
        mock_check.return_value = None
        ItemFactory(item_code="ITEM-001", item_name="Sản phẩm test")

        round1_events = [
            {
                "event": "tool_call_delta",
                "tool_call_id": "call_1",
                "tool_name": "search_items",
                "args_delta": '{"query": ',
            },
            {
                "event": "tool_call_delta",
                "tool_call_id": "call_1",
                "tool_name": "search_items",
                "args_delta": '"test"}',
            },
            {
                "event": "message_done",
                "finish_reason": "tool_use",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        ]
        round2_events = [
            {"event": "content_delta", "delta": "Tìm thấy 1 sản phẩm."},
            {"event": "message_done", "finish_reason": "stop", "usage": {"prompt_tokens": 15, "completion_tokens": 10}},
        ]

        mock_stream.side_effect = [round1_events, round2_events]

        events = list(chat_send_message(user=self.user, user_content="Tìm test", conversation_history=[]))

        event_names = [e["event"] for e in events]
        assert "message_start" in event_names
        assert "tool_call_delta" in event_names
        assert "tool_result" in event_names
        assert "content_delta" in event_names
        assert "message_done" in event_names

    @patch("apps.assistant.services.chat_stream")
    @patch("apps.common.xlib.permissions.PermissionChecker.check_permission")
    def test_chat_send_message_max_tool_rounds_enforced(self, mock_check, mock_stream):
        mock_check.return_value = None

        tool_event = [
            {
                "event": "tool_call_delta",
                "tool_call_id": "call_1",
                "tool_name": "search_items",
                "args_delta": '{"query": "test"}',
            },
            {"event": "message_done", "finish_reason": "tool_use", "usage": None},
        ]
        mock_stream.side_effect = [tool_event, tool_event, tool_event, tool_event]

        events = list(chat_send_message(user=self.user, user_content="Tìm test", conversation_history=[]))
        done_event = events[-1]
        assert done_event["event"] == "message_done"
        assert done_event["finish_reason"] == "max_rounds"
