import json
import logging
import time
from typing import Generator

from django.conf import settings

from apps.assistant.llm.client import chat_stream
from apps.assistant.llm.prompts import build_system_prompt
from apps.assistant.llm.tool_registry import TOOL_REGISTRY, list_tools_for_llm
from apps.common.xlib.exceptions import PermissionException, ValidationException

logger = logging.getLogger(__name__)

# Log lưu trữ các tool call phục vụ debug và audit (trong bộ nhớ)
TOOL_CALLS_LOG: list[dict] = []


def chat_send_message(
    *,
    user,
    user_content: str,
    conversation_history: list,
) -> Generator[dict, None, None]:
    """
    Orchestrator quản lý hội thoại chatbot stateless hỗ trợ gọi tool (tool calling).
    Thực hiện gửi/nhận SSE stream với LLM Provider được cấu hình.
    """
    # 1. Validate đầu vào
    max_chars = getattr(settings, "CHATBOT_USER_MESSAGE_MAX_CHARS", 4000)
    if len(user_content) > max_chars:
        raise ValidationException(f"Tin nhắn vượt quá {max_chars} ký tự.")

    max_history = getattr(settings, "LLM_MAX_HISTORY_MESSAGES", 10)
    if len(conversation_history) > max_history:
        raise ValidationException(f"conversation_history tối đa {max_history} turn.")

    # 2. Xây dựng tin nhắn hệ thống dựa trên quyền của User
    tools_schema = list_tools_for_llm()
    system_prompt = build_system_prompt(user, tools_schema)
    messages = [
        {"role": "system", "content": system_prompt},
        *conversation_history,
        {"role": "user", "content": user_content},
    ]

    # 3. Loop gọi Tool (Tối đa MAX_TOOL_ROUNDS vòng)
    max_tool_rounds = getattr(settings, "LLM_MAX_TOOL_ROUNDS", 3)
    final_content = ""
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    yield {"event": "message_start", "role": "assistant"}

    for round_idx in range(max_tool_rounds + 1):
        tool_calls_buffer: dict[str, dict] = {}
        round_content = ""

        # Gọi LLM Client Stream
        for event in chat_stream(messages=messages, tools_schema=tools_schema):
            if event["event"] == "error":
                yield event
                return
            elif event["event"] == "content_delta":
                round_content += event["delta"]
                yield event
            elif event["event"] == "tool_call_delta":
                tc_id = event["tool_call_id"]
                if tc_id not in tool_calls_buffer:
                    tool_calls_buffer[tc_id] = {"name": event["tool_name"], "args": ""}
                tool_calls_buffer[tc_id]["args"] += event["args_delta"] or ""
                yield event
            elif event["event"] == "message_done":
                final_content += round_content
                if "usage" in event and event["usage"]:
                    total_usage["prompt_tokens"] += event["usage"].get("prompt_tokens", 0)
                    total_usage["completion_tokens"] += event["usage"].get("completion_tokens", 0)

                # Nếu không có tool call hoặc LLM chủ động dừng -> hoàn tất
                if not tool_calls_buffer or event["finish_reason"] == "stop":
                    yield {
                        "event": "message_done",
                        "finish_reason": event["finish_reason"],
                        "token_input": total_usage["prompt_tokens"],
                        "token_output": total_usage["completion_tokens"],
                    }
                    return

        # Nếu vòng stream này kết thúc mà không có bất kỳ tool call nào
        if not tool_calls_buffer:
            break

        # 4. Ghi nhận Assistant's tool_calls vào lịch sử để chuẩn bị cho round tiếp theo
        messages.append(
            {
                "role": "assistant",
                "content": round_content,
                "tool_calls": [
                    {"id": tc_id, "type": "function", "function": {"name": tc["name"], "arguments": tc["args"]}}
                    for tc_id, tc in tool_calls_buffer.items()
                ],
            }
        )

        # Xử lý tuần tự các tool calls trong buffer
        tool_results = []
        for tc_id, tc in tool_calls_buffer.items():
            tool_name = tc["name"]
            try:
                args = json.loads(tc["args"]) if tc["args"] else {}
            except json.JSONDecodeError:
                args = {}

            # Kiểm tra whitelist cứng
            tool_def = TOOL_REGISTRY.get(tool_name)
            if not tool_def:
                result = {"error": "TOOL_NOT_ALLOWED", "detail": f"Tool '{tool_name}' không tồn tại trong whitelist"}
                yield {"event": "tool_result", "tool_call_id": tc_id, "tool_name": tool_name, "error": result["error"]}
                tool_results.append(
                    {"tool_call_id": tc_id, "tool_name": tool_name, "content": json.dumps(result, ensure_ascii=False)}
                )
                _log_tool_call(user, tool_name, args, result, 0, "TOOL_NOT_ALLOWED")
                continue

            # Thực thi tool handler với đo lường thời gian
            start = time.time()
            try:
                result = tool_def.handler(args, user)
                error_msg = ""
            except PermissionException as e:
                result = {"error": "PERMISSION_DENIED", "detail": str(e)}
                error_msg = str(e)
            except ValidationException as e:
                result = {"error": "VALIDATION_ERROR", "detail": str(e)}
                error_msg = str(e)
            except Exception as e:
                logger.exception(f"Tool {tool_name} failed during execution")
                result = {"error": "TOOL_EXECUTION_FAILED", "detail": str(e)}
                error_msg = str(e)
            duration_ms = int((time.time() - start) * 1000)

            _log_tool_call(user, tool_name, args, result, duration_ms, error_msg)

            # Tránh LLM context limit overflow bằng cách giới hạn kích thước kết quả
            result_str = json.dumps(result, ensure_ascii=False)
            if len(result_str) > 8000:
                result_str = json.dumps(
                    {"summary": "Kết quả quá lớn, đã tự động rút gọn", "preview": result_str[:8000]}, ensure_ascii=False
                )

            yield {
                "event": "tool_result",
                "tool_call_id": tc_id,
                "tool_name": tool_name,
                "result_preview": str(result)[:200],
            }
            tool_results.append({"tool_call_id": tc_id, "tool_name": tool_name, "content": result_str})

        # Gửi tất cả kết quả của tool call về LLM ở round tiếp theo
        for tr in tool_results:
            messages.append(
                {"role": "tool", "tool_call_id": tr["tool_call_id"], "name": tr["tool_name"], "content": tr["content"]}
            )

    # Nếu vượt quá tối đa số vòng gọi tool mà vẫn chưa xong
    yield {
        "event": "message_done",
        "finish_reason": "max_rounds",
        "token_input": total_usage["prompt_tokens"],
        "token_output": total_usage["completion_tokens"],
    }


def _log_tool_call(user, tool_name, args, result, duration_ms, error):
    """Ghi log và audit cho các lượt gọi tool (CloudWatch logs)."""
    log_entry = {
        "user_id": user.id,
        "username": user.username,
        "tool_name": tool_name,
        "args": args,
        "result_keys": list(result.keys()) if isinstance(result, dict) else None,
        "duration_ms": duration_ms,
        "error": error,
    }
    if error:
        logger.warning(f"CHATBOT_TOOL_CALL: {log_entry}")
    else:
        logger.info(f"CHATBOT_TOOL_CALL: {log_entry}")

    TOOL_CALLS_LOG.append(log_entry)
    if len(TOOL_CALLS_LOG) > 1000:
        TOOL_CALLS_LOG.pop(0)
