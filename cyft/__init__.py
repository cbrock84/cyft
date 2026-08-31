"""Cyft: decide whether the things you save are useful to you.

The core (intake, dedupe, scoring, routing, digest) is deterministic and depends
on nothing but the standard library. Only the reading stage talks to a model,
and its provider SDKs are optional extras imported at call time.
"""

__version__ = "0.1.0"
