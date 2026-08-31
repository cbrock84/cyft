"""Configuration and credentials.

One key, supplied by the person running Cyft, read from the environment or from
a config file that must not be world readable. Never written to the run store,
never sent anywhere except the provider it belongs to.
"""

import json
import os
import stat

CONFIG_NAME = "config.json"

DEFAULTS = {
    "provider": "anthropic",
    "model": "claude-opus-5",
    "base_url": None,
    "api_key_env": None,
    "effort": "low",
    "max_output_tokens": 2000,
}

# Convenience presets. Every one of these speaks the OpenAI wire format except
# anthropic, which is why there are only two adapters behind them.
PRESETS = {
    "anthropic": {"provider": "anthropic", "model": "claude-opus-5",
                  "api_key_env": "ANTHROPIC_API_KEY", "base_url": None},
    "openai": {"provider": "openai-compat", "api_key_env": "OPENAI_API_KEY",
               "base_url": None},
    "gemini": {"provider": "openai-compat", "api_key_env": "GEMINI_API_KEY",
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"},
    "xai": {"provider": "openai-compat", "api_key_env": "XAI_API_KEY",
            "base_url": "https://api.x.ai/v1"},
    "groq": {"provider": "openai-compat", "api_key_env": "GROQ_API_KEY",
             "base_url": "https://api.groq.com/openai/v1"},
    "openrouter": {"provider": "openai-compat", "api_key_env": "OPENROUTER_API_KEY",
                   "base_url": "https://openrouter.ai/api/v1"},
    "ollama": {"provider": "openai-compat", "api_key_env": None,
               "base_url": "http://localhost:11434/v1"},
}


class ConfigError(Exception):
    pass


def config_path(root):
    return os.path.join(root, CONFIG_NAME)


def load(root):
    """Read config from the run store, falling back to defaults."""
    cfg = dict(DEFAULTS)
    path = config_path(root)
    if os.path.exists(path):
        _warn_if_readable(path)
        with open(path, "r", encoding="utf-8") as fh:
            try:
                cfg.update(json.load(fh))
            except ValueError as exc:
                raise ConfigError("%s is not valid JSON: %s" % (path, exc))
    return cfg


def save(root, cfg):
    path = config_path(root)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.chmod(path, 0o600)
    return path


def apply_preset(cfg, name):
    if name not in PRESETS:
        raise ConfigError("unknown preset %r. Known: %s"
                          % (name, ", ".join(sorted(PRESETS))))
    cfg = dict(cfg)
    cfg.update(PRESETS[name])
    return cfg


def resolve_key(cfg):
    """Return the API key, or None.

    Order: the env var named in api_key_env, then the provider default env var.
    A key is never read from the config file itself, so a stray commit of the
    run store cannot leak one.
    """
    names = []
    if cfg.get("api_key_env"):
        names.append(cfg["api_key_env"])
    if cfg.get("provider") == "anthropic":
        names.append("ANTHROPIC_API_KEY")
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _warn_if_readable(path):
    """A config file others can read is a problem worth naming, not hiding."""
    try:
        mode = os.stat(path).st_mode
    except OSError:
        return
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        import sys
        sys.stderr.write(
            "warning: %s is readable by other users. Run: chmod 600 %s\n" % (path, path))
