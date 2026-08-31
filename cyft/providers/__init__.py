"""Two adapters, six or more providers.

Everything except Anthropic speaks the OpenAI wire format, so `openai-compat`
plus a base URL reaches OpenAI, Gemini, xAI, Groq, OpenRouter and a local
Ollama. Anthropic gets a native adapter because its message shape differs.

Adding a native adapter is a matter of implementing `complete()` and
registering it here.
"""

from .base import Block, ProviderError, text_block, image_block


def get(cfg):
    """Return a provider instance for this config. SDKs import lazily, so the
    deterministic half of Cyft runs with neither SDK installed."""
    name = cfg.get("provider", "anthropic")
    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(cfg)
    if name in ("openai-compat", "openai"):
        from .openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(cfg)
    raise ProviderError(
        "unknown provider %r. Use 'anthropic' or 'openai-compat'." % name)


__all__ = ["get", "Block", "ProviderError", "text_block", "image_block"]
