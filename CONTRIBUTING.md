# Contributing

There is a working command line tool, and a method behind it that has been run over one
real backlog. That shapes what is useful to contribute.

## Most useful right now

**Run it against your own pile and tell me where it broke.** The scoring questions and the
routing table came out of one person's backlog of 158 items, so they have exactly one data
point behind them. A second honest account of using it is worth more than a feature.

The open questions at the end of `README.md` are the ones I actually cannot answer.
The profile step is the weakest: writing down what you are genuinely trying to do this
quarter, with a kill criterion attached, is harder than it sounds and is the step most
likely to be skipped.

## Also useful

- An adapter. The contract is one JSON file, described in `intake.md`. Anything that
  can write files to a directory qualifies, so an adapter can be a shell script or a
  Shortcut, and does not need to live in this repository.
- A profile example for a role that is not covered. Careful here: a library of profile
  templates could quietly become the generic ranking this project exists to avoid.
- Schema problems. If a schema cannot express something real you encountered, that is
  a bug in the design.
- A provider. Everything except Anthropic speaks the OpenAI wire format, so a new one is
  usually a base URL and a model name rather than new code.

## Less useful

- Dependencies in the core. It is Python 3 standard library only, deliberately, and CI
  fails on any dependency declared outside an extra. Provider SDKs are optional extras,
  imported lazily.
- Integrations that hold credentials for the places your material lives. This is a
  deliberate boundary, not an oversight. See `intake.md` and `SECURITY.md`.
- A global ranking of tools. There is no global user, so there is no such ranking.

## Ground rules

- Every factual claim carries a label and a source. The vocabulary is closed:
  claimed, verified, tested, adopted, rejected, inferred, uncertain.
- Numbers that move are readings with a date, not properties.
- Normal hyphens only. No em dash or en dash.
- Contributions are under Apache-2.0, per section 5 of the license. No separate
  contributor agreement is needed.
