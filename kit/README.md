# The loop kit

The fixed half of every harness. Installed into a project by:

```powershell
<project venv python> kit\install_kit.py <project folder>
```

Run the installer with the project's own interpreter; that path gets pinned
into the hooks. Safe to re-run after updating this repo: it overwrites kit
files only, keeps your `loop/loop.json`, and merges into an existing
`.claude/settings.json` (keeping a `.bak`).

## What gets installed

| In the project | Purpose |
|---|---|
| `verify/gatekit.py` | Gate framework. A project gate declares checks and broken fixtures; gatekit supplies the command line (`--only`, `--json`, `--list`, `--matrix`, `--selftest`), exit codes (0 pass, 1 fail, 3 HARNESS ERROR) and the self-test. |
| `.claude/hooks/guard.py` | `PreToolUse`. Blocks writes to locked paths for the current stage, blocks git, blocks agents running the driver. Fails closed. |
| `.claude/hooks/gate_hook.py` | `PostToolUse` on file edits. Runs the current task's gate checks; exit 2 feeds a failure back to the model, exit 0 on a harness error. |
| `.claude/hooks/stop_gate.py` | `Stop`. In a build run, refuses to let the agent finish while its gate checks or tests fail (three nudges, then the driver decides). |
| `.claude/agents/scout.md` | Read-only Haiku subagent for searches and digesting long output. |
| `.claude/settings.json` | Registers the hooks in exec form with the absolute interpreter path; denies git and edits to kit files. |
| `loop/run_loop.py` | The driver: `doctor`, `harness`, `tests`, `build`, `review`, `go`, `status`. |
| `loop/policy.py` | What may be written in which stage. Shared by the guard and the driver. |
| `loop/checks.py` | How the gate and the tests are run. Shared by the hooks and the driver, so they always agree. |
| `loop/loop.json` | Tier → model routing, attempts, caps. The one place models are named. |
| `loop/prompts/*.md` | Role instructions for the test author, builder, reviewer and diagnostician. |
| `tests/pytest.ini` | Pins the test configuration. |

## What stays project-specific

Written by the harness stage, never by the installer: `verify/smoke_test.py`
(the gate), `verify/fixtures/`, `spec.md`, `plan/test-plan.md`,
`plan/tasks.json`, `CLAUDE.md`, the project skill. Then `tests/` by the tests
stage and the application by the build stage.

## Who may write what

| Stage (`LOOP_STAGE`) | May write | Locked |
|---|---|---|
| `harness` | gate, fixtures, spec, plan, `CLAUDE.md`, skill | kit files |
| `tests` | `tests/` only | everything else |
| `build` (and any plain session) | the application | kit, gate, plan, spec, `CLAUDE.md`, `tests/`, root `conftest.py` / `pytest.ini` / `sitecustomize.py` |
| `review` | nothing | everything |

File-tool writes are checked exactly. Shell commands are checked by
heuristics, which cannot be complete. The backstop is the driver: it holds a
copy of every locked file, compares after each run, restores anything that
changed and fails the attempt.

## Examples

- `examples/smoke_test.example.py` — a complete small gate on gatekit. Copy
  the shape, not the checks.
- `examples/tasks.example.json` — a task plan using all three tiers.

## Tests

```powershell
<python> -m pip install pytest
<python> -m pytest kit\tests -q
```

`tests/fake_claude.py` stands in for the `claude` command, so the suite runs
offline and costs nothing. It proves the kit's logic, not your Claude Code
install; `run_loop.py doctor --live` covers that.
