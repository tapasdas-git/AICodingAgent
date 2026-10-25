# Agent Harness Summary

## Executive summary

MyCodeAgent uses **Omnigent as the workflow runner and agent orchestration layer**
and **Codex as the active model harness**. The active workflow contains one
persistent supervisor and two child-agent tools: an implementer and an adversarial
reviewer. Python code outside the agents owns task selection, state transitions,
test execution, logging, worktree isolation, timeouts, changelog generation, Git
operations, and pull-request delivery.

There is currently only one active LLM harness/provider route:

```text
MyCodeAgent CLI -> Omnigent -> Codex supervisor
                              |-> Codex implementer
                              `-> Codex reviewer
```

The repository contains comments and older documentation describing Claude as an
implementation option, but no active workflow routes an agent to Claude or
Anthropic.

## Active harness configuration

The active runtime is configured by two files:

- `workflow_runtime.toml` selects the Omnigent executable, Codex harness, model,
  reasoning effort, timeout, and token budgets.
- `coding_agent.yaml` defines the supervisor prompt, child agents, deterministic
  tools, sequencing rules, and report contracts.

Current effective settings are:

| Setting | Effective value | Purpose |
| --- | --- | --- |
| Workflow runner | Omnigent 0.8.2 | Loads and executes the workflow definition |
| Runner command | `/Users/tapasdas/.local/bin/omnigent` | Local Omnigent executable |
| Harness | `codex` | Required model-execution harness |
| Model | `gpt-5.4-mini` | Model passed to the supervisor and both child agents |
| Supervisor effort | `medium` | Default workflow reasoning effort |
| Implementer effort | `medium` | Inherits the configured workflow effort |
| Reviewer effort | `high` | Explicitly raised for adversarial review |
| Workflow timeout | 1,800 seconds | Hard process-level ceiling |
| Combined task budget | 400,000 tokens | Aggregate supervisor and child ceiling |
| Supervisor budget | 150,000 tokens | Native supervisor-goal ceiling |
| Implementer budget | 175,000 tokens per invocation | Child ceiling, reduced by task remainder when necessary |
| Reviewer budget | 75,000 tokens per invocation | Child ceiling, reduced by task remainder when necessary |

`src/mycodeagent/runner.py` rejects any configured harness other than `codex`,
renders the environment placeholders into a temporary copy of
`coding_agent.yaml`, and launches the workflow approximately as follows:

```bash
omnigent run <rendered-coding-agent.yaml> \
  --harness codex \
  --model gpt-5.4-mini \
  --no-session \
  -p <workflow-request>
```

The `--no-session` option means each CLI workflow invocation starts without
reusing an earlier Omnigent session. Persistence within a task comes from keeping
one supervisor alive for the complete implementation/review loop.

## Agent roles

### Persistent supervisor

The top-level `executor` in `coding_agent.yaml` is the supervisor. It does not
normally write task code or perform Git delivery. Its responsibilities are to:

- create and monitor its native token-budget goal;
- invoke exactly one child or deterministic tool at a time;
- wait for each child agent's terminal report;
- preserve implementation, test, and review observations in one context;
- route complete test or review findings back to the implementer;
- enforce a maximum of five implementation/remediation iterations;
- stop on timeout, tool error, missing report, iteration exhaustion, or budget
  exhaustion; and
- return the final structured workflow report.

The supervisor implements a bounded ReAct-style control cycle:

```text
decision -> one tool action -> terminal observation -> next decision
```

Child agents never communicate directly with each other. Every result returns to
the supervisor, which alone decides the next stage.

### Implementer agent

`implement_task` is an Omnigent `type: agent` tool using the Codex harness. It:

- reads the selected task and referenced repository context;
- creates or modifies source only under the task's `Coding/` directory;
- creates tests only under the task's `test/` directory;
- converts acceptance criteria into implementation and test evidence;
- uses validated configuration and injectable dependencies for agentic features;
- handles both initial implementation and later remediation requests;
- runs focused tests before reporting completion; and
- returns a structured Markdown report with exact native token usage.

For remediation, the supervisor passes the review or test findings back unchanged.
The implementer must fix every actionable finding and add regression coverage
without broadening the task scope.

### Reviewer agent

`review_change` is a separate Omnigent `type: agent` tool using Codex with high
reasoning effort. It is intentionally adversarial and read-only. It:

- reads the complete task and `codeReviewGuideline.md`;
- inspects tracked and untracked files in the selected task workspace;
- maps architecture, security, and acceptance criteria to code and tests;
- reruns the task tests independently;
- performs credential and unsafe-side-effect checks;
- probes missing adversarial cases with non-mutating fakes or reproductions; and
- returns exactly `APPROVED` or `CHANGES_REQUESTED` with actionable findings.

The reviewer cannot contact the implementer. A `CHANGES_REQUESTED` verdict goes
back to the supervisor, which decides whether the remaining iteration and token
budgets permit remediation.

## Deterministic tools exposed to the supervisor

The workflow also exposes Python functions as tools. These are not model agents or
harnesses:

| Tool | Implementation | Responsibility |
| --- | --- | --- |
| `record_stage_event` | `mycodeagent.workflow_tools` | Writes lifecycle transitions to the task trace |
| `record_token_usage` | `mycodeagent.workflow_tools` | Aggregates supervisor snapshots and child invocation usage |
| `record_agent_report` | `mycodeagent.workflow_tools` | Stores redacted, deduplicated terminal agent reports |
| `execute_task_tests` | `mycodeagent.workflow_tools` | Runs the selected task's pytest suite deterministically |

This split is important: agents make judgment-heavy implementation and review
decisions, while Python performs verifiable operations and records their evidence.

## Workflow modes

The CLI selects how much of the harness runs:

| Mode or command | Harness behavior |
| --- | --- |
| `submit --mode 1` / `run TASK-ID` | Supervisor invokes only the implementer stage |
| `submit --mode 2` / `verify TASK-ID` | One supervisor runs implementation, deterministic tests, review, and bounded remediation |
| `submit --mode 3` | Runs mode 2, then Python delivery only after final `APPROVED` |
| `review TASK-ID` | Runs one read-only reviewer stage |
| `review TASK-ID --remediate` | Reviews, conditionally remediates, tests, and re-reviews within one supervisor context |
| `deliver TASK-ID --approved` | Runs deterministic delivery; no LLM agent performs delivery |
| `github-submit` | Selects a GitHub Project issue, converts it to a local work order, then uses the same workflow modes |

Mode 3 does not give an agent Git or GitHub authority. After an approved report,
`src/mycodeagent/delivery.py` invokes `scripts/workflow_helpers.py` to update the
changelog, validate the approved Git identity and remote, commit scoped files,
push the branch, and create the pull request.

## End-to-end stage flow

The active mode 2/3 path is:

```text
CLI selects one ready task
  -> optional origin-based isolated Git worktree
  -> Python marks task working
  -> runner renders coding_agent.yaml
  -> Omnigent starts persistent Codex supervisor
  -> supervisor invokes Codex implementer
  -> Python runs isolated task tests
  -> supervisor invokes Codex reviewer
       -> APPROVED: verification completes
       -> CHANGES_REQUESTED: findings return to supervisor
            -> Codex implementer remediates
            -> Python reruns tests
            -> Codex reviewer re-reviews
            -> repeat, up to iteration 5 and within all budgets
  -> supervisor returns structured final report
  -> Python validates the verdict and task state
  -> mode 3 only: deterministic changelog/Git/PR delivery
