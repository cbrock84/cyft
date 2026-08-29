# Contributing

This is a design document at the moment, not an implementation. That shapes what is
useful to contribute.

## Most useful right now

**Run the method by hand and tell me where it broke.** The pipeline has been run once,
over one person's backlog. Everything in `README.md` is a hypothesis with exactly one
data point behind it. A second honest account of using it is worth more than code.

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

## Less useful

- An implementation, before the method has been run enough times to know which stages
  are real. Building now freezes guesses as architecture.
- Integrations that hold credentials. This is a deliberate boundary, not an oversight.
  See `intake.md`.
- A global ranking of tools. There is no global user, so there is no such ranking.

## Ground rules

- Every factual claim carries a label and a source. The vocabulary is closed:
  claimed, verified, tested, adopted, rejected, inferred, uncertain.
- Numbers that move are readings with a date, not properties.
- Normal hyphens only. No em dash or en dash.
- Contributions are under Apache-2.0, per section 5 of the license. No separate
  contributor agreement is needed.
