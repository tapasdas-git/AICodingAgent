# MyCodeAgent — Architecture and Process Reference

This document summarizes the workflow, harness, and Task 101 improvements made in this working period. It is a reference guide, not an execution log. Runtime traces are written separately to `logs/<TASK_ID>.logs`.

## Implementation file map

| File | What it performs | Key responsibility |
| --- | --- | --- |
| `coding_agent.yaml` | Defines the LLM-driven workflow | Instructs Omnigent/Codex to implement, test, review, optionally remediate, and return a structured report. Git and PR actions are deliberately excluded. |
| `workflow_runtime.toml` | Defines runtime defaults | Holds model, harness, effort, and timeout-related defaults used when launching the agent runner. |
| `pyproject.toml` | Publishes the command-line program | Registers `mycodeagent` and its Python package configuration. |
| `src/mycodeagent/__main__.py` | Parses and routes CLI commands | Handles `submit`, `review`, `deliver`, modes 1–3, task selection, timeout options, and worktree mode. |
| `src/mycodeagent/tasks.py` | Reads and updates task records | Parses `TODO.md`, derives omitted workspace metadata, validates explicit paths, selects ready tasks, and changes task status safely. |
| `src/mycodeagent/submission.py` | Coordinates a task submission | Applies the selected mode, records implementation/test/review outcomes, and permits delivery only after final approval. |
| `src/mycodeagent/runner.py` | Runs the Omnigent workflow | Renders the task prompt, launches the configured agent workflow, streams bounded output, and handles timeout/process cleanup. |
| `src/mycodeagent/protocol.py` | Validates terminal reports | Extracts the last complete implementation, review, delivery, or overall workflow report from streamed output. |
| `src/mycodeagent/tracing.py` | Creates task trace logs | Writes secret-redacted lifecycle/raw traces and provides configurable debug, info, and error console output. |
| `src/mycodeagent/orchestration.py` | Selects workflow depth | Builds implementation/review/remediation mode instructions and routes them to the runner. |
| `src/mycodeagent/workflow_tools.py` | Runs deterministic workflow tools | Records stage events and executes isolated tests with the worktree import path configured explicitly. |
| `src/mycodeagent/paths.py` | Resolves runtime paths | Makes root, workflow, trace, and configuration paths work correctly in both the main checkout and a task worktree. |
| `src/mycodeagent/worktrees.py` | Isolates work by task | Creates a branch/worktree from origin's resolved default branch, prepares a task-local work order, invokes the child submission, and syncs the final status back. |
| `src/mycodeagent/delivery.py` | Performs deterministic delivery | Enforces final-review approval and invokes the Python Git/GitHub helper for changelog, commit, push, and PR creation. |
| `scripts/workflow_helpers.py` | Executes Git and GitHub operations | Validates the approved remote/account, updates the changelog, creates commits, pushes the task branch, and opens a task-derived PR title. |
| `git_approval.toml` | Restricts delivery targets | Stores the approved GitHub identity and remote policy checked before any push or pull-request action. |
| `TODO.md` | Defines the work backlog | Stores task headings and optional scope details; workspace paths can be supplied explicitly or derived dynamically. |
| `README.md` | Documents operator usage | Explains command-line modes, review/remediation, worktrees, trace locations, delivery rules, and troubleshooting. |

## High-level process flow: ready task to pull request

The end-to-end delivery path is initiated with:

```bash
mycodeagent submit --worktree --mode 3
```

At a high level, control moves through the following components:

```text
TODO.md
  |
  | 1. Parse tasks and select the first `ready` entry
  v
Python task parser (`tasks.py`)
  |
  | 2. Derive/validate workspace and atomically mark `working`
  v
Task worktree (`worktrees.py`)
  |
  | 3. Create feature branch + isolated checkout + frozen work order
  v
Submission/orchestration (`submission.py`, `orchestration.py`, `runner.py`)
  |
  | 4. Implementation agent writes application code and tests
  v
Deterministic verifier (`workflow_tools.py`)
  |
  | 5. Run `<python> -m pytest` inside the active worktree
  v
Review agent
  |
  +-- APPROVED ---------------------------------------------+
  |                                                         |
  +-- CHANGES_REQUESTED -> implementation remediation       |
                              |                              |
                              +-> tests -> re-review --------+
                                                             v
                                              Python approval gate
                                                             |
                                                             | 6. Changelog, commit,
                                                             |    push, create PR
                                                             v
                                                  Pull request + `delivered`
```

