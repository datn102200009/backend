from abc import ABC, abstractmethod
from typing import Generator


class LLMProviderInterface(ABC):
    """
    Interface cho tất cả LLM providers (Gemini, OpenAI, Anthropic...).

    Internal contract (được service layer consume):
    - Input: messages (list[dict]), tools_schema (list[dict])
    - Output: Generator yielding events: content_delta, tool_call_delta, message_done, error
    """

    @abstractmethod
    def chat_stream(self, *, messages: list[dict], tools_schema: list[dict]) -> Generator[dict, None, None]:
        """Stream LLM response. Yield events với format chuẩn."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Tên provider (vd: 'gemini', 'openai') — dùng cho logging."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Tên model đang dùng (vd: 'gemini-3.1-flash-lite')."""
        pass
