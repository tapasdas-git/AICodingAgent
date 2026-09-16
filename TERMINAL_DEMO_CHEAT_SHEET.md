# MyCodeAgent Terminal Demo Cheat Sheet

Use this guide to demonstrate how MyCodeAgent picks up a task from a Git
repository, implements it, runs tests, reviews the result, and optionally opens
a pull request.

> Recommended live-demo path: use **Mode 2** first. It demonstrates
> implementation, tests, and review without pushing a branch or creating a PR.
> Use **Mode 3** only when you intentionally want GitHub side effects.

## 1. Before the demo

Open a terminal and move to the repository:

```bash
cd /path/to/AICodingAgent
```

Confirm the repository and tools are ready:

```bash
git status --short
git remote -v
python3 --version
git --version
gh --version
omnigent --version
```

For a Mode 3 demo, also verify GitHub authentication:

```bash
gh auth status
```

Install the CLI in an isolated Python environment if it is not already set up:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -e .
mycodeagent --help
```

If the environment already exists, only activate it:

```bash
source venv/bin/activate
```

## 2. Show the audience the workflow inputs

Briefly show the task queue, review rules, workflow, and runtime configuration:

```bash
sed -n '1,220p' TODO.md
sed -n '1,180p' codeReviewGuideline.md
sed -n '1,180p' coding_agent.yaml
sed -n '1,160p' workflow_runtime.toml
```

Talking point: a task moves through these states:

```text
ready -> working -> implemented/reviewed -> delivered
                   \-> failed (if the workflow cannot complete)
```

## 3. Prepare one small demo task

Create or edit a task in `TODO.md`. The task must have a unique ID and the
state `ready`. Keep the scope small enough to finish during the presentation.

Example:

```markdown
## TASK-900 | ready | P2 | Add a slug utility
- Outcome: Add a dependency-free function that converts a title to a URL slug.
- Depends on: None
- Repository: https://github.com/tapasdas-git/AICodingAgent.git
- Harness: codex
- Night-ready: no
- Workspace Boundary:
  - Source: `workspace/slug_demo/Coding/`
  - Tests: `workspace/slug_demo/test/`
  - Do not modify files outside `workspace/slug_demo/`.
- Acceptance:
  - Add `workspace/slug_demo/Coding/slug.py` with `slugify(value: str) -> str`.
  - Trim surrounding whitespace, lowercase text, and join words with `-`.
  - `slugify("  Hello   World  ")` returns `"hello-world"`.
  - Empty input raises `ValueError`; non-string input raises `TypeError`.
  - Add tests covering every acceptance criterion.
  - All tests pass.
- Approved by: Demo operator
- Approval reference: Live demo authorization
```

Verify that the task appears as `ready`:

```bash
rg -n '^## .*\| ready \|' TODO.md
```

> The CLI normally selects the first ready task. Supplying `--task-id` with a
> worktree makes the live demo deterministic when multiple tasks are ready.

## 4. Run the recommended demo (Mode 2)

Run the selected task in an isolated Git worktree:

```bash
mycodeagent submit \
  --task-id TASK-900 \
  --worktree \
  --mode 2 \
  --timeout-seconds 1800
```

What to narrate while it runs:

1. The CLI reads the structured `ready` task.
2. A separate worktree protects the presenter’s main checkout.
3. The implementation agent writes code and tests within the stated boundary.
4. Deterministic tests run against the generated workspace.
5. The reviewer checks the diff, tests, security, and review guidelines.
6. The supervisor can send findings back for a bounded remediation loop.

## 5. Inspect the result

Check the task state and generated audit files:

```bash
rg -n 'TASK-900' TODO.md
ls -lah logs/
tail -n 80 logs/TASK-900.logs
cat logs/TASK-900_usage.json
```

Find the task worktree and inspect its changes:

```bash
git worktree list
```

Copy the displayed task-worktree path, then run:

```bash
cd /path/from/git-worktree-list
git status --short
git diff --stat
git diff
```

Run the task’s tests directly (adjust the path if your demo task differs):

```bash
python -m pytest -q workspace/slug_demo/test
```

Show the final review verdict from the logs:

```bash
rg -n 'APPROVED|CHANGES_REQUESTED|FAILED' logs/TASK-900*
```

## 6. Optional full delivery demo (Mode 3)

Mode 3 runs implementation and review, then updates the changelog, commits,
pushes the task branch, and opens a GitHub pull request after an `APPROVED`
review. Confirm that `git_approval.toml` identifies the intended Git user,
remote, and GitHub repository before running it.

```bash
cat git_approval.toml
gh auth status
mycodeagent submit \
  --task-id TASK-900 \
  --worktree \
  --mode 3 \
  --timeout-seconds 1800
```

After completion:

```bash
gh pr list --head feature/task-900
git log --oneline --decorate -5
rg -n 'TASK-900' CHANGELOG.md TODO.md
```

If the actual branch name differs, get it from `git branch --show-current` in
the task worktree and pass that value to `gh pr list --head`.

## 7. Useful fallback commands

Run only one stage while troubleshooting:

```bash
# Implementation only
mycodeagent run TASK-900 --timeout-seconds 1800

# Implementation plus the review/remediation loop
mycodeagent verify TASK-900 --timeout-seconds 1800

# Read-only review of existing changes
mycodeagent review TASK-900 --timeout-seconds 1800

# Review with one targeted remediation attempt
mycodeagent review TASK-900 --remediate --timeout-seconds 1800

# Deliver only after an APPROVED review; this commits, pushes, and creates a PR
mycodeagent deliver TASK-900 --approved --timeout-seconds 600
```

## 8. Fast troubleshooting

```bash
# CLI is not found
source venv/bin/activate
python -m pip install -e .

# No ready task is found
rg -n '^## .*\| ready \|' TODO.md

# Inspect recent task output
tail -n 120 logs/TASK-900.logs

# Inspect detailed test output
tail -n 120 logs/TASK-900_test.log

# Check repository and GitHub identity before delivery
git remote -v
git config user.name
git config user.email
gh auth status
```

Common safety reminders:

- Commit or stash unrelated local changes before the demo.
- Use one small, self-contained task with explicit acceptance criteria.
- Prefer `--worktree` for isolation.
- Never show secrets or API keys in task text, source files, or terminal output.
- Do not use Mode 3 unless creating a remote branch and PR is intended.
- Do not combine `--all` with Mode 3 or with `--worktree`.

## 9. 30-second closing summary

“The repository holds the task, acceptance criteria, runtime policy, and review
rules. MyCodeAgent selects a ready task, implements it in isolation, runs tests,
performs an adversarial review, records an audit trail, and—when explicitly run
in Mode 3—delivers the approved change as a GitHub pull request.”
