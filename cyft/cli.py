"""The command line.

    cyft init                 create a run store here, with a profile to fill in
    cyft config --preset xai  point it at a provider and model
    cyft add PATH...          take in files, folders, or URLs
    cyft read                 ask the model what each new item is
    cyft sort                 score and route, one item at a time
    cyft list                 what is where, and why
    cyft digest               what changed since last time
    cyft mcp                  serve over stdio, so your assistant does the reading
"""

import argparse
import json
import os
import sys

from . import config as configmod
from . import digest as digestmod
from . import intake, scoring, store
from .providers import ProviderError

DEFAULT_ROOT = ".cyft"

PROFILE_TEMPLATE = {
    "goals": [
        {"id": "goal-1", "name": "", "why": "", "stop_when": ""}
    ],
    "constraints": {"can_operate": "", "can_buy": "", "notes": ""},
}


def out(msg=""):
    sys.stdout.write(str(msg) + "\n")


def err(msg):
    sys.stderr.write(str(msg) + "\n")


def resolve_root(args):
    return os.path.abspath(getattr(args, "root", None) or
                           os.environ.get("CYFT_ROOT") or DEFAULT_ROOT)


def require_store(root):
    if not os.path.isdir(root):
        err("No run store at %s. Run: cyft init" % root)
        raise SystemExit(2)


def require_profile(root):
    profile = store.load_profile(root)
    named = [g for g in (profile or {}).get("goals", []) if (g.get("name") or "").strip()]
    if not named:
        err("No goals in %s. Nothing can be scored without them.\n"
            "Edit %s and give at least one goal a name."
            % (root, os.path.join(root, store.PROFILE)))
        raise SystemExit(2)
    return profile


# ------------------------------------------------------------------ commands

def cmd_init(args):
    root = resolve_root(args)
    store.ensure(root)
    path = os.path.join(root, store.PROFILE)
    if os.path.exists(path) and not args.force:
        out("Run store already at %s" % root)
    else:
        store.save_profile(root, PROFILE_TEMPLATE)
        out("Created %s" % root)
    cfg = configmod.load(root)
    configmod.save(root, cfg)
    out("")
    out("Next: edit %s and write down what you are actually trying to do." % path)
    out("Then:  cyft add ~/Desktop/screenshots")
    return 0


def cmd_config(args):
    root = resolve_root(args)
    require_store(root)
    cfg = configmod.load(root)
    if args.preset:
        cfg = configmod.apply_preset(cfg, args.preset)
    for field in ("model", "base_url", "api_key_env", "effort"):
        value = getattr(args, field, None)
        if value is not None:
            cfg[field] = value
    if args.preset or any(getattr(args, f, None) is not None
                          for f in ("model", "base_url", "api_key_env", "effort")):
        configmod.save(root, cfg)

    out("provider     %s" % cfg.get("provider"))
    out("model        %s" % (cfg.get("model") or "(not set)"))
    out("base_url     %s" % (cfg.get("base_url") or "(provider default)"))
    out("api_key_env  %s" % (cfg.get("api_key_env") or "(provider default)"))
    out("effort       %s" % cfg.get("effort"))
    key = configmod.resolve_key(cfg)
    out("api key      %s" % ("found in the environment" if key else "NOT SET"))
    if not key:
        out("")
        out("Set the key before running cyft read. Nothing else needs it.")
    return 0


def cmd_presets(args):
    out("Presets for: cyft config --preset NAME")
    out("")
    for name in sorted(configmod.PRESETS):
        p = configmod.PRESETS[name]
        out("  %-11s %s" % (name, p.get("base_url") or "(provider default URL)"))
    out("")
    out("All but 'anthropic' use the same OpenAI-compatible adapter.")
    out("Set the model yourself: cyft config --preset xai --model MODEL")
    return 0


