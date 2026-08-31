"""Everything that speaks the OpenAI wire format.

One adapter, one base URL. Verified shapes:
  OpenAI      default base URL
  Gemini      https://generativelanguage.googleapis.com/v1beta/openai/
  xAI         https://api.x.ai/v1
  Groq        https://api.groq.com/openai/v1
  OpenRouter  https://openrouter.ai/api/v1
  Ollama      http://localhost:11434/v1

Structured-output support varies across these, so a json_schema response format
is attempted and quietly dropped if the endpoint rejects it. The reply is parsed
defensively either way.
"""

from .base import Provider, MissingDependency, MissingKey, ProviderError


class OpenAICompatProvider(Provider):
    name = "openai-compat"

    def __init__(self, cfg):
        Provider.__init__(self, cfg)
        try:
            from openai import OpenAI
        except ImportError:
            raise MissingDependency(
                "the openai SDK is not installed. Run: pip install 'cyft[openai]'")
        from ..config import resolve_key
        key = resolve_key(cfg)
        base = cfg.get("base_url")
        # A local Ollama needs no key, but the SDK requires the argument.
        if not key and base and "localhost" in base:
            key = "ollama"
        if not key:
            raise MissingKey(
                "no API key. Set the variable named by api_key_env in config.json.")
        self._client = OpenAI(api_key=key, base_url=base) if base else OpenAI(api_key=key)

    def _content(self, blocks):
        out = []
        for b in blocks:
            if b["type"] == "image":
                out.append({"type": "image_url", "image_url": {
                    "url": "data:%s;base64,%s" % (b["media_type"], b["data"])}})
            else:
                out.append({"type": "text", "text": b["text"]})
        return out

    def complete(self, system, blocks, schema, max_tokens):
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": self._content(blocks)},
        ]
        strict = {
            "type": "json_schema",
            "json_schema": {"name": "cyft_reading", "strict": True, "schema": schema},
        }
        for response_format in (strict, {"type": "json_object"}, None):
            kwargs = {"model": self.model, "messages": messages,
                      "max_completion_tokens": max_tokens}
            if response_format:
                kwargs["response_format"] = response_format
            try:
                response = self._client.chat.completions.create(**kwargs)
            except Exception as exc:
                if response_format is None or not _unsupported(exc):
                    raise ProviderError("%s: %s" % (type(exc).__name__, exc))
                continue          # endpoint refused this response_format, step down
            content = response.choices[0].message.content
            if content:
                return content
            raise ProviderError("empty response")
        raise ProviderError("no usable response")


def _unsupported(exc):
    """True when the endpoint rejected the request shape rather than the content."""
    text = str(exc).lower()
    markers = ("response_format", "json_schema", "unsupported", "not supported",
               "invalid_request", "unrecognized", "unknown parameter")
    return any(m in text for m in markers)