```

## Isolation and runtime controls

- `--worktree` creates `feature/<task-id>` from the commit at the remote default
  branch and executes the task inside a dedicated worktree.
- The primary process freezes the selected task into a work-order file so the
  isolated process sees only the intended task.
- Current runtime modules are overlaid into the origin-based worktree during the
  run, allowing local harness fixes to be tested without permanently copying them
  into task output.
- `PYTHONPATH` and `MYCODEAGENT_*` environment variables point the isolated CLI
  and Omnigent tools at the intended runtime, workflow, settings, logs, and test
  interpreter.
- The runner starts a process group, captures combined output, enforces the hard
  timeout, and terminates the complete process tree on timeout.
- Omnigent is configured with `os_env.sandbox.type: none`; therefore safety is
  provided by workflow instructions, task-directory rules, worktree isolation,
  deterministic Python gates, and delivery policy rather than an Omnigent OS
  sandbox.

## Token accounting

Each role creates a native goal with its assigned budget. The supervisor records
cumulative snapshots, while implementer and reviewer usage is recorded per
invocation. The ledger computes:

```text
task usage = latest supervisor cumulative usage
             + sum(all implementer invocation usage)
             + sum(all reviewer invocation usage)
```

The workflow must stop when either the combined task budget or an individual
agent budget is exhausted. Usage and exhaustion state are persisted in
`logs/<TASK_ID>_usage.json`; readable snapshots are written to
`logs/<TASK_ID>.logs`, and full agent reports are stored in
`logs/<TASK_ID>.raw.logs`.

## Active versus inactive harness definitions

### Active

- `coding_agent.yaml`: the workflow loaded by the CLI.
- `workflow_runtime.toml`: the effective harness/model/budget settings.
- `src/mycodeagent/runner.py`: validates `harness = "codex"` and launches
  Omnigent.

### Inactive or informational

- `omnigent_bugfix_workflow.yaml` is a legacy workflow and is not loaded by the
  current CLI. It includes agent-based changelog and pull-request stages that the
  active design has replaced with deterministic Python delivery.
- The commented `[models.claude_implementer]` block in `workflow_runtime.toml` is
  inactive.
- The comment saying "Claude implements and Codex reviews" is stale. Both active
  child executors specify `harness: codex` and the same configured model.
- Agent runtimes generated inside `workspace/` are task deliverables, not part of
  the MyCodeAgent development harness. For example, the flight-booking task has
  its own application-level agents and injected model client, but those run inside
  the produced application rather than orchestrating MyCodeAgent itself.

## Primary implementation references

- `src/mycodeagent/__main__.py`: CLI commands and mode routing.
- `src/mycodeagent/submission.py`: task lifecycle and delivery gating.
- `src/mycodeagent/orchestration.py`: supervisor-mode prompt selection.
- `src/mycodeagent/runner.py`: Omnigent launch, environment, timeout, output, and
  protocol handling.
- `src/mycodeagent/workflow_tools.py`: deterministic test, trace, report, and token
  tools.
- `src/mycodeagent/worktrees.py`: isolated branch/worktree execution and runtime
  overlay.
- `src/mycodeagent/delivery.py`: deterministic post-approval delivery.
- `src/mycodeagent/github_tasks.py`: GitHub Project issue ingestion.
- `coding_agent.yaml`: active supervisor and child-agent contracts.
- `workflow_runtime.toml`: active model, harness, timeout, and budget values.
