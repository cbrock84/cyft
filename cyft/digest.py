"""Stage 8: what changed, and nothing else.

If a run turns up nothing new it says so in one line, which is a complete answer.
"""

from .scoring import ROUTES

LABEL = {"act": "Act", "test": "Test", "watch": "Watch",
         "reference": "Reference", "reject": "Reject", "notmine": "Not mine"}


def since(items, timestamp):
    out = []
    for it in items:
        if it.get("status") != "decided":
            continue
        if timestamp and (it.get("decided_at") or "") <= timestamp:
            continue
        out.append(it)
    return out


def render(items, timestamp=None):
    fresh = since(items, timestamp)
    waiting = len([i for i in items if i.get("status") == "recommended"])
    tail = ("%d proposal(s) await your confirmation.\n" % waiting) if waiting else ""
    if not fresh:
        return ("Nothing new since the last digest.\n" + tail).rstrip("\n")

    lines = []
    for r in ROUTES:
        group = [i for i in fresh if i.get("route") == r]
        if not group:
            continue
        lines.append("%s (%d)" % (LABEL[r], len(group)))
        for it in sorted(group, key=lambda x: x.get("decided_at") or ""):
            name = it.get("what") or it.get("name") or it.get("id")
            reason = it.get("reason")
            lines.append("  - %s%s" % (name, ("  (%s)" % reason) if reason else ""))
            decision = it.get("decision") or {}
            rec = it.get("recommendation") or {}
            if decision.get("overrides_recommendation") and rec.get("route"):
                lines.append("    Cyft recommended %s: %s" % (rec["route"], rec["reason"]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n" + tail
