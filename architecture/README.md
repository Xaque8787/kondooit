# Architecture

This directory holds the project's architectural direction: principles, boundaries, and open questions.

It is distinct from:

- `vision/` — the product North Star (what we are building and why).
- `decisions/` — ADRs recording specific decisions that were made.
- `research/` — cross-project capability analysis.

`architecture/` describes the **shape** of the system; `decisions/` records the **choices** that produced that shape.

## Contents

- `PRINCIPLES.md` — architectural principles and invariants.
- `OPEN_QUESTIONS.md` — unresolved architectural questions, actively maintained.

## Conventions

- Do not lock in plugin interfaces here until the relevant research is complete.
- When an open question is resolved, move it out of `OPEN_QUESTIONS.md` and record the decision as an ADR in `decisions/`.
- Never edit a resolved decision in place — supersede it with a new ADR.
