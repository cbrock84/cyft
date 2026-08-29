# Cyft

**Decide whether saved things are useful to you, given what you are actually trying to do.**

A design document, not a working tool. There is no implementation yet, and the
reasoning for that is in Status below.

## The problem

You save things. A screenshot of a tool thread, a link someone sent, a PDF from a vendor,
a paragraph you pasted into a note. Saving is the right instinct: you saw something
plausible while you were busy doing something else.

Then it sits there. The folder grows, and it stops being a resource and becomes a debt.

The usual fix is a better read-later app, which is the wrong fix. The problem is not
retrieval. The problem is that nothing in the pile has been evaluated, and evaluation is
the expensive part.

## The idea this is built on

**Usefulness is not a property of a thing. It is a relationship between the thing and
what you are trying to do.**

Almost every tool roundup, newsletter, and "top 10 repos" carousel gets this wrong. They
assert usefulness absolutely. A tool is called essential with no reference to who is
reading, what they own, what they are allowed to buy, what they can operate, or what they
are trying to accomplish this quarter.

That absolute framing is why the pile does not resolve. Nothing in it can be true or false
until you supply the missing half of the sentence.

So the first-class object here is not the item. It is the **profile**: your goals, your
active work, your constraints, and your kill criteria. Items are scored against it.
Change the profile and the same item can move from adopt to reject, correctly.

## What it does

```
intake  ->  normalize  ->  dedupe  ->  resolve  ->  verify  ->  score  ->  route  ->  digest
```

You put in screenshots, links, PDFs, text snippets, and repository references. You get
back, for each distinct item: what it actually is, what is verifiably true about it, what
is merely claimed, how it relates to your stated goals, and a routed decision with a
reason. Plus a digest of only what is new since last time.

**It does not decide.** It produces evidence and a recommendation. A person adopts.

## What it is not

- Not a read-later app. It does not help you store things, it helps you finish with them.
- Not a summarizer. A summary of a marketing claim is still a marketing claim.
- Not a ranking of tools. There is no global leaderboard, because there is no global user.
- Not an autonomous agent. It never installs, buys, subscribes, or posts.

## Design principles

1. **Usefulness is relational.** No score exists without a profile. The tool refuses to
   rank items with no profile loaded, rather than falling back to a generic score.
2. **Discovery is not diligence.** A saved item is evidence that a claim exists. Nothing
   more, until a primary source says otherwise.
3. **Deduplicate on the artifact, not the post.** The same repository in four threads is
   one item. Frequency across sources is a distribution artifact, not corroboration.
4. **Every claim carries a label and a source.** The vocabulary is closed: claimed,
   verified, tested, adopted, rejected, inferred, uncertain.
5. **Check the license before the plan.** It is the cheapest gate and the only one that
   can retroactively invalidate finished work.
6. **Rejections are outputs.** A rejected item keeps its evidence and its reason, so a
   later pass does not rediscover it as new.
7. **Counts come from files, not prose.** Any total in a report cites the file that
   generates it and the date it was read.
8. **The human decides.** The tool proposes; a person adopts, with a date and a reversal
   condition.

## Repository layout

```text
cyft/
  README.md
  LICENSE                     Apache-2.0
  NOTICE
  intake.md                   How things get in. The adapter contract
  agent-prompt.md             Copy-paste prompt for collecting via a connector
  profile.example.json        Your goals, constraints, entities, kill criteria
  inbox/<run-id>/
    intake.json               Written by the adapter. The whole integration surface
    <files>                   Images, PDFs, archives, .url, .md, .txt
  items/<id>/
    item.json                 Normalized record: type, hash, source, capture date
    extracted.md              Text pulled out of the artifact
    claims.json               Every assertion, labeled, with its source
    decision.json             Score against the profile, route, reason, date
  library/                    Items routed to reference. Searchable, not actionable
  rejected/                   Items that failed a gate, with the gate named
  digests/YYYY-MM-DD.md       Only what is net new or materially changed
  schemas/                    profile, item, claim, decision, intake-manifest
  scripts/                    Deterministic steps. LLM only where it must be
```

## The pipeline, stage by stage

### 1. Intake

Accepts screenshots and photos, PDFs, URLs, plain text and Markdown snippets, archives, and
direct repository references. Records the source, the capture date, and a content hash. The
hash is what makes step 3 possible.

**Cyft never holds your credentials and never reaches out to a service.** Adapters bring
bytes to it. Drop a zip of a hundred screenshots, point it at a folder, or ask the
assistant that already has a connector to your cloud drive to collect a folder and write a
manifest. The entire integration surface is one JSON file, so anything that can write files
is an adapter.

