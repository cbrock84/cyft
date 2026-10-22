"""Stages 6 and 7: score against the profile, then route.

Pure functions over data. No model, no network, no randomness, so the same item
and the same profile always produce the same route and the same reason.
"""

ROUTES = ("act", "test", "watch", "reference", "reject", "notmine")

VETOES = {
    "legal": "no lawful path to the intended use",
    "data": "unacceptable exposure of data or credentials",
    "licence": "the licence does not permit the intended use",
    "lockin": "no export or rollback for something that holds your data",
    "claims": "the economics rest entirely on unverified claims",
}

HELP = ("lot", "some", "little")
COST = ("hour", "day", "week")


class ScoringError(ValueError):
    pass


def goal_by_id(profile, goal_id):
    for g in (profile or {}).get("goals", []):
        if g.get("id") == goal_id:
            return g
    return None


def route(item, profile):
    """Return (route, reason). An empty route means not enough has been answered."""
    vetoes = [v for v in item.get("vetoes", []) if v in VETOES]
    if vetoes:
        return "reject", "a dealbreaker applies: %s" % VETOES[vetoes[0]]

    goal_id = item.get("goal") or ""
    if goal_id == "notmine":
        return "notmine", "it belongs to someone else"
    if goal_id in ("", "none"):
        if goal_id == "none":
            return "reference", "it does not serve a goal you have written down"
        return "", ""

    goal = goal_by_id(profile, goal_id)
    if goal is None:
        return "", ""
    name = '"%s"' % goal.get("name", goal_id)

    help_, cost = item.get("help"), item.get("cost")
    if help_ not in HELP or cost not in COST:
        return "", ""

    if help_ == "lot" and cost == "hour":
        return "act", "it helps %s a lot and costs about an hour to try" % name
    if help_ == "lot":
        return "test", "it helps %s a lot but is not a same-day job" % name
    if help_ == "some" and cost == "hour":
        return "test", "cheap enough to try against %s" % name
    if help_ == "some":
        return "watch", "some help to %s, not enough for the effort now" % name
    return "reference", "little help to %s as things stand" % name


# A dealbreaker may still be filed as watch, reference, reject or notmine, but
# never as something to act on or test. This is enforced here, not in a prompt.
BLOCKED_BY_VETO = ("act", "test")


def active_vetoes(item):
    return [v for v in item.get("vetoes", []) if v in VETOES]


def recommend(item, profile):
    """Store Cyft's own recommendation on the item, apart from any decision."""
    suggested, why = route(item, profile)
    from . import store
    item["recommendation"] = {"route": suggested, "reason": why, "by": "cyft",
                              "at": store.now()}
    return suggested, why


def _choose(item, profile, chosen, reason):
    suggested, why = recommend(item, profile)
    final = chosen or suggested
    if not final:
        raise ScoringError(
            "not enough answered to route this item. Set a goal, and help and cost.")
    if final not in ROUTES:
        raise ScoringError("unknown route %r. One of: %s" % (final, ", ".join(ROUTES)))
    vetoes = active_vetoes(item)
    if vetoes and final in BLOCKED_BY_VETO:
        raise ScoringError(
            "a dealbreaker applies (%s: %s), so this cannot go to %s. "
            "Remove the dealbreaker if it does not apply." % (vetoes[0], VETOES[vetoes[0]], final))
    overrides = bool(suggested) and final != suggested
    text = (reason or "").strip()
    if not text:
        text = ("chosen over Cyft's recommendation of %s" % suggested) if overrides else why
    return final, text, overrides


def propose(item, profile, chosen=None, reason=None, by="mcp-client"):
    """Record a route someone other than the person picked. Not a decision."""
    final, text, overrides = _choose(item, profile, chosen, reason)
    from . import store
    item["proposal"] = {"route": final, "reason": text, "by": by, "at": store.now(),
                        "overrides_recommendation": overrides}
    item["status"] = "recommended"
    return item


def apply_route(item, profile, chosen=None, reason=None, by="person"):
    """The person's decision. The only path that sets status 'decided'."""
    final, text, overrides = _choose(item, profile, chosen, reason)
    from . import store
    at = store.now()
    item["decision"] = {"route": final, "reason": text, "by": by, "at": at,
                        "overrides_recommendation": overrides}
    item["route"] = final
    item["reason"] = text
    item["status"] = "decided"
    item["decided_at"] = at
    item["decided_by"] = by
    item.pop("proposal", None)
    return item


def counts(items):
    out = dict((r, 0) for r in ROUTES)
    for it in items:
        if it.get("route") in out:
            out[it["route"]] += 1
    return out
