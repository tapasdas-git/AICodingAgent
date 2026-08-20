MyCodeAgent 

MyCodeAgent is an autonomous, agentic task-execution engine and CLI tool designed to automate software feature development, adversarial code reviews, changelog updates, and GitHub Pull Request delivery.

By combining high-reasoning AI models (for code creation and automated security/guideline reviews) with deterministic Python scripting (for Git lifecycle management and changelog generation), MyCodeAgent delivers a controlled task-resolution workflow with minimal token usage and high reliability.

***
💡 Key Features & Architecture

```text
                               ┌────────────────────────────────────────┐
                               │ 1. TASK PICKUP                         │
                               │    Parses 'ready' tasks from TODO.md   │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  v
                               ┌────────────────────────────────────────┐
                               │ 2. IMPLEMENT TASK (AI Agent)           │
                               │    Isolated workspace creation         │
                               │    Generates code, dependencies & tests│
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  v
                               ┌────────────────────────────────────────┐
                               │ 3. ADVERSARIAL CODE REVIEW (AI Agent)   │
                               │    Inspects diffs vs. guidelines       │
                               │    Verifies 100% test suite pass rate  │
                               │    Scans for security & key leaks      │
                               └─────────┬────────────────────┬─────────┘
                                         │                    │
                                [CHANGES_REQUESTED]        [APPROVED]
                                         │                    │
                                         v                    v
                                  ┌───────────────────┐   ┌───────────────────┐
                                  │ FIX & RE-REVIEW   │   │ 4. UPDATE CHANGELOG│
                                  │ (ONE ATTEMPT)     │   │    Deterministic  │
                                  └───────────────────┘   │    Python Script  │
                                                    └─────────┬─────────┘
                                                              │
                                                              v
                                                    ┌───────────────────┐
                                                    │ 5. CREATE PULL REQ│
                                                    │    Pushes branch  │
                                                    │    Opens GitHub PR│
                                                    └───────────────────┘

Automated Task Ingestion: Scans TODO.md for structured tasks marked as ready.

Isolated Task Workspaces: Generates feature implementations and unit tests within scoped task directories to avoid cross-task pollution.

Adversarial Code Review: Evaluates task changes against customized guidelines (codeReviewGuideline.md), test suite execution results, and security scans before approving. `CHANGES_REQUESTED` findings are sent back to the implementation agent for one targeted remediation attempt; only an explicit `APPROVED` result proceeds to delivery.

Deterministic Delivery Pipeline: Executes branch creation, changelog tracking, and GitHub PR creation using deterministic Python helpers (saving tokens and eliminating non-deterministic Git errors).

🛠️ Technology Stack & Dependencies
Language & Runtime: Python 3.8+ (Recommended Python 3.11+)

Agent Framework & Runner: Omnigent Core Engine (omnigent)

Version Control & Integration: Git, GitHub CLI (gh)

Testing Frameworks: pytest, Python unittest

Configuration Formats: YAML (.yaml), TOML (.toml), Markdown (.md)

***
📋 Prerequisites

🔧 Installing the Omnigent Core Engine

pip install omnigent

omnigent setup


Before setting up MyCodeAgent in a fresh environment, ensure the following dependencies and tools are installed and configured:

Python 3.8+
Check installation:
python3 --version

Git
Installed and configured with your target repository:
git --version

GitHub CLI (gh)
Required for automated Pull Request creation during the delivery stage.
Authenticate your active session:
gh auth login
gh auth status

Omnigent Binary / Core Runner
Ensure omnigent is installed and accessible in your environment's $PATH:
omnigent --version

***
📁 Project Directory Structure

For MyCodeAgent to locate configuration files and source code correctly, ensure your repository root matches this layout. The CLI loads `coding_agent.yaml` as its active Codex/Omnigent workflow definition; `omnigent_bugfix_workflow.yaml` is not used by the current CLI.

```text
MyCodeAgent/                        # Project Root Directory
├── TODO.md                        # Task queue file containing structured tasks
├── CHANGELOG.md                   # Automated release changelog
├── codeReviewGuideline.md         # Enterprise review & security standards
├── pyproject.toml                 # Package configuration & entry points
├── workflow_runtime.toml          # Model, harness, and timeout runtime settings
├── coding_agent.yaml              # Active Codex/Omnigent workflow stages
├── git_approval.toml             # Approved Git identity & remote repository rules
├── README.md                      # Documentation
├── scripts/
│   └── workflow_helpers.py        # Deterministic Python scripts (Changelog & PR)
└── src/
    └── mycodeagent/
        ├── __init__.py        # Package initialization
        ├── __main__.py        # CLI argument routing and console entry point
        ├── paths.py           # Repository paths and runtime constants
        ├── tasks.py           # Flexible TODO parsing, derived workspaces, task states
        ├── protocol.py        # Structured terminal-report parsing and validation
        ├── tracing.py         # Configurable console logging and secret-redacted traces
        ├── runner.py          # Omnigent process, timeout, and cleanup logic
        ├── orchestration.py   # Implementation/test/review workflow routing
        ├── workflow_tools.py  # Stage events and isolated deterministic test execution
        ├── delivery.py        # Deterministic changelog and PR helper execution
        ├── submission.py      # One-task and explicit batch submission modes
        └── worktrees.py       # Isolated task worktree creation and launch