### 1. Task discovery and validation

`parse_todo_file()` reads task headings in document order. Automatic submission selects only the first task whose state is `ready`. A minimal task is sufficient:

```markdown
## TASK-107 | ready | P3 | [SMOKE] Build Slug Utility in `workspace/slug_utility/`
- Outcome: Convert text into deterministic lowercase URL slugs.
```

`get_task_spec()` resolves the workspace in this order:

1. An explicit `Source` entry.
2. A `workspace/...` path embedded in the title.
3. A safe fallback such as `workspace/task_107/` derived from the task ID.

Missing `Source`, `Tests`, and `Requirements` entries are generated in the frozen work order. Explicit entries remain subject to repository-boundary and consistency validation. Duplicate IDs, escaping paths, repository-root workspaces, and inconsistent explicit paths are rejected before execution.

### 2. State transition and isolated worktree

Before execution, Python atomically changes the selected task from `ready` to `working`. With `--worktree`, it then:

1. Fetches and resolves origin's advertised default branch, with `main` and `master` fallbacks.
2. Creates `feature/<task-id>` in a sibling Git worktree.
3. Writes the selected task section to `.mycodeagent/work-orders/<TASK_ID>.md`.
4. Passes the worktree root, task ID, task directory, TODO/work-order path, runtime configuration, and helper paths to the child process through validated environment variables.

If worktree creation or the guarded state update fails, the workflow stops before implementation.

### 3. Implementation and deterministic verification

The Codex supervisor invokes `implement_task`. The implementation agent reads the selected work order, creates application code under `<workspace>/Coding/`, creates tests under `<workspace>/test/`, and returns a structured implementation report.

After a completed implementation report, `execute_task_tests()` runs the selected Python interpreter as:

```text
<python> -m pytest -q <workspace>/test
```

The active worktree is the working directory. Its root and `src` directory are prepended to `PYTHONPATH`, preventing false `ModuleNotFoundError: workspace` failures caused by launching a virtual-environment `pytest` script directly.

Test outcomes are handled as follows:

- `passed`: proceed to review.
- `failed`: forward the complete test observation to `implement_task` as remediation feedback, then test again.
- `error` or `timeout`: stop as an infrastructure failure; do not ask the implementation agent to repair the verifier.

### 4. Review and bounded remediation

After tests pass, the supervisor invokes the separate `review_change` agent. The reviewer reads the task requirements and every relevant source/test file, including untracked files, then returns exactly `APPROVED` or `CHANGES_REQUESTED` with findings.

For `CHANGES_REQUESTED`, the supervisor forwards all findings unchanged to `implement_task`. The remediated code must pass the deterministic tests before re-review. The loop is bounded to five iterations. Approval is valid only when the latest tests pass and the latest review returns `APPROVED`.

### 5. Report parsing, traces, and timeout

The complete supervisor invocation has a default 1800-second hard ceiling; successful small tasks return immediately. `protocol.py` extracts and validates the final structured report. `tracing.py` records diagnostics but does not decide workflow success.

Two append-only files are maintained:

- `logs/<TASK_ID>.logs`: lifecycle events, tests, review decisions, timing, delivery, and errors.
- `logs/<TASK_ID>.raw.logs`: verbose agent output and bounded test-failure details.

Console visibility is controlled by `console_log_levels` in `workflow_runtime.toml`; persistent traces remain enabled independently.

### 6. Approval-gated delivery

Mode 3 reaches delivery only when the parsed final review is `APPROVED`. Python—not an agent—then performs deterministic delivery:

