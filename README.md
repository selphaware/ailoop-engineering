# ailoop-engineering

Autonomous, model-routed build loops for Claude Code, with a judge the
agents cannot edit.

You define "done" as a program that returns pass or fail. Agents iterate
against it until it passes. Each stage runs on the model that stage calls
for, and a small driver script re-judges every result itself, because an
agent saying it has finished proves nothing.

```
 brief ─▶ HARNESS ─▶ TESTS ─▶ BUILD (one run per task) ─▶ REVIEW
          fable      opus     opus / sonnet / haiku        fable
          gate,      suite    by the tier the plan         read-only
          spec,      written  gives each task;
          plans      first    escalates on failure
            │          │              │                       │
          commit     commit   stops after three strikes     commit
                              and asks fable to diagnose
```

**Start here:** [`SETUP-GUIDE.md`](SETUP-GUIDE.md).

## What is in this repo

| Path | What it is |
|---|---|
| [`SETUP-GUIDE.md`](SETUP-GUIDE.md) | The steps, start to finish, for Windows. |
| [`MODEL-ROUTING.md`](MODEL-ROUTING.md) | Which model does what, why, and the one file to edit when models change. |
| [`kit/`](kit/) | The fixed machinery, copied into each project by `kit/install_kit.py`. Has its own tests. One copy, shared by both kinds of project. |
| [`generic/`](generic/) | Briefs for applications: dashboards, APIs, pipelines, CLIs, report generators. |
| [`ML/`](ML/) | Briefs for modelling tools: profilers, training pipelines, evaluation tools. |

Each of `generic/` and `ML/` holds the same three files, and `ML/` one more:

| File | What it is |
|---|---|
| `BOOTSTRAP-TEMPLATE.md` | The brief the harness stage follows. Fill in the project block at the top. |
| `BOOTSTRAP-EXAMPLE.md` | The template filled in for a real project, annotated. |
| `PROJECT-INSTRUCTIONS.md` | Instructions for a claude.ai Project that interviews you and writes the bootstrap. |
| `ML-GATE-PATTERNS.md` (ML only) | The synthetic datasets a modelling gate is built from. |

**Which one?** If the tool's output is a model, a score or a statistical
conclusion, use `ML/`. Its brief has a methodology section, and its gate
judges the tool on synthetic data with a known right answer, because on real
data there is no right score to check. Everything else uses `generic/`. The
kit, the driver, the routing and the setup steps are the same for both.

## The guardrails, in one table

| Risk | What stops it |
|---|---|
| A build that runs but is silently wrong | The gate: every named failure mode (F1, F2, ...) has a check, and a broken fixture that proves the check fires (`--selftest`) |
| A gate nobody ever saw fail | `--selftest`, `run_loop.py doctor`, and the live-fire test in the setup guide |
| Tests written to fit the code | Tests are written first, from the spec, by a different model, and must be red before the build starts |
| An agent editing its own judge | Three layers: deny rules, a guard hook on every write and shell command, and a tamper check in the driver that restores any locked file and fails the attempt |
| An agent declaring victory | The driver re-runs the task's checks itself after every run. A `Stop` hook refuses to let a build run end while its checks fail |
| A later task breaking an earlier one | Every earlier check is re-run on every later task |
| A gate too slow to run on every edit | Checks marked `slow` are skipped per edit, and still run when a builder finishes and whenever the driver judges. `doctor` times the per-edit run against a budget |
| A gate that changes its mind between runs | `--selftest` runs the known-good fixture twice and fails if the verdict or any measured value differs |
| A plausible, wrong model score | Synthetic ground truth: planted signal must be found, pure noise must show none, a leaked column must be flagged (`ML/ML-GATE-PATTERNS.md`) |
| Thrashing on an impossible task | Fixed attempts per tier, then a hard stop and a read-only diagnosis. No agent rewrites the spec, gate or tests unattended |
| Passing the checks but missing the point | A read-only review on the strongest model, then you |
| A runaway bill | Turn, time and spend caps per run, and a total budget |
| Agents touching git | Denied outright. The driver only reads git state |

## What the kit has and has not been tested against

`kit/tests` (171 tests) exercises the guard rules, the gate framework, the
three hooks and the driver end to end: routing, escalation, three strikes,
tamper detection and restore, budgets, the red-before-build rule, slow
checks, score bands and the determinism check.

Those tests drive a **stand-in** for the `claude` command. They prove the
loop's own logic. They do not prove that your installed Claude Code accepts
every flag, or that the hooks load on your machine. Three steps in the setup
guide cover that, and none is optional the first time:

1. `python -m pytest kit\tests` on your machine (the suite was developed on
   Linux; this is its first run on Windows).
2. `run_loop.py doctor --live`: one small real call that exercises the
   driver's flags and an unattended command.
3. The live-fire test: watch the gate reject a broken file and the guard
   refuse an edit to the gate.

## What changed from the first version

- Models are chosen by alias in one file (`loop/loop.json`), not typed by hand
  per session and not named by version in the docs.
- The harness stage now also produces a spec with an interface contract, a
  test plan, and a task plan with a model tier per task.
- A real test suite, written before the code by a different model.
- Per-task routing with automatic escalation, and the three-strikes rule
  enforced by the driver rather than remembered.
- The hooks, guard, driver and gate framework ship as tested files instead of
  being regenerated per project.
- The judge is protected against shell and subprocess writes, not only
  against the Edit tool.
- A final read-only review stage.
- Corrected: hooks no longer need a session restart to register (settings
  are normally picked up live), though a fresh session per stage is still
  how the loop runs.

Added since:

- Briefs split into `generic/` and `ML/`, over one shared kit.
- Slow checks and a per-edit fast profile, score bands, a determinism check
  in the self-test, and gate timing in `doctor`.
- A runnable example gate for a modelling tool.

## Requirements

Windows (the guide is written for it; nothing in the kit is Windows-only),
Python 3.10+, Claude Code 2.1.302 or later on the Anthropic API or a Claude
subscription with access to Fable, Opus, Sonnet and Haiku.
