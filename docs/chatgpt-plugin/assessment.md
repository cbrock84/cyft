# Cyft as a ChatGPT plugin: phase 1 assessment

Status: research only. No code has changed. Section 6 lists questions that are still open; the defaults there are proposals, not decisions. Decided so far: the plugin will be free (section 7). Every platform claim carries a source URL and a check date. Re-verify anything that moves before relying on it.

Read-only. Checkout: `cbrock84/cyft` main at `9c07e34` (after PR #6). Docs read 2026-10-05.
`cbrock84/operator-notes` is outside this session's repo scope and was not read.

## 1. What the code actually does

`python -m unittest discover -s tests`: **78 tests, all pass.**

| Your understanding | Verdict | Evidence |
| --- | --- | --- |
| Python core, no runtime deps | Working | `pyproject.toml` `dependencies = []`; CI job `no-dependencies` enforces it (`.github/workflows/tests.yml`) |
| Eight local stdio MCP tools | Working, stdio only | `cyft/mcp.py:300-420`; newline JSON-RPC, protocol `2025-06-18`. No HTTP, no auth, one store set by `--root` |
| File hashing + URL dedup | Working, with gaps | SHA-256 of bytes `intake.py:172-180`; `normalise_url` `intake.py:117-127` |
| Goal routing | Working, simpler than documented | `scoring.py:32-63`: goal + help (lot/some/little) + cost (hour/day/week) + 5 vetoes |
| Incremental digest | Working, with gaps | `digest.py:209-236`, watermark in `state.json`, set by `cyft_digest mark=true` `mcp.py:279-288` |
| Host-assistant reading | Working | `cyft_next_unread` / `cyft_record_reading` `mcp.py:139-197`; screenshot sent inline as base64 |
| Optional provider reading | Working | `cyft/providers/`, lazily imported; `cyft read` |
| PDF text | Working, best effort | stdlib extractor `pdftext.py`; no OCR |

**Documented but not built** (README "pipeline" + layout, `intake.md`):
- OCR, and fetching a URL's page. A URL item holds only the string; nothing is ever fetched.
- `claims.json`, `decision.json`, `library/`, `rejected/`, `scripts/`, `inbox/` manifests. Real layout is `items/<id>/item.json` + `original.*` (`store.py:1-10`).
- Archive and agent/manifest intake: marked "Planned, v0" (`intake.md:69-70`).
- `schemas/decision.schema.json` (6 dimensions scored 0-5, `first_step`, `kill_date`, `decided_by: human|proposed`, route `not-mine`) does not match the code (3 answers, `decided_by: "mcp-client"`, route `notmine`).
- `schemas/claim.schema.json` requires `source` and `recorded` per claim; the code stores neither.

## 2. The four suspected gaps

1. **Profile editing: confirmed.** `cyft_profile` is read-only (`mcp.py:92-96`). A profile only exists after `cyft init` plus hand-editing JSON. No create/update tool.
2. **Claim evidence: confirmed.** Claims are `{text, label}` only (`reading.py:347-360`). No evidence URL, no checked date. `verified` is accepted on the assistant's word; only the prompt discourages misuse (`mcp.py:171-174`).
3. **Override beats dealbreaker: confirmed, reproduced.** `cyft_decide` with `vetoes:["licence"]`, `route:"act"` files the item under **act**, with stored reason "a dealbreaker applies: the licence does not permit..." Cause: `scoring.apply_route` takes `final = chosen or suggested` (`scoring.py:66-69`). The computed route is not stored, so the override survives only in that one response's text. CLI `sort` has the same path (`cli.py:247-252`). Tests cover override (`test_manual_override_wins`, `test_override_is_recorded_as_an_override`) but never with a veto.
4. **Storage for hosted use: confirmed.**
   - One directory, no user dimension.
   - `write_json` always writes the same `<path>.tmp` (`store.py:128-133`), so two concurrent writers to one file can collide.
   - Every write is read-modify-write with no lock or version, so concurrent updates are lost.
   - `find_by_hash` scans every item on every add.
   - `cyft_add` takes arbitrary local paths (`mcp.py:99-107`). This must never be exposed over a network.

## 3. Other findings that affect the plugin

- **No suggestion vs decision distinction.** README principle 8 and `SECURITY.md` say a route is a proposal until a person accepts it. In code, the assistant's `cyft_decide` sets `status: decided` directly and records `decided_by: "mcp-client"`. CLI decisions set no `decided_by` at all.
- **Dedup loses provenance.** A duplicate only increments `seen` (`intake.py:162-165, 177-180`). The second source, filename or URL variant is discarded.
- **URL normalisation is too broad and too narrow.** It lowercases the whole URL, including path and query, so distinct case-sensitive paths merge. It keeps `utm_*`, so tracking variants do not merge.
- **Digest watermark.** It is wall-clock `now()` at mark time, with second resolution and a `<=` compare (`digest.py:214`). An item decided in the same second after a mark is never shown. Render and mark are separate reads, so an item decided between them can be skipped. Only decisions appear; adds and readings do not. Re-deciding an item resurfaces it.
- **Sizes.** Images go inline at full size with no cap (`mcp.py:159-167`). Text is truncated at 20,000 characters on intake and 6,000 on reading.

## 4. ChatGPT platform constraints (verified 2026-10-05)

Sources: developers.openai.com/plugins/{build/mcp-server, build/auth, reference, build/monetization, plugin-guidelines, deploy/submission, deploy/app-review, deploy/connect-chatgpt}.

- **Packaging.** A plugin is "skills, MCP servers, and optional UI", submitted as a **ZIP** (manifest, MCP config, assets, review material) at platform.openai.com/plugins. Only one MCP server is allowed per plugin, and it must be in the initial ZIP. The legacy plugin protocol is not involved.
- **Transport.** The server must "support the MCP streamable HTTP transport", typically at `/mcp`, on a stable public HTTPS origin. Changing the origin means a new plugin. A Secure MCP Tunnel is fine for testing but does not replace the public endpoint.
- **Auth.** OAuth 2.1 per the MCP authorization spec, with PKCE `S256` and RFC 9728 metadata at `/.well-known/oauth-protected-resource`. CIMD is "preferred" and DCR is supported. Tokens are audience-bound to our resource. `securitySchemes` can be declared per tool (`noauth` / `oauth2`).
  - `_meta["openai/subject"]` is an anonymized id "for rate-limiting". It is not identity, so storage scope must come from our own token.
- **Tool metadata.** `readOnlyHint` / `destructiveHint` / `openWorldHint` must match actual behaviour, and mismatched hints are a listed rejection reason. Writing a log or advancing a digest marker counts as not read-only.
  - Descriptions must state side effects and limitations.
  - Responses must not carry internal ids or timestamps "unless strictly required".
- **Files.** A tool receives files only if it declares them in `_meta["openai/fileParams"]`. Each arrives as `{download_url, file_id, mime_type?, file_name?}`, and our server downloads it.
  - A widget can also use `uploadFile` / `selectFiles`, but that needs UI.
  - Size limits per tool: **unverified**.
  - There is no documented access to all chat attachments, chat history (the guidelines forbid requesting it), other plugins, local files, or background runs. I did not read `build/mcp-events`; treat any scheduled or push behaviour as a dependency.
- **Links.** Only the URL string reaches us. Fetching page content would be our server's outbound request, which means owning SSRF protection and site terms.
- **Testing.** chatgpt.com/plugins, then "+", then "Add custom MCP server". Use a public URL or Secure MCP Tunnel, then "Create as a plugin".
- **Plan gate (help.openai.com/en/articles/12584461).** "Full MCP is only available to Business and Enterprise/Edu users, currently. Pro users can connect MCPs with read/fetch permissions in developer mode." Plus is not mentioned. The service is web only, and only admins/owners can enable developer mode.
  - **Cyft's write tools (add, decide) need Business/Enterprise/Edu.** This also limits who can join an unlisted beta.
  - That help page may lag the newer plugins flow, so it is unconfirmed until tried on your account.
  - Workspace sharing ("Only those invited" / "Anyone in this workspace with the link") exists for Business/Enterprise plugins (help article 20001256, reported by the research pass, not re-checked by me).
- **Public submission.**
  - A verified organization (individual or business); an owner, or a member with Apps Management Write.
  - Website, support, privacy policy and terms URLs; domain verification; icon and screenshots; a demo video.
  - 5 positive and 3 negative test cases.
  - A demo account with sample data and no MFA.
  - "Trial or demo plugins will not be accepted". Suitable for ages 13-17.
  - After approval, eligible tool updates go live after automated checks.
- **Monetization.** This is the decisive constraint.
  - "plugins may conduct commerce only for physical goods. Selling digital products or services, including subscriptions, digital content, tokens, or credits, is not allowed, whether offered directly or indirectly (for example, through freemium upsells)."
  - Plugins "must not display subscription plans, initiate new subscriptions, or promote upgrades", and may not link to checkout. They may link to an informational plans page and may say a feature isn't on the user's plan.
  - "Users may sign in to an existing paid account and access features already included in their subscription."
  - No revenue share was found, and directory listing is not demand.
  - **So any revenue comes from an account sold on our own site. ChatGPT is a delivery channel, not a checkout.**

## 5. Recommended smallest direction

Build a thin remote adapter (separate `server` extra or subpackage) over the existing core. The CLI and stdio MCP stay unchanged and dependency-free.

- **Tools-only.** No widget until a concrete interaction problem needs one.
- **Identity.** From a hosted OAuth IdP's validated token `sub`; storage is scoped per user server-side.
- **Inputs on day one.** Pasted text, links (URL string only, no fetch), and uploaded screenshots and PDFs via `fileParams`, with type and size caps. No local paths over the network.
- **Reading.** The ChatGPT model reads; the server makes no LLM call, so marginal cost is hosting plus storage.
- **New tools.** Profile create/update.
- **Recommendations vs decisions.** Cyft records a computed **recommendation**. The user **accepts, rejects, defers or overrides** it, and an override is stored with the computed route and a required reason. A dealbreaker cannot be overridden into act or test (proposed rule; your call in Q4).
- **Claims.** Carry an evidence URL and a checked date. Assistant-supplied `verified` is stored as an assertion, not independent verification.
- **Digest.** A per-user monotonic change cursor replaces wall-clock time. Reading a digest is read-only; advancing the marker is a separate, explicitly write-annotated call.
- **Pilot.** Only you, connected as a custom MCP server. Prove two sessions end to end before anyone else.

## 6. Questions (defaults are proposals, not decisions)

1. **First customer and pile.** Default: you, then a few individuals triaging saved tools, articles and ideas against 1-3 active goals. Tradeoff: narrow enough to judge quality; a team or B2B pile would need sharing and roles first.
2. **Launch scope and your ChatGPT plan.** Default: private pilot, you only, via custom MCP server, on a Business workspace (required for write tools per the help center). An invite-only beta would be workspace sharing, which limits testers to that workspace. A public listing then reaches everyone. Tradeoff: fastest real proof, but outsiders can't use it until a public listing. Which plan do you have?
3. **Day-one inputs.** Default: pasted text, single URLs (stored, not fetched), and uploaded PNG/JPEG/WebP and PDF via `fileParams`, at 10 MB and 25 items per call. Defer server-side URL fetch, OCR, archives and bulk imports. Tradeoff: no SSRF surface; a link is judged on what the user or ChatGPT says about it.
4. **Experience and decision rules.** Default: chat-first, tools only. Goals are collected conversationally into a profile tool. Each item gets a recommendation plus reasons; you accept, reject, defer or override.
   - Override rule: dealbreakers block act/test, and any override needs a reason and is stored beside the computed route.
   - Tradeoff: a hard block is safer but occasionally annoying. The alternative is allowing a veto override with an explicit flag shown in every digest.
5. **Data and privacy.** Default:
   - Store extracted text, the user's notes, decisions and source URLs.
   - Delete original uploaded files after reading (keep only the hash), or keep them 30 days.
   - Export as JSON; delete-everything tool; no training use.
   - Tradeoff: no originals means no re-reading later.
6. **Infrastructure and cost.**
   - Default: Cloudflare (you already have the "Chris Brock LLC" account). Python Worker or a small container, D1 (SQLite) for records, R2 only if originals are kept.
   - Auth: a hosted IdP that supports CIMD or DCR with a free tier (WorkOS, Stytch or Auth0; I'd pick after checking current CIMD support).
   - Domain: your existing one if you have it.
   - Cost ceiling: $25/month for the pilot.
   - Tradeoff: Python on Workers has packaging limits. A small VM/container (Fly, Render, Railway) is simpler for Python but costs a little more. Which hosting, domain and IdP do you already pay for?
7. **Commercial value.** Default: the paid result is "my saved pile is cleared and I trust the decisions", measured by items decided per session and items not resurfaced.
   - Validate with 5-10 pilot users and a stated price ($5-10/month) on a plain web page before any billing.
   - Billing, when it comes, lives on our site. The plugin only signs in existing accounts (per the guidelines above).
   - Tradeoff: no in-ChatGPT conversion funnel at all.

## 7. Pivot: free plugin (Chris, 2026-10-06)

Install and use, per help.openai.com/en/articles/20001256 (checked 2026-10-06):
- "The plugin directory is available across ChatGPT plans. Installing or using an individual plugin depends on your plan, workspace, role, region, and its included capabilities."
- Directory, then "Install plugin", then "Connect" (sign-in) if the plugin needs an account.
- "ChatGPT automatically uses your installed plugins when they're relevant to your request. You can also select a plugin directly with an @ mention."

What changes:
- Q7 (paid result, billing) is dropped. The monetization ban no longer constrains the design.
- Hosting is now pure cost with no revenue against it. Host-assistant reading (no server-side model calls) and a hard monthly ceiling matter more. Per-user quotas protect that ceiling.
- Per-user sign-in is still needed. Remembering decisions across sessions means server storage, and storage must be scoped by a validated identity.
  - A skills-only plugin (no server) costs nothing to host but cannot remember a pile between chats, so it can't deliver the core promise.
- A public listing still needs a website, privacy policy, terms, a support contact, a verified org, a demo account and review test cases. Being free does not remove any of these.
- Which plans can install a published third-party plugin with write tools: unverified. The help text says it depends on plan and capabilities.

## 8. Proposed: "where to log results" onboarding (Chris, 2026-10-06; proposal, not decided)

- Onboarding asks for a preferred destination, which is stored as a profile field.
- Day one: Cyft formats results for that destination: Markdown for Notion/Confluence/Evernote, CSV for Google Sheets/Excel, plain text for phone notes, and a task list for PM tools. The user pastes or shares it. Cyft keeps the copy that counts, so "already processed" still works.
- Direct writes into those tools need Cyft to hold each user's OAuth tokens per service. That reverses the boundary in SECURITY.md and CONTRIBUTING.md, adds a review and maintenance cost per integration, and has no server path for Apple Notes. It is deferred until the pilot shows demand; then one integration at a time.
- Unverified: whether ChatGPT will pass Cyft's output to another plugin the user has installed (Notion, Google Drive) in the same chat. Test it in the pilot; don't promise it.