1. Verify the configured GitHub account, repository remote, branch, and allowed task path using `git_approval.toml`.
2. Add the task entry to `CHANGELOG.md` unless it is already prepared.
3. Stage only the task workspace and changelog.
4. Commit on `feature/<task-id>`.
5. Push the feature branch.
6. Create the pull request against `main`.
7. Mark the task `delivered` and synchronize that state back to the primary `TODO.md` when execution occurred in a worktree.

Without approval, mode 2 ends as `reviewed` and creates no pull request. Any implementation, verification, review, runner, or delivery failure ends in `failed` or preserves `reviewed` when verification succeeded but delivery did not complete.

The principal successful lifecycle is:

```text
ready -> working -> reviewed -> delivered
```

Mode 1 can end at `implemented`; failures branch from the active stage to `failed`.

## 1. Task 101 specification

**File:** `TODO.md`

**Problem:** The original task named Groq and ReAct, but its acceptance criteria could be satisfied by a fixed regex-and-mock pipeline. It did not require native Groq tool calling, a Booking Agent, a runtime harness, or adversarial safety tests.

**Fix applied:** Task 101 now retains its native Groq, ReAct, flight-agent, booking-safety, workspace, and test requirements while referencing the reusable standard agentic runtime policy in `coding_agent.yaml`.

```md
- Target Architecture Pattern: ReAct ... model decision -> Pydantic-validated
  tool action -> tool observation -> next decision or final response.
- Groq Tool-Calling Protocol: Use Groq native chat-completions tool calling
  with declared function schemas and `tool_choice="auto"`.
- Runtime Harness:
  - Provide one public engine factory or entry point that accepts validated
    configuration and injectable dependencies.
  - Put Groq and all external services behind injectable interfaces/protocols.
  - Return structured result/status objects rather than relying on printed output.
```

New Task 101 test acceptance includes `test_react_protocol.py` and `test_runtime_harness.py`, in addition to search and booking-flow tests.

## 2. Active workflow configuration

**File:** `coding_agent.yaml`

**Problem:** The active workflow was not clearly documented, stopped on review findings, reviewed only `git diff`, and did not reliably see new untracked task files. It also had no formal feedback loop from reviewer to implementer.

**Fix applied:** The workflow now has bounded implementation/review/remediation modes and explicit task tracing requirements.

```yaml
If the user prompt begins with `REVIEW AND REMEDIATE ONLY`, invoke
`review_change` first. If it returns `CHANGES_REQUESTED`, pass the complete
findings to `implement_task` for one targeted remediation attempt, then invoke
`review_change` again. Stop after the final review result.
```

The implementation agent receives reviewer findings as a remediation request:

```yaml
If the supervisor includes reviewer feedback, treat it as a remediation
request for the same selected task. ... add or strengthen regression tests for
each defect ... Do not broaden scope or change unrelated files.
```

The reviewer now reads the actual workspace, including untracked files:

```yaml
1. Derive the exact task workspace path from TODO.md.
2. Inspect `git status --short --untracked-files=all -- <task_directory>`.
3. Read every relevant source and test file directly from the task workspace.
4. Inspect `git diff` only as supplemental evidence.
```

For state-changing tools, the reviewer must treat LLM-provided fields as untrusted and test forged booking data against canonical inventory.

The supervisor also treats agent tools as synchronous stages. It must wait for a
terminal stage result, rather than polling internal session/inbox/transcript
APIs or declaring failure solely because no intermediate text was emitted. It
cannot cancel an agent or replace the implementation/review path with its own
edits; the only remediation path is reviewer findings, one implementation
attempt, then re-review.

## 3. CLI command naming and stage routing

**Files:** `pyproject.toml`, `src/mycodeagent/__main__.py`

**Problem:** The project documentation and source still referred to `myomnigent`; the installed console script was therefore `myomnigent`, while users were instructed to run `mycodeagent`. The previous stage routing also used unsupported `omnigent --tool` syntax.

**Fix applied:** The package now registers the correct executable:

```toml
[project.scripts]
mycodeagent = "mycodeagent.__main__:main"
```

The CLI identifies itself consistently:

```python
parser = argparse.ArgumentParser(
    prog="mycodeagent", description="MyCodeAgent Workflow CLI"
)
```

