"""The provider contract.

A provider takes a system prompt, a list of normalised blocks, and a JSON schema,
and returns the model's raw text. Turning that text into validated claims is the
caller's job, not the provider's, so a badly behaved model cannot smuggle
structure past validation.
"""


class ProviderError(Exception):
    pass


class MissingDependency(ProviderError):
    pass


class MissingKey(ProviderError):
    pass


class Block(dict):
    pass


def text_block(text):
    return Block({"type": "text", "text": text})


def image_block(media_type, b64):
    return Block({"type": "image", "media_type": media_type, "data": b64})


class Provider(object):
    name = "abstract"

    def __init__(self, cfg):
        self.cfg = cfg
        self.model = cfg.get("model")
        if not self.model:
            raise ProviderError(
                "no model set. Add \"model\" to config.json, or run: cyft config --model NAME")

    def complete(self, system, blocks, schema, max_tokens):
        raise NotImplementedError

    def describe(self):
        base = self.cfg.get("base_url")
        return "%s %s%s" % (self.name, self.model, (" via " + base) if base else "")
