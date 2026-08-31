# MyCodeAgent Strict Task Template

Copy this template into `TODO.md` or a GitHub issue. Replace every placeholder;
tasks containing missing sections, empty sections, or placeholder text are not
eligible for implementation.

```markdown
## TASK-000 | ready | P2 | [FEATURE] <short title> in `workspace/<task_name>/`

### Outcome
<Describe the externally visible result in measurable terms.>

### Context
<Explain why the change is needed and how it fits the existing project.>

### Workspace
- Source: `workspace/<task_name>/Coding/`
- Tests: `workspace/<task_name>/test/`
- Requirements: `workspace/<task_name>/Coding/requirements.txt`
- Rule: All task changes must remain inside `workspace/<task_name>/`.

### Technology Stack
- Runtime: <language and supported version>
- Frameworks/Libraries: <names and major versions, or None>
- Architecture/Pattern: <required design pattern or Not applicable>
- External Systems: <APIs, databases, queues, files, or None>

### Public API
<List required import paths, classes, functions, commands, schemas, or endpoints
with signatures and observable return values. Write "No public API" only when
the task genuinely has none.>

### Functional Requirements
- <Requirement 1 with one observable behavior>
- <Requirement 2 with one observable behavior>

### Input Validation
- <Accepted input types, formats, ranges, defaults, and invalid-input behavior.>

### Error Behavior
- <Exception/error type, message or status expectations, and state after failure.>

### Performance and Operational Requirements
- <Expected workload, complexity/latency/memory/concurrency limits, or explain why
  performance is not material for this task.>

### Security Requirements
- <Trust boundaries, authorization, secret handling, side-effect rules, or explain
  why no task-specific security behavior applies.>

### Edge Cases
- <Empty, boundary, malformed, repeated, failure, concurrency, or platform case.>

### Acceptance Criteria
- <A testable criterion mapped to externally observable behavior.>
- The complete task test suite passes locally with a 100% pass rate.

### Out of Scope
- <Explicitly excluded behavior to prevent accidental scope expansion.>
```

Use `ISSUE-<number>` instead of `TASK-000` for GitHub-derived work orders. A task
must not be marked `ready` until every section contains a deliberate answer.
