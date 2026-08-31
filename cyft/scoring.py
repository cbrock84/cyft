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


def apply_route(item, profile, chosen=None, reason=None):
    suggested, why = route(item, profile)
    final = chosen or suggested
    if not final:
        raise ScoringError(
            "not enough answered to route this item. Set a goal, and help and cost.")
    if final not in ROUTES:
        raise ScoringError("unknown route %r. One of: %s" % (final, ", ".join(ROUTES)))
    item["route"] = final
    item["reason"] = (reason or item.get("reason") or why or "").strip()
    item["status"] = "decided"
    from . import store
    item["decided_at"] = store.now()
    return item


def counts(items):
    out = dict((r, 0) for r in ROUTES)
    for it in items:
        if it.get("route") in out:
            out[it["route"]] += 1
    return out