🚀 Quickstart & Installation
Clone the Repository

git clone https://github.com/tapasdas-git/MyCodeAgent.git

cd MyCodeAgent

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

📖 Usage Guide

### Execute the automated workflow

`submit` processes the first `ready` task in `TODO.md` and exits. Select the level of automation with `--mode`:

| Mode | Command | What it runs | Final task state on clean workflow exit |
| --- | --- | --- | --- |
| 1 | `mycodeagent submit --mode 1` | Implementation only | `implemented` |
| 2 (default) | `mycodeagent submit --mode 2` | One persistent supervisor runs implementation, deterministic tests, review, and a feedback loop capped at five iterations | `reviewed` |
| 3 | `mycodeagent submit --mode 3` | Mode 2, then deterministic changelog and PR delivery only after verified `APPROVED` | `delivered` |

Run the default mode (mode 2):

```bash
mycodeagent submit
```

### Token budgets and usage audit

Task workflows use native Codex goal accounting with separate task, supervisor,
implementer, and reviewer ceilings configured in `workflow_runtime.toml`:

```toml
token_budget = 400000
supervisor_token_budget = 75000
implementer_token_budget = 100000
reviewer_token_budget = 60000
```

Override the combined task ceiling for one invocation with
`--token-budget`. Usage is aggregated in `logs/<TASK_ID>_usage.json` and
appended live to `logs/<TASK_ID>.logs`. Full redacted implementer, reviewer,
and supervisor reports are framed and deduplicated in
`logs/<TASK_ID>.raw.logs` so review failures remain auditable.

```bash
mycodeagent submit --mode 2 --token-budget 400000
```

```bash
# Mode 1 — implementation only
mycodeagent submit --mode 1

# Mode 2 — implementation and bounded review, without PR delivery
mycodeagent submit --mode 2

# Mode 3 — full workflow; deterministic PR delivery only after verified APPROVED review
mycodeagent submit --mode 3
```

For a task that may create a PR, use a worktree so its branch and files stay
isolated from the primary checkout:

```bash
# Automatically select the first ready task
mycodeagent submit --worktree --mode 3 --timeout-seconds 1800

# Select one particular ready task
mycodeagent submit --task-id TASK-104 --worktree --mode 3 --timeout-seconds 1800
```

Use a custom TODO file:

```bash
mycodeagent submit --todo /path/to/custom_todo.md
```

Before a task starts it is marked `working`. A timeout, runner failure, or invalid task configuration becomes `failed`. `reviewed` means implementation/review completed but delivery was not completed; inspect its trace for the review verdict and delivery result. `delivered` means an approved task's changelog, commit, push, and PR creation completed.

### Batch mode

Process all ready tasks sequentially, continuing after failures:

```bash
mycodeagent submit --all
```

Stop the batch after the first failure:

```bash
mycodeagent submit --all --stop-on-error
```

For safety, batch mode cannot be combined with mode 3 because it could create multiple PRs. `--all --worktree` is not supported yet; mode-3 worktree runs currently process one ready task per command.

### GitHub Project task ingestion

Keep `submit` for `TODO.md`. Use `github-submit` to select the first GitHub
Project item whose project status is `Todo` and whose linked issue is `OPEN`:

```bash
mycodeagent github-submit --owner tapasdas-git --project 4 --mode 2
```

Run the selected issue in an isolated worktree and deliver it after approval:

```bash
mycodeagent github-submit --owner tapasdas-git --project 4 --worktree --mode 3
```

The issue body does not need a TODO heading or embedded state. MyCodeAgent
creates a private, TODO-compatible work order under `logs/work-orders/` and
uses the issue title/body as the task specification. GitHub remains read-only;
workflow state is recorded in the local work order. Project queries require
`gh auth refresh -s read:project`.

An OPEN/Todo issue can be retried when its local work order is `failed`,
`implemented`, or `reviewed`. Issues currently `working` or already `delivered`
are not selected again. A retry reuses the issue's registered feature worktree
and branch so partial implementation remains available.

### Parallel task worktrees

Use one Git worktree per task when a task needs its own pull request. Python
creates each worktree from `origin`'s advertised default branch, with `main`
and `master` fallbacks. It never bases TASK-104 on another task's feature
branch such as TASK-103.