Full design in [`intake.md`](intake.md), with the manifest schema, the archive-extraction
safety rules, the untrusted-content handling, and a copy-paste prompt for the agent path in
[`agent-prompt.md`](agent-prompt.md).

### 2. Normalize

Extract text. For images this is OCR; for PDFs, text extraction with OCR fallback; for
URLs, a fetch of the page itself rather than a description of it. Extraction output is
kept separately from the original, and neither is treated as authoritative for a product
name. Reading a name off an image is exactly how you end up researching the wrong company.

### 3. Dedupe

Group adjacent captures from the same source post, then merge on the underlying artifact.
Check against everything already processed. Most piles are far smaller than they look.

### 4. Resolve

Find the primary source for each item, in descending order of strength: the source
repository and its license file, official documentation, filings and standards, first-party
pricing pages captured with a date, a reproducible observation, and only then third-party
reporting. A social post is a primary source for one thing, which is that somebody made
the claim.

Items that cannot be resolved are not discarded. They are labeled `uncertain` and routed
with that label attached.

### 5. Verify

For each item, establish what can be established: license and what it permits for your
intended use, maintenance signals, open security issues, and whether specific claims hold.
Separate what the source claimed from what a primary source confirms. Record both. The gap
between them is often the most useful output in the whole run.

### 6. Score against the profile

Not a generic score. Each item is scored against each **goal** in your profile:

| Dimension | Question |
| --- | --- |
| Relevance | Does this advance a goal you have actually stated? |
| Evidence | Is the value verified, tested, or only claimed? |
| Effort | What does a bounded first test cost, in your hours? |
| Risk | Security, license, platform terms, reputational, reversibility |
| Fit | Can you operate it, given what you already run? |
| Timing | Does it matter now, or is it a watch item? |

Plus **vetoes**, which are absolute and are not outscored by a high total: no lawful use
path, unacceptable data or credential exposure, a license incompatible with the intended
use, no export or rollback for anything that holds your data, or economics that depend
entirely on unverified claims.

### 7. Route

Every item ends in exactly one place, with a reason:

- **Act** on a named goal, with a first step and a kill date
- **Test** as a bounded experiment, with what is being measured
- **Watch**, with the specific condition that would promote it
- **Reference**, useful to know, not to do
- **Reject**, with the gate it failed
- **Not mine**, correct for someone else: a different entity, team, or owner

That last route matters more than it looks. A lot of what clogs a personal backlog is good
work that belongs to somebody else.

### 8. Digest

A short report of what is net new or materially changed. Not a re-listing of the library.
If a run produces nothing new, it says so in one line.

## Implementation notes

Deterministic where it can be, model-assisted where it must be.

- Steps 1, 3, and 7 are ordinary code. Hashing, grouping, and file moves need no model.
- Steps 2, 4, and 5 use a model for extraction and drafting, then a deterministic check:
  a fetched license file, an HTTP status, a schema validation.
- Step 6 uses a model to draft the argument and a person to accept it.
- Nothing autonomous touches money, credentials, production systems, or a social account.

Prefer Markdown plus JSON, local files, no database, and no service dependency for the
core loop. It should run offline against a folder, and be readable by a person who has
never seen the tool.

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

Chosen over MIT for three reasons that matter over a long life: an express patent grant in
section 3, which protects anyone who implements these schemas; explicit contribution terms
in section 5, so inbound contributions do not need a separate agreement; and the fact that
most corporate legal teams already have Apache-2.0 pre-approved for both use and
contribution, which matters when the intended audience works inside companies.

## Status

Blueprint. Schemas and a worked example are in this directory. There is no implementation
yet, and one should not be started before the method has been run by hand often enough to
know which parts are real.

The method itself has been run once, by hand, over a backlog of 158 saved items. That run
is the reason this exists as a design rather than a hypothesis.

## Open questions

1. **Profile bootstrapping.** Writing an honest profile is harder than it sounds and is
   the step most likely to be skipped. Does it need an interview flow, or does a good
   example file carry it?
2. **Model dependence.** How much of steps 4 and 5 can be made deterministic before the
   quality drops below useful?
3. **Scope of the library.** Does an item routed to reference need re-verification on a
   schedule, or is a stale reference honest as long as it carries its access date?
4. **Multi-profile.** One person often wears several hats with genuinely different goals.
   Is that several profiles, or one profile with several goals and an entity tag?
5. **Profile portability.** If two people share a profile shape for a common role, is that
   a template library, or is that the beginning of exactly the generic ranking this tool
   exists to avoid?