Stage modes are expressed in the workflow prompt instead of an unsupported Omnigent command-line argument:

```python
prompt = (
    f"STAGE ONLY: {target_stage}\n"
    "Invoke only the named workflow stage...\n\n"
    f"{prompt}"
)
```

## 4. Safe review and remediation commands

**Files:** `src/mycodeagent/__main__.py`, `coding_agent.yaml`, `README.md`

**Problem:** A direct review needed two clearly separated modes: inspection with no code changes, and an explicit review-to-remediation loop. Reusing one command for both could make an apparently read-only review modify a task.

**Fix applied:** The following commands have distinct behavior:

```bash
# Implement, review, remediate once if needed, re-review; no delivery.
mycodeagent verify TASK-101

# Review once only; it never invokes implementation or delivery.
mycodeagent review TASK-101

# Review first, remediate once only if findings exist, re-review; no delivery.
mycodeagent review TASK-101 --remediate

# Implementation only.
mycodeagent run TASK-101
```

By default, `review` sends a read-only workflow directive:

```python
"REVIEW ONLY\n"
"Review TASK-101 once. Report findings or approval, then stop. "
"Do not invoke implementation, update the changelog, or create a pull request."
```

Only `review --remediate` sends this bounded remediation directive:

```python
"REVIEW AND REMEDIATE ONLY\n"
"Review TASK-101. If findings are returned, send the complete findings "
"to the implementation agent for one targeted fix attempt, then re-review."
```

## 5. Token and runtime controls

**Files:** `workflow_runtime.toml`, `coding_agent.yaml`, `src/mycodeagent/__main__.py`

**Problem:** A short global timeout caused active implementation and review stages to be terminated before their terminal reports arrived, while uniformly high reasoning effort increased token usage.

**Fix applied:**

```toml
effort = "medium"
time_limit_seconds = 1800
```

The 1800-second value is a hard ceiling rather than a mandatory wait; small workflows return as soon as they finish. Implementation uses `medium` effort and the adversarial reviewer uses `high` effort. The bounded feedback loop permits at most five iterations. The CLI supports a per-run override:

```bash
mycodeagent review TASK-101 --timeout-seconds 300
```

Every Omnigent invocation also uses an ephemeral session:

```python
command = ["omnigent", "run", rendered_path, ..., "--no-session", "-p", prompt]
```

## 6. Task trace logging

**Files:** `src/mycodeagent/__main__.py`, `.gitignore`, `README.md`

**Problem:** It was difficult to see the review → feedback → remediation → re-review handoff. Omnigent output was visible only in the terminal.

**Fix applied:** Each task run appends a private trace file:

```python
TRACE_DIR = ROOT / "logs"

def task_trace_path(task_id: str) -> Path:
    trace_path = TRACE_DIR / f"{task_id}.logs"
    trace_path.touch(exist_ok=True)
    restrict_file_permissions(trace_path)  # POSIX owner-only; safe no-op on Windows
    return trace_path
```

Watch a run from another terminal:

```bash
tail -f logs/TASK-101.logs
```

The runner streams Omnigent output to both the terminal and the task log, writes workflow start/finish/timeout markers, and redacts common secret assignments before they are persisted. `logs/` is ignored by Git.

## 7. Input validation and task scope

**File:** `src/mycodeagent/__main__.py`

**Problem:** The harness accepted ambiguous task metadata, silently overwrote duplicate IDs, did not validate a task's workspace path, and could select a custom TODO file while agents read the root TODO file.

**Fix applied:** Task metadata is represented by a validated `TaskSpec`:

```python
@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    state: str
    priority: str
    title: str
    workspace: Path
```

The harness now rejects duplicate task IDs, requires a `Source` workspace, prevents paths outside the repository, validates positive timeouts, and passes the validated values through the environment:

```python
environment["TASK_ID"] = task.task_id
environment["TASK_DIR"] = task.workspace.relative_to(ROOT).as_posix()
environment["TODO_PATH"] = str(todo_path.resolve())
```

## 8. Process cleanup and trace secrecy

**File:** `src/mycodeagent/__main__.py`

