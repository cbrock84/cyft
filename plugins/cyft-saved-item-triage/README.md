# Cyft: Saved Item Triage plugin

This folder is a skills-only Agent Plugins 1.0 package for a **conversational, one-item Cyft workflow**. It does not connect to Cyft's local store, stdio MCP server, cloud accounts, or a hosted backend. ChatGPT may use its own available research capabilities; the skill requires a source URL, supporting passage or section, and checked date before calling a claim verified.

The route table and vetoes mirror [`cyft/scoring.py`](../../cyft/scoring.py), and the evidence and profile rules come from [`USAGE.md`](../../USAGE.md). A route is a proposal; a person makes the decision.

## Sample review prompts

- "I saved this repository. My goal is to ship a small open source dashboard this month, with no paid hosting. Should I try it?"
- "This vendor pitch promises automated reporting. My goal is to cut manual reporting by five hours a week, but customer data must stay in our account. What should I do with it?"
- "I have not decided on a goal. Is this link universally useful?" Expected: ask for a concrete goal; do not fabricate a score.

## Public listing preparation

The package includes the initial listing, review prompts, all-available-country targeting, release notes, and an icon. The four published HTTPS listing pages are included under `extensions.com.openai.interface`: `websiteURL`, `supportURL`, `privacyPolicyURL`, and `termsOfServiceURL`. The publisher hub, support, privacy, and terms pages were checked live after publication on October 27, 2026; each identifies Cyft or the skills-only plugins and its relevant purpose. Recheck them before upload.

For a skills-only plugin, MCP review cases, a demo recording, and reviewer credentials are not required. This source has not been submitted or published. If packaging it into a ZIP, include this plugin directory as the sole top-level folder and inspect the resulting archive.
