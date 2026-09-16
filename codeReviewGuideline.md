# Shared Implementation and Code Review Guidelines

This is the single quality standard for both the implementer and reviewer.
Folder placement and passing happy-path tests are necessary, but never sufficient.
Apply only rules relevant to the task's declared technology stack and workload.

## Documentation

- **DOC-01 — Public modules:** Every public Python module must have a useful module docstring.
- **DOC-02 — Public API:** Every public class, function, and method must have a useful docstring explaining its contract or purpose. A class docstring covers its constructor unless construction has non-obvious behavior.
- **DOC-03 — Non-obvious decisions:** Complex private algorithms, security invariants, performance tradeoffs, protocol ordering, and state-changing behavior require concise comments explaining why the design is necessary.
- **DOC-04 — Comment quality:** Comments must explain intent, constraints, or tradeoffs rather than restating syntax. They must remain accurate after code changes.
- **DOC-05 — No placeholders:** Submitted code must not contain unresolved `TODO`, `FIXME`, `XXX`, or placeholder comments.

Simple private helpers, obvious accessors, and clearly named tests do not require docstrings. Do not add comments merely to increase comment volume.

## Correctness and architecture

- **COR-01 — Requirement coverage:** Trace every acceptance criterion to an implementation path and meaningful test.
- **COR-02 — Boundaries:** Validate public inputs and untrusted external data at system boundaries.
- **COR-03 — Failure safety:** Exceptions must be explicit and must not leave partial or corrupted state.
- **COR-04 — Compatibility:** Imports, APIs, and patterns must match the declared runtime and dependency major versions.
- **COR-05 — Maintainability:** Code must be cohesive, readable, typed at public boundaries, and free of needless duplication, dead code, hidden global state, or broad exception swallowing.

## Performance and resource use

- **PERF-01 — Proportional review:** Establish the realistic workload before evaluating performance; do not demand speculative micro-optimization.
- **PERF-02 — Complexity:** Reject material avoidable quadratic work, repeated full scans, N+1 I/O, unbounded accumulation, and unnecessary serialization.
- **PERF-03 — Resources:** Expensive resources must be bounded, timed out, reused or released appropriately. Blocking I/O must not run directly in asynchronous execution paths.
- **PERF-04 — Evidence:** A blocking performance finding requires a realistic execution path and impact plus a benchmark, complexity argument, or resource-bound reproduction.

## Security and operational safety

- **SEC-01 — Secrets:** Never commit credentials, tokens, passwords, private keys, or sensitive values.
- **SEC-02 — Untrusted data:** Validate user, file, network, database, tool, and model output before authorization or state changes.
- **SEC-03 — Side effects:** Authorization and complete input validation must occur before business-critical side effects.
- **SEC-04 — External calls:** External calls require task-appropriate timeouts and deterministic error behavior.

## Test quality

- **TEST-01 — Meaningful assertions:** Tests must assert observable behavior and be capable of failing when that behavior breaks.
- **TEST-02 — Coverage matrix:** Cover every acceptance criterion plus applicable boundaries, malformed inputs, exceptions, failure-state consistency, and regressions.
- **TEST-03 — Isolation:** Tests must be deterministic, order-independent, offline where required, and must not mock away the behavior under review.
- **TEST-04 — Test review:** The reviewer must inspect test source, fixtures, mocks, and assertions—not merely run pytest.
- **TEST-05 — Missing cases:** A significant missing scenario requires a durable regression test. A manual reproduction alone is not sufficient for approval.

## Scope and repository hygiene

- **SCOPE-01 — Isolation:** Task code belongs in `<task_directory>/Coding/` and tests in `<task_directory>/test/` unless the task explicitly requires another structure.
- **SCOPE-02 — Focus:** Reject unrelated refactoring, caches, logs, generated artifacts, or changes outside the selected task's authority.
- **SCOPE-03 — Complete inspection:** Inspect tracked and untracked task files; `git diff` alone is not complete evidence.

## Evidence and verdict

- **REVIEW-01 — Technology context:** Identify the actual runtime, frameworks, dependency versions, architecture, I/O boundaries, and workload before reviewing.
- **REVIEW-02 — Evidence:** Every blocking finding must include a guideline ID, severity, existing file and line, concrete defect and impact, direct evidence, and specific required fix.
- **REVIEW-03 — No invented findings:** Never claim an API rule, test result, performance problem, or line-level defect without verifying it from repository files, installed/declaration metadata, or an executed non-mutating reproduction.
- **REVIEW-04 — Severity:** Use Critical, High, Medium, or Low based on user impact. Optional preferences are non-blocking observations.
- **REVIEW-05 — Approval:** Return `APPROVED` only when deterministic checks pass, all applicable requirements have evidence, tests are meaningful, and no blocking findings remain. Otherwise return `CHANGES_REQUESTED`.
