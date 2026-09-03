# Using the CLI

## Install

```
pip install cyft[anthropic]     # or cyft[openai], or cyft[all]
```

The core has no dependencies. Only `cyft read` needs a provider SDK, so intake,
scoring, routing and digests work with neither installed.

## Set up

```
cyft init
```

Creates `.cyft/` here and writes a profile template. Open `.cyft/profile.json`
and fill in at least one goal. Nothing can be scored without one, and Cyft will
refuse to guess rather than fall back on a generic score.

```json
{
  "goals": [
    {
      "id": "goal-1",
      "name": "Land three paid audit clients",
      "why": "The only revenue test running this quarter",
      "stop_when": "Fifty conversations and no paid order"
    }
  ],
  "constraints": {
    "can_operate": "nothing I have to babysit",
    "can_buy": "under $50/mo on a personal card",
    "notes": "no customer data leaves our tenancy"
  }
}
```

## Point it at a model

```
cyft presets                                    # what is available
cyft config --preset anthropic                  # uses claude-opus-5
cyft config --preset xai --model MODEL_NAME
cyft config --preset ollama --model MODEL_NAME  # local, no key needed
cyft config                                     # show current settings
```

There are two adapters. `anthropic` speaks the Messages API; everything else
goes through one OpenAI-compatible adapter with a different base URL. Adding a
provider that speaks that format is a preset, not code.

Set the key in the environment. It is never written to `.cyft/config.json`:

```
export ANTHROPIC_API_KEY=...     # or OPENAI_API_KEY, XAI_API_KEY, and so on
```

## Run

```
cyft add ~/Desktop/screenshots ~/notes/links.url https://github.com/some/repo
cyft read
cyft sort
cyft list
cyft digest --mark
```

`add` takes files, folders, or URLs. Identical files merge on a content hash and
links merge on a normalised URL, so the same repository saved four times is one
item. A `.url` file expands into one item per link.

`read` sends each new item to the model and records what it is and what is
claimed, each claim labelled `verified`, `claimed`, `inferred` or `uncertain`.

`sort` asks three questions per item, suggests a route with its reasoning, and
lets you override it. Dealbreakers override the score entirely.

`digest` reports what changed since you last marked one. If nothing changed it
says so in one line.

## What ends up on disk

```
.cyft/
  profile.json          your goals and constraints
  config.json           provider and model, mode 0600, no key in it
  state.json            digest watermark
  items/<id>/item.json  one record per distinct thing
  items/<id>/original.* the bytes you supplied
```

Plain files. Read them with anything. Nothing is uploaded except the item being
read, to the provider you configured.

## Costs

One screenshot is roughly 1,800 input and 400 output tokens. Check your
provider's current rates before running a large batch, and start with `--limit`.

```
cyft read --limit 5
```

## Using it from your assistant instead

Cyft can run as an MCP server, which is the path that needs no API key at all.
Instead of Cyft calling a model, the assistant you already use calls Cyft: it
asks for the next item, is handed the screenshot, and hands back what it found.

Claude Desktop, in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cyft": {
      "command": "cyft",
      "args": ["--root", "/absolute/path/to/your/.cyft", "mcp"]
    }
  }
}
```

Claude Code:

```
claude mcp add cyft -- cyft --root /absolute/path/to/your/.cyft mcp
```

Use an absolute `--root`. The server is started by your client in a working
directory you do not control, so a relative path will not find your run store.

Then say something like: *work through my cyft pile.* The eight tools are

| Tool | What it does |
| --- | --- |
| `cyft_status` | Counts by status and route, plus the goals |
| `cyft_profile` | The full profile |
| `cyft_add` | Add files, folders or URLs |
| `cyft_next_unread` | The next item, with the screenshot attached |
| `cyft_record_reading` | Store what it is and what is claimed |
| `cyft_next_undecided` | The next item awaiting a decision, with its claims |
| `cyft_decide` | Give goal, help and cost; Cyft computes the route |
| `cyft_digest` | What changed |

Two things hold here as everywhere else. Item content reaches your assistant
wrapped in a warning that it is data to describe and not instruction to follow,
and nothing an item says can set its own route. Routes are computed from your
answers, and a dealbreaker outranks any score.

Decisions made this way are recorded with `decided_by: "mcp-client"`, so you can
tell later which judgements were yours and which your assistant's.
