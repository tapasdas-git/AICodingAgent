# Code Review Guidelines and Guardrails

Approve only when the implementation, its tests, and the review evidence satisfy
every applicable requirement below. Folder placement and a passing happy-path
test suite are necessary, but never sufficient. Return `CHANGES_REQUESTED` with
specific file-and-line findings whenever a material requirement is unmet.

## 1. Understand the task and technology stack

- Read the complete task, its architecture and acceptance criteria, dependency
  declarations, project configuration, and relevant existing code before judging
  the implementation.
- Identify and report the language/runtime version, frameworks, libraries,
  persistence or network components, concurrency model, and architectural pattern
  that are actually applicable. Never apply framework-specific rules by guesswork.
- Check usage against the installed/declared major version. Reject deprecated,
  incompatible, invented, or incorrectly used APIs.
- Confirm the design follows the task's requested architecture and the repository's
  established conventions without unnecessary abstractions or dependencies.

## 2. Correctness and behavior

- Trace every acceptance criterion to a concrete implementation path and at least
  one meaningful test or focused reviewer reproduction.
- Inspect normal, boundary, empty, malformed, failure, and recovery paths. Include
  state consistency after exceptions and repeated calls where state is retained.
- Validate public inputs and external data at the boundary. Errors must be explicit,
  useful, and consistent; failures must not silently corrupt or partially update state.
- Check package-style imports and the public API from the repository root, not only
  imports that happen to work from the source directory.
- Look for off-by-one errors, invalid assumptions, mutation leaks, resource leaks,
  race conditions, ordering problems, and incorrect exception handling when relevant.

## 3. Code quality and maintainability

- Code must be readable, cohesive, typed at public boundaries, and consistent with
  the repository style. Names should express intent and comments should explain why,
  not restate the code.
- Functions and classes should have focused responsibilities. Reject duplicated
  logic, needless complexity, dead code, broad exception swallowing, hidden global
  state, and premature abstraction that makes the task harder to maintain.
- Dependencies must be justified, declared, version-compatible, and used through
  supported APIs. Avoid a dependency when the standard library is sufficient.
- Public behavior and important constraints must be discoverable through types,
  validation, docstrings, or tests as appropriate to the project.

## 4. Performance and resource use

- Determine the expected input size, frequency, latency, memory, I/O, and concurrency
  characteristics from the task and code. State when performance is not material.
- Review algorithmic time and space complexity. Reject avoidable quadratic work,
  unbounded accumulation, repeated full scans, N+1 I/O, unnecessary serialization,
  blocking I/O in asynchronous paths, or loading unbounded data into memory.
- Verify expensive resources are created, reused, bounded, timed out, and released
  correctly. Check batching, caching, pagination, retry/backoff, and concurrency only
  where the workload requires them; do not demand speculative optimization.
- A performance finding must describe the execution path, realistic workload,
  expected impact, and a concrete fix. For a performance-sensitive requirement,
  obtain evidence with a focused benchmark, complexity argument, or resource-bound
  test; intuition alone is not enough for approval or rejection.

## 5. Security and operational safety

- No secrets, credentials, private keys, or sensitive values may be committed.
- Treat user, file, network, database, tool, and model output as untrusted. Validate
  before authorization or any state-changing operation.
- Check injection, path traversal, unsafe deserialization, excessive permissions,
  sensitive logging, denial-of-service bounds, and dependency risk where applicable.
- External calls must have appropriate timeouts and deterministic failure behavior.
  Business-critical side effects must be authorized and validated before execution.

## 6. Test quality

- Run the exact task suite independently. Passing tests do not prove completeness.
- Tests must assert behavior rather than implementation details and must be isolated,
  deterministic, readable, and capable of failing when the behavior is broken.
- Require coverage of happy paths, boundaries, invalid inputs, exceptions, state after
  failure, and regression cases for corrected defects. Add concurrency, performance,
  security, integration, or platform cases when the task makes them relevant.
- Inspect fixtures, mocks, and assertions for false positives. Reject tests that only
  call code without meaningful assertions, mock away the behavior under review, depend
  on execution order, or require uncontrolled live services.
- When an important scenario is missing, run a focused non-mutating reproduction and
  request a durable regression test rather than approving based on manual evidence alone.

## 7. Scope and repository hygiene

- Application code belongs in `<task_directory>/Coding/`; tests and fixtures belong
  in `<task_directory>/test/` unless the task explicitly specifies another layout.
- Inspect tracked and untracked files. Reject unrelated refactoring, generated files,
  caches, logs, temporary scripts, and changes outside the selected task's authority.
- Run the relevant tests and repository sanity checks such as `git diff --check`.

## 8. Evidence and verdict

- Report the identified technology stack and the checks applied to it.
- Report correctness, code quality, performance, security, and test-quality results.
- Use severity based on impact: Critical, High, Medium, or Low. Do not block approval
  for purely optional preferences; label those as non-blocking observations.
- Each blocking finding must include a stable identifier, severity, file and line,
  the concrete defect and impact, evidence or reproduction, and a specific required fix.
- Return `APPROVED` only when there are no blocking findings and all applicable review
  areas have evidence. Otherwise return `CHANGES_REQUESTED`.