Let Python create and run a clean worktree for TASK-104:

```bash
mycodeagent submit --task-id TASK-104 --worktree --mode 3 --timeout-seconds 1800
```

This creates a sibling worktree at `.mycodeagent-worktrees/task-104` beside the
primary checkout, on `feature/task-104` from the resolved origin default branch. The selected task
section is frozen as private worktree metadata and logs remain in the primary
checkout. Its implementation, review, changelog update, commit, push, and PR
are isolated from other tasks. Remove a worktree only after its PR is safely
delivered or no longer needed:

```bash
git worktree remove ../.mycodeagent-worktrees/task-104
```

### Direct modes

Use a direct command when you already know the task ID:

| Command | Action |
| --- | --- |
| `mycodeagent run TASK-101` | Implementation only |
| `mycodeagent verify TASK-101` | One supervisor runs implementation, tests, review, and bounded feedback; no PR |
| `mycodeagent review TASK-101` | Read-only review; no implementation changes |
| `mycodeagent review TASK-101 --remediate` | One supervisor reviews and runs bounded remediation/test/re-review feedback; no PR |
| `mycodeagent deliver TASK-101 --approved` | Explicitly authorized deterministic delivery after an approved review |

Each workflow invocation is one-shot. The default runtime limit is 1800 seconds. This is a hard ceiling, not a mandatory wait: small tasks return immediately when their terminal result arrives. Override the ceiling per command when needed:

```bash
mycodeagent run TASK-101 --timeout-seconds 900
mycodeagent review TASK-101 --remediate --timeout-seconds 1800
mycodeagent submit --worktree --mode 3 --timeout-seconds 1800
```

## To test a perticular task post completion

cd /Users/tapasdas/work/AICodingAgent/workspace-worktrees/task-015

PYTHONPATH="$PWD:$PWD/src" \
/Users/tapasdas/work/AICodingAgent/venv/bin/python \
-m pytest -vv workspace/calculator/test

### Runtime logging

Console diagnostic levels are configured independently in `workflow_runtime.toml`:

```toml
console_log_levels = ["debug", "info", "error"]
```

Remove a value to suppress that level. For example, use `["info", "error"]` in normal operation or `["error"]` for error-only console output. Persistent task traces remain enabled regardless of the console selection. Tracing only records and renders diagnostics; structured workflow-result parsing and validation live separately in `protocol.py`.

### Isolated test execution

The verifier always runs the selected interpreter as `python -m pytest`, uses the active task worktree as its working directory, and prepends the worktree root plus its `src` directory to `PYTHONPATH`. This allows imports such as `workspace.example.Coding.module` to resolve consistently without test-side path shims. Test imports that reference another task workspace remain implementation defects and should be corrected during remediation.

### Monitoring task runs

Each invocation writes an append-only lifecycle trace to `logs/<TASK_ID>.logs`
and verbose agent output to `logs/<TASK_ID>.raw.logs`. The lifecycle trace contains
workflow start/finish markers, timestamps, elapsed duration, stage transitions,
test outcomes, and timeout or launch errors. To keep the terminal readable, it
shows only the final structured report. Monitor an active run in another terminal:

Deterministic pytest runs append their command, status, exit code, individual
test results, and summary to `logs/<TASK_ID>_test.log`. Disable task test logs
while retaining per-task lifecycle status in `workflow_runtime.toml`:

```toml
test_result_logging_enabled = false
```

tail -f logs/TASK-101.logs

# Verbose agent output
tail -f logs/TASK-101.raw.logs

Direct Script Execution (Human-in-the-Loop Fallback)

To execute changelog updates or GitHub PR generation directly via the deterministic helper scripts:

Append task entry to a repository or linked worktree CHANGELOG.md
python3 scripts/workflow_helpers.py --repo-root /path/to/worktree changelog --task-id "TASK-100"

Create feature branch, commit, push, and open Pull Request on GitHub
python3 scripts/workflow_helpers.py --repo-root /path/to/worktree --approval-file /path/to/git_approval.toml pr --task-id "TASK-100" --task-dir "workspace/example" --review-status APPROVED

📝 Defining Tasks in TODO.md

### Minimal task format

A user only needs to provide a valid heading. An `Outcome` line is strongly recommended so the implementation intent is unambiguous:

```markdown
## TASK-107 | ready | P3 | [SMOKE] Build Slug Utility in `workspace/slug_utility/`
- Outcome: Implement a deterministic standard-library utility that converts text into lowercase URL slugs.
```

Automatic submission picks the first task whose state is `ready`. The normal state progression is:

```text
ready -> working -> implemented/reviewed/delivered
                 -> failed
```

The heading must contain a task ID such as `TASK-107`, a state, priority `P0` through `P3`, and a title. A task in `working`, `implemented`, `reviewed`, `delivered`, or `failed` remains parseable, but automatic `submit` selects only `ready` tasks.

