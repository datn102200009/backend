from .providers.factory import get_provider


def chat_stream(*, messages: list[dict], tools_schema: list[dict]):
    """Wrapper gọi qua factory. Service layer chỉ cần import hàm này."""
    provider = get_provider()
    yield from provider.chat_stream(messages=messages, tools_schema=tools_schema)