def cmd_add(args):
    root = resolve_root(args)
    require_store(root)
    urls = [t for t in args.targets if t.startswith("http://") or t.startswith("https://")]
    paths = [t for t in args.targets if t not in urls]
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        err("Not found: %s" % ", ".join(missing))
        return 2

    added = dupes = 0
    skipped = []
    for url in urls:
        _, is_new = intake.add_url(root, url)
        added += 1 if is_new else 0
        dupes += 0 if is_new else 1
    if paths:
        a, d = intake.add_paths(root, paths, on_skip=lambda p, why: skipped.append((p, why)))
        added += a
        dupes += d

    out("%d added, %d already in the pile" % (added, dupes))
    if skipped:
        out("")
        out("%d file(s) left alone, because Cyft copies what it takes in and sends" % len(skipped))
        out("text to a model when you run read:")
        for path, reason in skipped[:12]:
            out("  %-44s %s" % (os.path.basename(path)[:44], reason))
        if len(skipped) > 12:
            out("  and %d more" % (len(skipped) - 12))
    pending = [i for i in store.list_items(root) if i.get("status") == "new"]
    if pending:
        out("%d waiting to be read. Next: cyft read" % len(pending))
    return 0


def cmd_read(args):
    root = resolve_root(args)
    require_store(root)
    cfg = configmod.load(root)
    items = [i for i in store.list_items(root)
             if i.get("status") == "new" or (args.all and i.get("status") != "decided")]
    if not items:
        out("Nothing to read.")
        return 0
    if args.limit:
        items = items[:args.limit]

    from .providers import get as get_provider
    from . import reading
    try:
        provider = get_provider(cfg)
    except ProviderError as exc:
        err(str(exc))
        return 2
    out("Reading %d item(s) with %s" % (len(items), provider.describe()))

    ok = failed = 0
    for item in items:
        label = item.get("name") or item["id"]
        try:
            reading.read_item(root, cfg, item, provider=provider)
        except Exception as exc:
            failed += 1
            err("  %-40s %s" % (label[:40], exc))
            continue
        ok += 1
        out("  %-40s %s" % (label[:40], (item.get("what") or "")[:60]))
    out("")
    out("%d read, %d failed" % (ok, failed))
    if ok:
        out("Next: cyft sort")
    return 1 if failed and not ok else 0


def cmd_sort(args):
    root = resolve_root(args)
    require_store(root)
    profile = require_profile(root)
    items = [i for i in store.list_items(root) if i.get("status") != "decided"]
    if not items:
        out("Nothing left to sort.")
        return 0

    goals = [g for g in profile["goals"] if (g.get("name") or "").strip()]
    for item in items:
        out("")
        out("=" * 68)
        out(item.get("what") or item.get("name") or item["id"])
        if item.get("url"):
            out(item["url"])
        for claim in item.get("claims", []):
            out("  [%s] %s" % (claim["label"], claim["text"]))
        out("-" * 68)

        for i, g in enumerate(goals, 1):
            out("  %d. %s" % (i, g["name"]))
        out("  n. none of them      x. someone else's job      s. skip      q. quit")
        answer = _ask("Which goal does it serve? ")
        if answer is None or answer == "q":
            break
        if answer == "s":
            continue
        if answer == "x":
            item["goal"] = "notmine"
        elif answer == "n":
            item["goal"] = "none"
        elif answer.isdigit() and 1 <= int(answer) <= len(goals):
            item["goal"] = goals[int(answer) - 1]["id"]
            item["help"] = _choice("How much would it help? ",
                                   [("1", "lot", "a lot"), ("2", "some", "some"),
                                    ("3", "little", "not really")])
            item["cost"] = _choice("A first proper try costs? ",
                                   [("1", "hour", "about an hour"), ("2", "day", "about a day"),
                                    ("3", "week", "a week or more")])
        else:
            continue

        vetoes = _vetoes()
        if vetoes:
            item["vetoes"] = vetoes

        suggested, why = scoring.route(item, profile)
        if suggested:
            out("  Suggested: %s, because %s" % (suggested.upper(), why))
        chosen = _ask_route(suggested)
        if chosen is None:
            break
        try:
            scoring.apply_route(item, profile, chosen=chosen or None)
        except scoring.ScoringError as exc:
            err("  %s" % exc)
            continue
        store.save_item(root, item)
        out("  Filed under %s" % item["route"])

    return 0