Workspace metadata is optional. Resolution follows this order:

1. Use an explicit `Source` entry when supplied.
2. Otherwise use a `workspace/...` path embedded in the title.
3. Otherwise derive `workspace/<task_id>/`, converting the hyphen to an underscore.

For the example above, MyCodeAgent dynamically supplies the work order with:

```markdown
- Source: `workspace/slug_utility/Coding/`
- Tests: `workspace/slug_utility/test/`
- Requirements: `workspace/slug_utility/Coding/requirements.txt`
```

Users may still declare these paths explicitly. Explicit paths must be mutually consistent and remain inside the repository. The task workspace does not need to exist before implementation.

### Coding-agent implementation contract

`mycodeagent` invokes Codex through `coding_agent.yaml`. The task description is the source of truth; the coding agent must translate its architecture and acceptance criteria into implementation, tests, and a reviewable result. For every task, the implementation stage must:

- inspect the referenced repository files before choosing dependencies or APIs;
- keep changes inside the task's stated workspace boundary;
- map every acceptance criterion to at least one test;
- inject external integrations behind interfaces and use fakes/mocks in tests; and
- report the task ID, changed files, acceptance-test evidence, and any unsupported requirement rather than silently substituting an unrelated design.

For an AI-agent task, naming an LLM provider is an implementation requirement. For example, a Groq ReAct feature must include a dynamically configured Groq adapter, validated tool inputs and outputs, and an explicit thought/action/observation loop with a bounded iteration count. A key lookup alone is not an LLM integration. Business-critical checks—such as price, inventory, policy, and booking confirmation—must remain deterministic code and must not rely on model output.

The Omnigent workflow is the outer development pipeline (implement, review, changelog, delivery). It is distinct from any multi-agent runtime that the task asks the coding agent to build.

```markdown
## TASK-100 | ready | P1 | Build Flight Booking Agent in `workspace/flight_booking/`
- Outcome: Implement a flight search and booking module that processes natural-language requests.
- Acceptance:
  - Mock external airline APIs so tests run offline.
  - Validate booking authorization and inventory before reservation.
  - All task tests pass.
```


# This performs a read-only review only—no implementation changes, remediation, changelog update, or PR creation.
mycodeagent review TASK-101 --timeout-seconds 300

tail -f logs/TASK-101.logs

# This runs only the implementation stage for the specified task—no review, remediation, changelog, or PR.

mycodeagent run TASK-101 --timeout-seconds 1800

# This runs implementation and review, without remediation, changelog updates, or PR creation.

mycodeagent verify TASK-101 --timeout-seconds 1800

# This runs review, performs one targeted implementation fix only if findings exist, then re-reviews. No PR is created.

mycodeagent review TASK-101 --remediate --timeout-seconds 1800

# For a task that has already received an APPROVED review, This performs the deterministic delivery steps:
mycodeagent deliver TASK-106 --approved

# Run the end to end flow till PR generation

mycodeagent submit --worktree --mode 3 --timeout-seconds 1800

### Platform compatibility

MyCodeAgent supports Python 3.11+ on Windows, macOS, and Linux. `git`, `gh`, and
`omnigent` must be available on `PATH`; executable locations are resolved at
runtime. Conventional `venv` and `.venv` interpreters are detected under both
`Scripts/python.exe` and `bin/python`.

Set `worktree_root` in `workflow_runtime.toml` to choose where task worktrees
are created. Relative paths are resolved from the primary repository root; the
default `.mycodeagent-worktrees` path is ignored by Git. Set
`MYCODEAGENT_WORKTREE_ROOT` to override this location for one process, which can
also help Windows installations with restrictive path-length policies. Git
pathspecs are emitted with forward slashes on every platform. The runtime uses
platform-specific process-tree cleanup and portable pipe streaming.

For long Windows repositories, enable Git long paths if organizational policy
allows it:

```powershell
git config --global core.longpaths true

This runs implementation and review, without remediation, changelog updates, or PR creation.

mycodeagent verify TASK-101 --timeout-seconds 1800

This runs review, performs one targeted implementation fix only if findings exist, then re-reviews. No PR is created.

mycodeagent review TASK-101 --remediate --timeout-seconds 1800

For a task that has already received an APPROVED review, This performs the deterministic delivery steps:
mycodeagent deliver TASK-106 --approved

Run the end to end flow till PR generation

mycodeagent submit --worktree --mode 3 --timeout-seconds 1800

git for mid failure run
git worktree list 
git worktree remove --force /Users/tapasdas/work/workingFolder/.mycodeagent-worktrees/task-109
git branch --no-merged
git branch --no-merged | grep 'feature/' | xargs git branch -D
git branch -D feature/task-109
```
