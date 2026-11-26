"""Provider registry — look providers up by name.

Only free-tier providers are registered: Gemini (native video understanding,
no credit card) and Groq (fast, free, transcript-based). Anthropic, Together
AI and Twelve Labs were removed - none of them offer an ongoing free tier.
"""

from providers.base import AnalysisResult, BaseProvider, ProviderError
from providers.gemini_provider import GeminiProvider
from providers.groq_provider import GroqProvider

PROVIDERS: dict[str, BaseProvider] = {
    "gemini": GeminiProvider(),
    "groq": GroqProvider(),
}


def get_provider(name: str) -> BaseProvider:
    provider = PROVIDERS.get((name or "").lower())
    if provider is None:
        raise ProviderError(f"Unknown provider '{name}'. Available: {', '.join(PROVIDERS)}")
    return provider


def configured_providers() -> list[str]:
    return [name for name, provider in PROVIDERS.items() if provider.is_configured()]


__all__ = [
    "PROVIDERS",
    "get_provider",
    "configured_providers",
    "AnalysisResult",
    "BaseProvider",
    "ProviderError",
]
