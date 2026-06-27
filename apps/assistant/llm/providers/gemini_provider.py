import json
import logging
from typing import Generator

from django.conf import settings
from google import genai
from google.genai import types

from .base import LLMProviderInterface

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProviderInterface):
    """Gemini provider dùng native google-genai SDK (KHÔNG qua OpenAI-compatible)."""

    def __init__(self):
        # Sẽ raise ImproperlyConfigured nếu thiếu API key trong thực tế,
        # nhưng để tránh crash trong tests/dev khi mock, cho phép fallback empty string
        api_key = getattr(settings, "GEMINI_API_KEY", "")
        self._client = genai.Client(api_key=api_key)
        self._model = getattr(settings, "GEMINI_MODEL", "gemini-3.1-flash-lite")

    def get_provider_name(self) -> str:
        return "gemini"

    def get_model_name(self) -> str:
        return self._model

    def chat_stream(self, *, messages: list[dict], tools_schema: list[dict]) -> Generator[dict, None, None]:
        """Stream LLM response. Yield events với format chuẩn."""
        try:
            # 1. Convert messages → Gemini format
            system_instruction, contents = self._convert_messages(messages)

            # 2. Convert tools_schema → Gemini Tool
            gemini_tools = self._convert_tools(tools_schema) if tools_schema else None

            # 3. Convert Pydantic objects -> raw dicts để tùy biến cấu trúc JSON payload
            contents_dict = []
            for c in contents:
                c_dict = c.model_dump(exclude_none=True)
                # Đính kèm thought_signature bypass cho các function_call parts của model role
                if c_dict.get("role") == "model" and "parts" in c_dict:
                    for part in c_dict["parts"]:
                        if "function_call" in part:
                            part["thought_signature"] = "skip_thought_signature_validator"
                contents_dict.append(c_dict)

            payload = {
                "contents": contents_dict,
                "generationConfig": {
                    "maxOutputTokens": getattr(settings, "GEMINI_MAX_TOKENS", 2000),
                },
            }

            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            if gemini_tools:
                payload["tools"] = [t.model_dump(exclude_none=True) for t in gemini_tools]

            # 4. Gọi REST API trực tiếp qua _api_client để bypass validator Pydantic của SDK
            path = f"models/{self._model}:generateContent"
            response_dict = self._client._api_client.request("post", path, payload)

            # 5. Parse response thô ngược về Pydantic object sử dụng phương thức của SDK
            response = types.GenerateContentResponse._from_response(response=response_dict, kwargs={})

            yield from self._process_chunk(response)

        except Exception as e:
            logger.exception("Gemini API call failed")
            yield {"event": "error", "code": "INTERNAL_ERROR", "message": str(e)}

    def _convert_messages(self, messages: list[dict]) -> tuple[str | None, list]:
        """Convert internal message format → Gemini format."""
        system_instruction = None
        contents = []
        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=content)],
                    )
                )
            elif role == "assistant":
                # Nếu assistant có tool_calls (round tiếp theo), chuyển thành function_call parts
                if msg.get("tool_calls"):
                    parts = []
                    if content:
                        parts.append(types.Part(text=content))
                    for tc in msg["tool_calls"]:
                        # Lấy args từ arguments (string/dict)
                        args_raw = tc["function"]["arguments"]
                        if isinstance(args_raw, str):
                            try:
                                args = json.loads(args_raw) if args_raw else {}
                            except json.JSONDecodeError:
                                args = {}
                        else:
                            args = args_raw or {}
                        parts.append(
                            types.Part(
                                function_call=types.FunctionCall(
                                    name=tc["function"]["name"],
                                    args=args,
                                )
                            )
                        )
                    contents.append(types.Content(role="model", parts=parts))
                else:
                    contents.append(
                        types.Content(
                            role="model",
                            parts=[types.Part(text=content)],
                        )
                    )
            elif role == "tool":
                tool_name = msg.get("name") or msg.get("tool_name") or ""
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=tool_name,
                                    response={"result": content},
                                )
                            )
                        ],
                    )
                )
        return system_instruction, contents

    def _convert_tools(self, tools_schema: list[dict]) -> list[types.Tool]:
        """Convert OpenAI tool format → Gemini Tool format."""
        declarations = []
        for tool in tools_schema:
            if tool.get("type") == "function":
                fn = tool["function"]
                declarations.append(
                    types.FunctionDeclaration(
                        name=fn["name"],
                        description=fn["description"],
                        parameters=fn.get("parameters", {}),
                    )
                )
        return [types.Tool(function_declarations=declarations)] if declarations else []

    def _process_chunk(self, chunk) -> Generator[dict, None, None]:
        """Process 1 chunk từ Gemini stream → yield internal events."""
        # Extract text content
        if chunk.candidates:
            for candidate in chunk.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if part.text:
                            yield {"event": "content_delta", "delta": part.text}
                        if part.function_call:
                            fc = part.function_call
                            yield {
                                "event": "tool_call_delta",
                                "tool_call_id": f"call_{fc.name}_{id(fc)}",  # Gemini không có tool_call_id riêng
                                "tool_name": fc.name,
                                "args_delta": json.dumps(dict(fc.args or {}), ensure_ascii=False),
                            }

        # Extract finish reason + usage
        if chunk.candidates and chunk.candidates[0].finish_reason:
            finish_reason = str(chunk.candidates[0].finish_reason)
            usage = {}
            if chunk.usage_metadata:
                usage = {
                    "prompt_tokens": chunk.usage_metadata.prompt_token_count or 0,
                    "completion_tokens": chunk.usage_metadata.candidates_token_count or 0,
                    "total_tokens": chunk.usage_metadata.total_token_count or 0,
                }
            yield {"event": "message_done", "finish_reason": finish_reason, "usage": usage}
