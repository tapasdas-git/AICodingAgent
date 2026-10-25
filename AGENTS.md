# MyCodeAgent Persistent Learning Memory

This file contains durable engineering lessons learned from verified test failures
and adversarial review findings. The supervisor, implementer, and reviewer must
read it before working on a task and apply every lesson relevant to the current
task, even when the task uses different names or directories.

## Usage rules

- Treat lessons as preventative checks, not as task requirements that broaden scope.
- Apply a lesson only when its failure mode is relevant to the current design.
- Verify each relevant lesson with implementation evidence or a regression test.
- Do not weaken, delete, or rewrite earlier lessons during task execution.
- Add lessons only through the `record_agent_learning` workflow tool.
- Record general root causes and prevention rules; never store secrets, raw prompts,
  complete reports, transient paths, or speculative conclusions.
- A failing test or a `CHANGES_REQUESTED` reviewer finding is valid evidence. A
  model guess without reproducible evidence is not.

## Learned engineering rules

<!-- learning:numeric-precision-before-conversion -->
### Preserve numeric precision before conversion

- Category: review finding
- Mistake: Converting arbitrary integral or `Real` operands to `float` before an operation can lose large-integer precision or overflow.
- Prevention: Preserve supported numeric types through calculation, explicitly define accepted numeric domains, and test integers beyond IEEE-754 exact range.
- Evidence: Prior calculator review found lossy eager float conversion.

<!-- learning:validate-custom-real-conversion -->
### Validate custom real-number conversion safely

- Category: review finding
- Mistake: Type checks against `numbers.Real` alone do not guarantee that conversion or finiteness checks are safe for custom implementations.
- Prevention: Validate conversion failures and non-finite values explicitly, and test custom `Real` implementations plus positive and negative infinity.
- Evidence: Prior calculator review found non-built-in `Real` edge cases bypassing intended validation.

## Automatically recorded lessons

New deduplicated lessons are appended below this heading by the workflow.
