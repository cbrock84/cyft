"""Anthropic, via the official SDK.

Uses structured outputs so the response is guaranteed to be JSON matching the
schema, and adaptive thinking at a configurable effort. Reading a screenshot and
labelling claims is a classification job, so the default effort is low; raise it
in config.json if the labels are not holding up.
"""

from .base import Provider, MissingDependency, MissingKey, ProviderError


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, cfg):
        Provider.__init__(self, cfg)
        try:
            import anthropic
        except ImportError:
            raise MissingDependency(
                "the anthropic SDK is not installed. Run: pip install 'cyft[anthropic]'")
        from ..config import resolve_key
        key = resolve_key(cfg)
        if not key:
            raise MissingKey(
                "no API key. Set ANTHROPIC_API_KEY, or name another variable "
                "with api_key_env in config.json.")
        self._client = anthropic.Anthropic(api_key=key)

    def _content(self, blocks):
        out = []
        for b in blocks:
            if b["type"] == "image":
                out.append({"type": "image", "source": {
                    "type": "base64", "media_type": b["media_type"], "data": b["data"]}})
            else:
                out.append({"type": "text", "text": b["text"]})
        return out

    def complete(self, system, blocks, schema, max_tokens):
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": self._content(blocks)}],
            "thinking": {"type": "adaptive"},
            "output_config": {
                "effort": self.cfg.get("effort", "low"),
                "format": {"type": "json_schema", "schema": schema},
            },
        }
        try:
            response = self._client.messages.create(**kwargs)
        except Exception as exc:
            raise ProviderError("%s: %s" % (type(exc).__name__, exc))

        if getattr(response, "stop_reason", None) == "refusal":
            detail = getattr(response, "stop_details", None)
            raise ProviderError("the model declined this item (%s)" % (
                getattr(detail, "category", None) or "refusal"))

        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text
        raise ProviderError("no text block in the response")