**Problem:** Timing out the immediate Omnigent process could leave child processes alive. Traces could also persist a printed API key or token.

**Fix applied:** The runner creates an isolated process group and terminates the full process tree after timeout. POSIX uses process-group signals; Windows uses `taskkill /T /F` with a direct-process fallback:

```python
process = subprocess.Popen(
    ...,
    start_new_session=os.name == "posix",
    creationflags=CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
)
terminate_process_group(process)
```

Trace text is redacted before file output:

```python
SECRET_PATTERN = re.compile(...)

def redact_secrets(message: str) -> str:
    return SECRET_PATTERN.sub(r"\1[REDACTED]", message)
```

## 9. Delivery guardrails

**Files:** `src/mycodeagent/__main__.py`, `scripts/workflow_helpers.py`, `coding_agent.yaml`, `git_approval.toml`

**Problem:** The prior delivery helper could create/reset branches, stage changes, push, and open a PR without checking the approved repository, Git identity, GitHub account, task path, or approval state. It also relied on unset `$TASK_ID` and `$TASK_DIR` shell variables.

**Fix applied:** Delivery is now deliberately human-authorized:

```bash
mycodeagent deliver TASK-101 --approved
```

The helper requires an approval status and runs deterministic preflight checks:

```python
if review_status != "APPROVED":
    raise RuntimeError("Pull-request delivery requires review status APPROVED")

if run_cmd(["git", "remote", "get-url", "origin"]) != approval["approved_remote"]:
    raise RuntimeError("Origin remote does not match approved_remote")

if run_cmd(["gh", "api", "user", "--jq", ".login"]) != approval["approved_github_login"]:
    raise RuntimeError("Authenticated GitHub account does not match approved_github_login")
```

It validates the task directory is repository-contained and has `Coding/` and `test/` directories, sets the approved local Git identity, and replaces destructive `git checkout -B` with safe branch switching or creation. `git_approval.toml` was aligned to the current `MyCodeAgent` origin.

## 10. Flight booking implementation review history

**Files:** `workspace/flight_booking_agent/Coding/agents.py`, `workspace/flight_booking_agent/Coding/tools.py`, `workspace/flight_booking_agent/Coding/schemas.py`, `workspace/flight_booking_agent/test/`

**Problem:** The first implementation was a fixed deterministic pipeline with no actual Groq invocation or ReAct tool loop. The later ReAct implementation required review for a critical booking issue: a model could provide a real flight ID with forged price/airline/route fields.

**Required remediation pattern:** Booking must use authoritative catalog data after resolving the flight ID, rather than trusting a model-provided `FlightOption` payload. Additionally, a complete model tool-call batch must be validated before any handler executes, so an invalid mixed batch cannot partially create side effects.

**Applied resolution:** `MockReservationGateway.reserve()` now treats the
model-supplied flight option as an identifier lookup only. After route/date
validation, it discards the supplied airline and price fields and uses the
authoritative catalog record for inventory, confirmation airline, and total
price. The forged-payload regression test now passes with the isolated suite.

Representative ReAct controls now expected by Task 101 include:

```python
validation = self.registry.validate_tool_call(tool_call)
if isinstance(validation, str):
    return ReActRunResult(status="error", error=validation, ...)
```

and native tool schemas generated from Pydantic action models:

```python
"parameters": spec.args_model.model_json_schema()
```

Run the isolated offline tests with:

```bash
python -m pytest -q workspace/flight_booking_agent/test
```

## 11. One-task submission and optional sequential batch

**Files:** `src/mycodeagent/__main__.py`, `README.md`

**Problem:** `mycodeagent submit` previously selected only the first task with
state `ready`, ran one workflow, and exited. Starting it overnight did not
advance to later ready tasks. Simply looping without a state update would also
select the same task repeatedly.

**Fix applied:** `submit` now returns to the safer one-task default: it selects
the first `ready` task in `TODO.md`, runs its bounded implementation/review
workflow, updates its state, and exits. The prior FIFO processing capability is
available only through explicit `--all`; it reloads the TODO file after each
task and remains sequential.

`submit --mode` makes the intended depth explicit:

