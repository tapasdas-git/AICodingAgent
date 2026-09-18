# MyCodeAgent Quality Gates

MyCodeAgent applies deterministic checks, independent review requirements, workflow controls, and delivery safeguards before a task can be delivered.

## Deterministic implementation and test gates

- **Task workspace:** The selected task must have a valid workspace containing both `Coding/` and `test/` directories.
- **Workspace isolation:** Implementation must remain inside the authorized task workspace. Unrelated files, caches, logs, generated artifacts, and out-of-scope refactoring are rejected.
- **Python syntax:** Every Python source and test file is parsed with Python's AST parser. Syntax errors fail the quality check.
- **Module documentation:** Every public Python module must have a useful module docstring.
- **Public API documentation:** Public classes, functions, and methods must have useful docstrings explaining their contracts or purposes.
- **No placeholders:** Unresolved `TODO`, `FIXME`, `XXX`, and `PLACEHOLDER` comments cause the quality check to fail.
- **Meaningful test assertions:** Every `test_*` function must contain a meaningful assertion, `pytest.raises`, or an equivalent assertion call.
- **Isolated tests:** The workflow runs `python -m pytest -v <task_workspace>/test`. Review cannot start unless pytest and the deterministic quality checks pass.
- **Test timeout:** The isolated test suite has a 300-second execution timeout.
- **Test-result trace:** When enabled, verbose individual pytest results are appended to `logs/<TASK_ID>_test.log`.

## Correctness and review gates

- **Acceptance coverage:** Every applicable architecture, security, and acceptance requirement must map to an implementation path and a meaningful test.
- **Correctness:** The reviewer checks public input validation, error handling, failure-state consistency, API behavior, dependency compatibility, maintainability, and hidden state.
- **Test quality:** The reviewer reads tests, fixtures, mocks, and assertions rather than relying only on a passing pytest result.
- **Scenario coverage:** Tests are reviewed for happy paths, boundaries, malformed input, exceptions, failure-state consistency, regressions, order independence, and nondeterminism.
- **No false confidence from mocking:** Tests must not mock away the behavior they claim to verify.
- **Durable regressions:** A significant missing scenario requires an automated regression test; a manual reproduction alone is insufficient for approval.
- **Independent execution:** The reviewer independently runs the selected task's tests and records the exact command and result.
- **Passing tests are necessary but insufficient:** The reviewer must inspect actual execution paths and implementation quality before approval.

## Performance and resource gates

- **Realistic workload:** Performance is evaluated against the workload declared or reasonably implied by the task.
- **Complexity:** The reviewer checks for avoidable quadratic work, repeated full scans, N+1 I/O, unnecessary serialization, and unbounded accumulation.
- **Resource handling:** Expensive resources must be bounded, reused, timed out, or released appropriately.
- **Async safety:** Blocking I/O must not execute directly in asynchronous paths.
- **Evidence requirement:** A blocking performance finding requires a realistic execution path and impact plus a benchmark, complexity argument, or resource-bound reproduction.
- **No speculative optimization:** Review must not block delivery solely for unsupported micro-optimization preferences.

## Security and integration gates

- **Secret scanning:** Reviewed source files, including untracked files, are inspected for credentials, tokens, passwords, private keys, and other sensitive values.
- **Untrusted data:** User, file, network, database, tool, and model output must be validated before authorization or state changes.
- **Side-effect safety:** Authorization and complete input validation must occur before booking, payment, deletion, inventory, or other business-critical side effects.
- **External calls:** External calls require task-appropriate timeouts and deterministic error behavior.
- **Injectable integrations:** External clients must be injectable, support deterministic offline fakes, and must not be constructed during module import.
- **Agentic-system controls:** LLM and tool-based implementations require validated schemas, allowlisted tools, complete tool-call batch validation, correct assistant/tool message ordering, matching tool-call IDs, multiple-call handling, and bounded loop termination.

## Review evidence and anti-hallucination gates

- **Technology context:** The reviewer must identify the actual runtime, frameworks, dependency versions, architecture, I/O boundaries, and expected workload before reviewing.
- **Complete inspection:** The reviewer inspects tracked and untracked task files. `git diff` alone is not accepted as complete evidence.
- **Structured findings:** Every blocking finding must provide a recognized guideline ID, severity, existing file, valid line number, concrete defect, impact, direct evidence, and specific required fix.
- **Finding validation:** Findings citing nonexistent files, invalid line numbers, paths outside the task workspace, unknown guideline IDs, or duplicate finding IDs are rejected.
- **No invented findings:** The reviewer must not claim an API requirement, test result, performance defect, or line-level issue without repository or executed-reproduction evidence.
- **Explicit verdict:** The reviewer must begin its report with exactly `APPROVED` or `CHANGES_REQUESTED`.
- **Approval standard:** Approval is allowed only when deterministic checks pass, applicable requirements have evidence, tests are meaningful, and no blocking findings remain.

## Workflow and remediation gates

- **Serialized stages:** Implementation, testing, review, remediation, and re-review run in sequence. Later stages cannot begin before the preceding stage finishes successfully.
- **Test-before-review:** Review cannot begin after a failed implementation or before the authoritative task tests pass.
- **Unchanged feedback:** Complete test failures and reviewer findings are forwarded to the implementer without alteration.
- **Remediation verification:** Tests must pass again after remediation before re-review begins.
- **Iteration limit:** The implementation, test, review, and remediation loop is limited to five iterations.
- **Token limits:** Supervisor, implementer, reviewer, and combined workflow token budgets are enforced.
- **Persistent evidence:** Stage events, agent reports, test output, findings, and final decisions are written to task-specific trace files.

## Delivery gates

- **Approved review required:** Pull-request delivery is allowed only when the final review status is exactly `APPROVED`.
- **Repository verification:** Delivery verifies that execution is occurring from the expected repository root.
- **Remote verification:** The configured `origin` must match the approved Git remote.
- **GitHub identity verification:** The authenticated GitHub account must match the approved GitHub login.
- **Task and branch validation:** The task identifier, task directory, attached feature branch, base branch, and remote branch ancestry are validated before delivery.
- **Deterministic delivery:** Python automation, rather than an implementation or review agent, owns changelog updates, commits, pushes, and pull-request creation.

## Known delivery gap

- The current delivery staging command includes only the task's `Coding/` directory, `test/` directory, and `CHANGELOG.md`.
- Workspace-level artifacts such as `<task_workspace>/README.md` can therefore remain untracked and be omitted from the pull request.
- The delivery implementation should stage the complete authorized task directory plus `CHANGELOG.md`, followed by a scope check before committing.
