# Worked example: one item, two profiles, two correct answers

The point of this example is the part most tool reviews skip. The same item, evaluated
honestly, produces opposite routes for two different people, and both are right.

The item is a real pattern from the run described in issue 1: a programmatic video library
whose license is free for individuals and for-profit organizations up to three employees,
and which requires a company license above that threshold.

Nothing about the library changes between the two evaluations. Only the profile does.

## The item

```json
{
  "schema_version": "0.1",
  "id": "programmatic-video-library",
  "kind": "repository",
  "name": "Programmatic video library",
  "one_line": "Renders video from code, so a product demo becomes an artifact you re-render instead of footage you re-shoot.",
  "captures": [
    {
      "capture_id": "cap-0041",
      "input_type": "screenshot",
      "origin": "social carousel, tool roundup",
      "captured": "2026-08-26",
      "content_hash": "sha256:2f1a...",
      "extracted_path": "items/programmatic-video-library/extracted.md",
      "group": "grp-roundup-08"
    },
    {
      "capture_id": "cap-0089",
      "input_type": "screenshot",
      "origin": "different account, same tool",
      "captured": "2026-08-26",
      "content_hash": "sha256:9c33...",
      "group": "grp-roundup-14"
    }
  ],
  "primary_source": { "url": "https://example.invalid/repo", "kind": "repository", "resolved": "2026-08-27" },
  "license": {
    "identifier": "custom",
    "source_available_not_osi": true,
    "permits_intended_use": null,
    "restrictions": ["Free only for individuals and for-profit organizations up to three employees."],
    "checked": "2026-08-27"
  },
  "first_seen": "2026-08-26",
  "status": "verified"
}
```

Two captures, one item. That is stage 3 doing its job: the same library appeared under two
different accounts, which is a distribution artifact and not a second data point.

## The claims

```json
{
  "schema_version": "0.1",
  "item_id": "programmatic-video-library",
  "claims": [
    {
      "id": "c1",
      "assertion": "The library renders video deterministically from code.",
      "label": "verified",
      "source": "https://example.invalid/repo",
      "source_kind": "repository",
      "recorded": "2026-08-27"
    },
    {
      "id": "c2",
      "assertion": "Free use is limited to individuals and for-profit organizations with up to three employees.",
      "label": "verified",
      "source": "https://example.invalid/repo/LICENSE",
      "source_kind": "license",
      "recorded": "2026-08-27",
      "revalidate_after_days": 30
    },
    {
      "id": "c3",
      "assertion": "Agencies are charging four figures per launch video built on it.",
      "label": "claimed",
      "source": "cap-0041",
      "source_kind": "capture",
      "recorded": "2026-08-26"
    },
    {
      "id": "c4",
      "assertion": "The re-render property is worth more than the render quality, because interfaces change more often than they ship.",
      "label": "inferred",
      "source": "analyst judgment from the capture and the repository",
      "source_kind": "analyst-judgment",
      "recorded": "2026-08-27"
    }
  ]
}
```

Note `c3`. It is the sentence that made the screenshot worth saving, and it is the only one
with no support. It stays in the record, labeled, rather than being deleted or believed.

## Profile A: a one-person company

Two employees, wants to sell a productized launch-video service. Budget posture is
`cheap-experiments`. License requirement: must permit commercial use for anything sold.

```json
{
  "schema_version": "0.1",
  "item_id": "programmatic-video-library",
  "profile_ref": { "owner": "operator-a", "profile_updated": "2026-08-29" },
  "scored": "2026-08-29",
  "vetoed_by": null,
  "per_goal": [
    {
      "goal_id": "revenue-1",
      "relevance": 5, "evidence": 4, "effort": 3, "risk": 4, "fit": 4, "timing": 4,
      "note": "Under the headcount threshold, so free use is permitted for the intended commercial work. Evidence is 4 not 5 because the pricing claim is unverified: the capability is established, the market is not."
    }
  ],
  "route": "test",
  "reason": "License permits the intended use at current headcount. Build one reusable template against an owned product before quoting any client work.",
  "first_step": "One template, one owned product, render end to end.",
  "measure": "Hours to first usable render, and hours to re-render after an interface change.",
  "kill_date": "2026-10-15",
  "promote_when": null,
  "reassign_to": null,
  "decided_by": "human"
}
```

## Profile B: a technology leader at a mid-size company

Two hundred employees, wants better internal explainer content. Same budget posture, but a
license requirement that anything deployed must be clearly licensed for the company.

```json
{
  "schema_version": "0.1",
  "item_id": "programmatic-video-library",
  "profile_ref": { "owner": "operator-b", "profile_updated": "2026-08-29" },
  "scored": "2026-08-29",
  "vetoed_by": "license-mismatch",
  "per_goal": [
    {
      "goal_id": "internal-comms-1",
      "relevance": 4, "evidence": 4, "effort": 2, "risk": 1, "fit": 3, "timing": 3,
      "note": "Capability fits the goal. The headcount threshold is exceeded by two orders of magnitude, so free use does not apply and a company license is required before any pilot."
    }
  ],
  "route": "watch",
  "reason": "Vetoed for immediate use by license-mismatch. Not rejected: the capability is genuinely relevant and the blocker is commercial, not technical.",
  "first_step": null,
  "measure": null,
  "kill_date": null,
  "promote_when": "A company license is priced and approved, or an equivalently capable tool with compatible terms is found.",
  "reassign_to": null,
  "decided_by": "human"
}
```

## What this shows

**The item did not change. The answer did.** Operator A tests it this month. Operator B
cannot touch it without a purchase order. A roundup that called this tool "essential for
creators" was not wrong so much as incomplete: it asserted half a sentence.

**The veto did not depend on the score.** Operator B's item scored respectably on
relevance and evidence. It was still stopped, because a veto is a gate and not a weight.
Averaging it into a total would have produced a number that looked fine and a decision that
was wrong.

**The unverified claim survived as an unverified claim.** Neither operator deleted `c3`,
and neither acted on it. It is now on the record so that if someone later says "but
agencies charge four figures for this", the answer is already written down: somebody said
so, on this date, with no source.

**Watch is a real route, not a polite reject.** Operator B's item has a written promotion
condition. In six months, that is the difference between rediscovering the tool from
scratch and reading one line.