```bash
mycodeagent submit --mode 1  # implementation only
mycodeagent submit --mode 2  # implementation, review, one remediation, re-review
mycodeagent submit --mode 3  # full workflow, including PR after APPROVED review
```

Mode 2 is the default. Mode 1 records a clean run as `implemented`; modes 2
and 3 record a clean run as `reviewed`. Mode 3 is intentionally refused with
`--all`, preventing a batch command from creating multiple pull requests.

The CLI atomically changes state before and after each run:

```text
ready -> working -> reviewed   # workflow process exited with code 0
ready -> working -> failed     # timeout, launch, or workflow failure
```

`reviewed` is intentionally not `completed` or `approved`: a zero exit code
only proves the bounded implementation/review workflow finished. The final
review result must still be checked in `logs/<TASK_ID>.logs` before a person
marks a task completed, returns it to `ready`, or authorizes delivery.

```python
task_id = get_first_ready_task(tasks)
...
update_task_state(todo_path, task_id, "working", expected_state="ready")
return_code = execute_omnigent_stage(...)
final_state = "reviewed" if return_code == 0 else "failed"
update_task_state(todo_path, task_id, final_state, expected_state="working")
```

The optional batch is deliberately sequential. Tasks can share the same Git
checkout, workflow configuration, and task workspaces; concurrent agents could
overwrite each other's files or create ambiguous review evidence.

Use the normal one-task flow or opt into the batch explicitly:

```bash
# Process the first ready task only (default).
mycodeagent submit

# Process all ready tasks sequentially, continuing after failures.
mycodeagent submit --all

# Stop the optional batch at the first failure.
mycodeagent submit --all --stop-on-error

# Watch the current task's agent trace in another terminal.
tail -f logs/TASK-101.logs
```

## 12. Readable agent reports

**File:** `coding_agent.yaml`

**Problem:** Agent responses were often long, free-form multi-line narratives.
They were difficult to scan in the terminal and made the saved task trace less
useful during an overnight queue run.

**Fix applied:** The supervisor and each relevant stage now require compact
Markdown headings with one-line bullets. The supervisor's final report has a
fixed outcome, implementation/test/review/remediation/delivery summary, and
next-action layout:

```md
# Task workflow: <TASK_ID>
## Outcome
- Status: <verification complete | changes requested | failed | delivered>
- Final review: <APPROVED | CHANGES_REQUESTED | not reached>
## Execution summary
- Implementation: <completed | not run | failed>
- Tests: `<command>` — <pass/fail/not run>
- Review: <APPROVED | CHANGES_REQUESTED | not run>
- Remediation: <not needed | completed | failed | not run>
- Pull request: <not created — submit is verification-only | URL | not run>
## Changed files
- <file>: <brief purpose>
## Next action
- <one clear action, or "None">
```

Implementation responses list status, changed files, validation, and
acceptance evidence. Review responses retain `APPROVED` or
`CHANGES_REQUESTED` as their first line for reliable workflow routing, then
present concise review-summary and finding bullets. Findings use a stable
`[F1] file:line — defect. Required fix: ...` form.

The CLI now keeps Omnigent's raw progress stream out of the terminal and writes
it to `logs/<TASK_ID>.raw.logs`; lifecycle events remain in
`logs/<TASK_ID>.logs`. When the process exits, the terminal prints
the final `# Task workflow` report (or final review report) instead. If an agent
does not follow the required report format, the terminal shows a short notice
and links to the full trace rather than dumping unstructured text.

## 13. Workflow duration reporting

**Files:** `src/mycodeagent/__main__.py`, `README.md`

**Problem:** The trace had timestamped lines, but a terminal user could not
quickly see the total time consumed by a review or remediation run.

**Fix applied:** Every Omnigent invocation now prints a local-time start line
and, on completion or timeout, a local end time with elapsed seconds. The same
start, end, elapsed duration, exit code, and timeout limit are appended to the
per-task trace.

```text
Workflow started at 2026-08-02T22:00:00+05:30
Workflow finished at 2026-08-02T22:04:12+05:30 after 252.4s (exit code 0).
```