def cmd_list(args):
    root = resolve_root(args)
    require_store(root)
    items = store.list_items(root)
    decided = [i for i in items if i.get("status") == "decided"]
    if args.route:
        decided = [i for i in decided if i.get("route") == args.route]

    counts = scoring.counts([i for i in items if i.get("status") == "decided"])
    out("  ".join("%s %d" % (digestmod.LABEL[r], counts[r]) for r in scoring.ROUTES))
    pending = len(items) - len([i for i in items if i.get("status") == "decided"])
    out("%d item(s), %d still to decide" % (len(items), pending))
    out("")
    for it in sorted(decided, key=lambda x: x.get("decided_at") or ""):
        out("%-10s %-46s %s" % (it.get("route", ""),
                                (it.get("what") or it.get("name") or "")[:46],
                                (it.get("reason") or "")[:40]))
    return 0


def cmd_digest(args):
    root = resolve_root(args)
    require_store(root)
    state = store.load_state(root)
    items = store.list_items(root)
    text = digestmod.render(items, None if args.all else state.get("last_digest"))
    out(text)
    if args.mark:
        state["last_digest"] = store.now()
        store.save_state(root, state)
        out("Marked. The next digest starts from here.")
    return 0


def cmd_mcp(args):
    """Speak MCP on stdio so the assistant you already use does the reading.

    Nothing may go to stdout but protocol messages, so this prints no banner.
    """
    from . import mcp
    return mcp.serve(resolve_root(args))


# ------------------------------------------------------------------- prompts

def _ask(prompt):
    """Returns the answer, or None if input ended. None means stop, never a value."""
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return None


def _ask_route(suggested):
    """Re-prompt until the answer is a real route or an empty line.

    An unrecognised answer used to fall through and drop the item silently.
    """
    options = "/".join(scoring.ROUTES)
    while True:
        answer = _ask("  Route [enter to accept%s, or %s]: "
                      % ((" " + suggested) if suggested else "", options))
        if answer is None:
            return None
        if answer == "":
            if suggested:
                return ""
            err("  No suggestion to accept. Name a route: %s" % options)
            continue
        if answer in scoring.ROUTES:
            return answer
        err("  %r is not a route. One of: %s" % (answer, options))


def _choice(prompt, options):
    out("  " + "   ".join("%s. %s" % (k, label) for k, _, label in options))
    answer = _ask("  " + prompt)
    if answer is None:
        return ""
    for key, value, _ in options:
        if answer == key:
            return value
    return ""


def _vetoes():
    answer = _ask("  Dealbreakers? [enter for none, or %s]: "
                  % "/".join(sorted(scoring.VETOES)))
    if not answer:
        return []
    return [v for v in answer.replace(",", " ").split() if v in scoring.VETOES]


# ---------------------------------------------------------------------- main

def build_parser():
    p = argparse.ArgumentParser(prog="cyft", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", help="run store directory (default: .cyft)")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("init", help="create a run store here")
    s.add_argument("--force", action="store_true", help="overwrite an existing profile")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("config", help="show or change the provider and model")
    s.add_argument("--preset", help="anthropic, openai, gemini, xai, groq, openrouter, ollama")
    s.add_argument("--model")
    s.add_argument("--base-url", dest="base_url")
    s.add_argument("--api-key-env", dest="api_key_env")
    s.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    s.set_defaults(func=cmd_config)

    s = sub.add_parser("presets", help="list provider presets")
    s.set_defaults(func=cmd_presets)

    s = sub.add_parser("add", help="add files, folders or URLs")
    s.add_argument("targets", nargs="+")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("read", help="ask the model what each new item is")
    s.add_argument("--limit", type=int, help="stop after N items")
    s.add_argument("--all", action="store_true", help="re-read items already read")
    s.set_defaults(func=cmd_read)

    s = sub.add_parser("sort", help="score and route each item")
    s.set_defaults(func=cmd_sort)

    s = sub.add_parser("list", help="show decisions")
    s.add_argument("--route", choices=list(scoring.ROUTES))
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("mcp", help="run as an MCP server over stdio")
    s.set_defaults(func=cmd_mcp)

    s = sub.add_parser("digest", help="what changed since last time")
    s.add_argument("--all", action="store_true", help="everything, not just what is new")
    s.add_argument("--mark", action="store_true", help="mark this digest as read")
    s.set_defaults(func=cmd_digest)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        err("\nStopped. Nothing was lost; decisions are saved as you make them.")
        return 130
    except configmod.ConfigError as exc:
        err(str(exc))
        return 2
