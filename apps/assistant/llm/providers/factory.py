from django.conf import settings

from .base import LLMProviderInterface

_provider_instance: LLMProviderInterface | None = None


def get_provider() -> LLMProviderInterface:
    """Factory: trả về singleton instance của provider được chọn qua settings."""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    provider_name = getattr(settings, "LLM_PROVIDER", "gemini").lower()

    if provider_name == "gemini":
        from .gemini_provider import GeminiProvider

        _provider_instance = GeminiProvider()
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider_name}")

    return _provider_instance


def reset_provider_cache():
    """Dùng cho test hoặc khi đổi config runtime."""
    global _provider_instance
    _provider_instance = None