For an active or completed run, inspect its durable record with:

```bash
tail -f logs/TASK-101.logs
```

The stdout selector cleanup is idempotent. A child process can reach EOF and
exit during the same polling iteration; the runner now safely ignores a second
unregister attempt instead of raising `KeyError` after an otherwise successful
workflow.

## 14. CLI modularization

**Files:** `src/mycodeagent/__main__.py`, `paths.py`, `tasks.py`,
`tracing.py`, `runner.py`, `submission.py`

**Problem:** The CLI implementation had grown into one large module containing
argument parsing, TODO parsing and atomic state changes, secret-redacted logs,
subprocess lifecycle management, workflow rendering, and submit-mode routing.
This made changes harder to review and test safely.

**Fix applied:** `__main__.py` is now a small command router. Responsibilities
are split into focused modules:

```text
paths.py       -> repository paths and runtime constants
tasks.py       -> TODO parsing, source-boundary validation, atomic task states
tracing.py     -> private redacted logs and concise terminal-report extraction
runner.py      -> Omnigent command, timeout, child-process cleanup, timing
submission.py  -> one-task/default and explicit batch submit orchestration
__main__.py    -> CLI flags and routing to the above modules
```

The public console entry point remains `mycodeagent`, and all submit modes and
direct `run`, `verify`, `review`, and `deliver` commands retain their behavior.

## 15. Deterministic mode-3 delivery

**Files:** `src/mycodeagent/submission.py`, `delivery.py`, `runner.py`,
`scripts/workflow_helpers.py`

**Problem:** An LLM-controlled PR stage could report that delivery succeeded
without actually running the PR helper. An Omnigent process exit code alone is
not proof of an approved review, changelog update, branch, commit, push, or PR.

**Fix applied:** Mode 3 now runs Omnigent only for implementation and review.
The runner returns the final structured report to the submission orchestrator.
Only a report containing `Final review: APPROVED` permits deterministic Python
delivery. That delivery checks that `CHANGELOG.md` is clean, runs the changelog
helper, then runs the PR helper. A missing final report is a workflow failure.

```text
Codex implementation/review -> verified APPROVED report
                              -> deterministic changelog helper
                              -> deterministic PR helper
```

The PR helper also refuses to switch into an existing feature branch, avoiding
workspace replacement during delivery. Mode 3 finishes as `delivered` only
after both deterministic helper commands succeed.

## Recommended operating sequence

```bash
# Install/update the editable CLI after package metadata changes.
python -m pip install --no-build-isolation -e .

# Implement and review a task without delivery.
mycodeagent verify TASK-101

# Inspect findings without changing code.
mycodeagent review TASK-101

# Or explicitly remediate one review cycle without delivery.
mycodeagent review TASK-101 --remediate

# Follow the workflow handoffs.
tail -f logs/TASK-101.logs

# Independently run offline tests.
python -m pytest -q workspace/flight_booking_agent/test

# Delivery is a separate, explicitly authorized action.
mycodeagent deliver TASK-101 --approved

PYTHONPATH=src venv/bin/python -m mycodeagent github-submit \
  --owner tapasdas-git \
  --project 4 \
  --mode 1

  PYTHONPATH=src venv/bin/python -m mycodeagent github-submit --owner tapasdas-git --project 4 --worktree --mode 3

  gh auth status
gh auth refresh -h github.com -s read:project
git --version
omnigent --version
```

Create and Activate Virtual Environment

python3 -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows Command Prompt
venv\Scripts\activate.bat

# Install MyCodeAgent in Editable Mode

pip install -e .


## GIT Feature branch merge

## To check current branch you are

git branch --show-current
## To work on a feature branch
git checkout -b feature/your-branch-name

## To merge Feature branch to Main

git add .

git commit -m "Complete feature implementation"

git push -u origin feature/your-branch-name

# 1. Switch back to your local main branch
git switch main

# 2. Pull the absolute latest updates from remote main (keeps you up to date)
git pull origin main

# 3. Merge your local feature branch into your local main branch
git merge feature/your-branch-name

# 4. Push the newly merged main branch back up to the remote server
git push origin main



