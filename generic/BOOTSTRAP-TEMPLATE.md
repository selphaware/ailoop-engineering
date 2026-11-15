# BOOTSTRAP — design this build and build its judge

You are going to produce the **harness** for this project: the gate that will
judge the application, and the design (spec, test plan, task plan) that lets
other agents build it unattended. You are NOT building the application. You
are NOT writing the test suite. You are building the thing that judges both,
and the plan the builders follow.

Read this whole file before doing anything.

**Where you sit in the pipeline:**

| Stage | Runs on | Produces |
|---|---|---|
| **Harness (you, now)** | `fable`, interactive | gate + self-test, `spec.md`, test plan, task plan, `CLAUDE.md`, skill |
| Tests | `opus`, unattended | the pytest suite, written from your spec before any app code exists |
| Build | one run per task: `opus` / `sonnet` / `haiku` by the tier you assign | the application |
| Review | `fable`, read-only | what the gate and tests cannot judge |

Every later stage is only as good as what you write here. A vague spec makes
the test author guess. A weak gate lets a broken build through. A task plan
with the wrong tiers wastes the strong model on boilerplate or sends the weak
one at the hard part.

---

## The project

<!-- ============================================================
     FILL THIS IN. Be concrete. Vagueness here costs iterations.
     See BOOTSTRAP-EXAMPLE.md for how specific to be.
     ============================================================ -->

**What it is:**
> <e.g. Python FastAPI service + vanilla JS dashboard frontend>

**Data source:**
> <API URL / DB connection / file paths. Include auth method, or state "none".
>  Paste a sample of the real shape if you have one.>

**The deliverable:**
> <the artifact(s) that must exist and work, e.g. `dashboard.html`, or
>  `app/main.py` + `app/static/index.html`. State the single argument the
>  gate takes: a file, or the app folder.>

**What "working" looks like to a user:**
> <what they would SEE or GET if it worked. Be visual and concrete. Include at
>  least one reconciliation rule: a number on screen or in the output that
>  must equal something computed directly from the source.>

**What "broken but passes tests" looks like:**
> <the silent failures you fear most, numbered F1, F2, F3 — the ones that
>  would sail through lint, type checks, and "it built successfully">

**Environment (fill in what you already know):**
> - Python interpreter: <absolute path, e.g. A:\envs\myproj\Scripts\python.exe>
>   **— this venv already exists; do not create a new one**
> - Node/npm needed? <yes/no, path if yes>
> - Already installed (gate dependencies): <pytest; playwright + Chromium if
>   the gate drives a browser>
> - You may install (app runtime dependencies): <e.g. fastapi, uvicorn, pandas>
>   — into the interpreter above, never into a new venv
> - Anything else the project needs: <DB, env vars, ports>

> **Note on the venv:** it is created by the user *before* this session, because
> the gate self-tests using that interpreter. An agent that builds its own
> verification environment has nothing trustworthy to verify with. App runtime
> packages are different — install those as you discover you need them.

---

The "broken but passes tests" lines are the most important thing on this page.
**They define the gate, and the gate is the whole system.** Each one keeps its
id (F1, F2, ...) from here through the gate, the tests and the review.

---

## Already installed: the loop kit. Use it. Do not rebuild or edit it.

The user installed these before this session. They are identical on every
project and already tested. Read them so you know the contracts you are
writing against; never modify them (the guard will block you).

| File | What it is |
|---|---|
| `verify/gatekit.py` | The gate framework: command line, exit codes, output format, `--selftest`. **Your gate is built on it.** |
| `.claude/hooks/gate_hook.py` | Runs the gate after every file edit during the build. Exit 2 feeds the failure back to the builder; exit 0 for harness errors. |
| `.claude/hooks/stop_gate.py` | A builder cannot finish while its task's checks and tests fail. |
| `.claude/hooks/guard.py` | Blocks writes to the gate, tests, plan and spec once their stage is over, and blocks git. |
| `.claude/settings.json` | Registers the three hooks with the absolute interpreter path. |
| `loop/run_loop.py` | The driver. Runs each later stage on its model, re-judges every run itself, escalates, and stops for the human after three strikes. |
| `loop/loop.json` | Tier → model routing and limits. |
| `loop/examples/smoke_test.example.py` | A complete small gate, for reference. Read it before writing yours. |
| `tests/pytest.ini` | Pins the test run so app code cannot reconfigure it. |

In this session the guard is live with the **harness** policy: you may write
the gate, spec, plan, `CLAUDE.md` and the skill. You may not touch the kit.

---

## Phase 0 — Discover the environment. Do not skip. Do not assume.

Assumptions about the environment are the single biggest source of wasted
iterations. Establish facts first, and **write them down** in the harness.

1. **Find the real Python interpreter.**
   - On Windows, bare `python` may resolve to the Microsoft Store alias stub at
     `...\WindowsApps\python.exe`, which is a 0-byte shim that cannot execute.
     Detect and reject it explicitly.
   - Report the absolute path you will use. Verify with `<path> --version`.
   - Confirm it is the same interpreter the hooks in `.claude/settings.json`
     are registered with. If not, stop and say so.
2. **Find the Node/npm toolchain** if the project needs one. Same rule: absolute
   path, verified by running it.
3. **Check the project location.** Resolve the working directory to an absolute
   path. If it is a mapped network drive or UNC path, say so — headless browsers
   and `file://` URIs behave differently there, and it is far cheaper to know now.
4. **Inspect the data source once.** API: request it and print the raw response
   — and if it errors, diagnose before proceeding (a 403 is as likely to be a
   missing `User-Agent` header as a firewall). File: read the real header and a
   few sample rows. Database: query the schema. Note the true field names,
   nesting, and types. The live source is the truth, not this brief.
5. **Check the kit.** Run `<python> loop/run_loop.py doctor` and read
   `verify/gatekit.py` and `loop/loop.json`. Report anything doctor flags.
6. **Report all of the above back to me before writing any files.**

---

## Phase 1 — Design the gate FIRST

The gate is the harness. Everything else is support. Build it before anything else.

**The gate must catch every failure mode named above**, not merely confirm the
code runs. Lint, type checks, and "it built successfully" do not catch a page
that renders blank, an API that returns `[]`, or a report with every field empty.

Pick the verification method that actually observes the deliverable:

| Deliverable | Gate must |
|---|---|
| HTML/JS frontend | load it in headless Chromium and assert real data is on screen |
| HTTP API | start it, make real requests, assert status + response shape |
| CLI tool | run it on fixture input, assert stdout/exit code |
| Data pipeline | run it, assert output row counts, schema, and value sanity |

Requirements for the gate:

- **Built on `gatekit`.** One `@gate.check("area.what", catches=["F1"], doc=...)`
  per concern. Small checks with stable ids, because the task plan assigns
  each check to the task that must make it pass.
- **Every check names the failure mode it catches.** A check that catches
  nothing you can name is decoration; gatekit refuses it unless you give a
  written reason.
- **Binary.** Exit 0 = pass, non-zero = fail. No warnings tier, no partial credit.
- **Specific failure messages.** Not "verification failed" but "0 populated KPI
  values (need >= 3) — check `.kpi-card .kpi-value` is non-empty". The message is
  fed back to the builder; a vague message costs an iteration.
- **Fast.** It runs on every edit. Seconds, not minutes. A check that cannot
  be made fast is marked `slow=True`: it is skipped on each edit and still run
  when a builder finishes and whenever the driver judges.
- **Deterministic.** `--selftest` runs the good fixture twice and fails if the
  verdict or any recorded value differs.
- **Thresholds derived from the real data**, not invented. If the source only
  supports 2 metrics, a gate demanding 3 can never pass and the builder will
  thrash forever inventing filler. Check the actual data before setting numbers.
- **Reconciles independently.** Where the brief gives a reconciliation rule,
  the gate computes the expected value itself from the source and compares.
  It never trusts a number the application hands it.
- **Offline and deterministic.** If the data source is a live API, the gate
  runs against recorded fixtures in `verify/fixtures/` through an injectable
  transport. No live network in the gate.
- **Distinguishes harness failure from deliverable failure.** A missing
  dependency, a busy port or a missing fixture is `ctx.harness_error(...)`:
  exit 3, the words "HARNESS ERROR", and the code is NOT blamed.
- **Writes only to `verify/artifacts/`.** Anything the gate writes elsewhere
  under `verify/` will be treated as tampering by the driver.

**Standard layout — do not deviate:** the gate lives at `verify/smoke_test.py`,
takes the deliverable path as its argument, supports `--selftest`, `--list`,
`--only`, `--fast` and `--json` (gatekit provides all five), and writes any screenshots
to `verify/artifacts/`. A consistent layout means the same driver and hooks
work on every project.

**Then prove the gate works.** For every failure mode, register a
`@gate.failure_mode("F1", ...)` fixture: a deliverable broken in exactly that
way and no other. Register one `@gate.good_fixture`. Then `--selftest`:

- passes the known-GOOD fixture on every check
- fails each known-BROKEN fixture, **on a check that names that failure mode**
- runs both from a temp dir and from the project dir, and reports if they
  disagree

Run the self-test. **A gate you have not watched fail is not a gate.** Do not
proceed until it discriminates correctly for every failure mode.

---

## Phase 2 — Write the design the other stages build from

You are the only stage that sees the whole problem with the strongest model.
Spend that here.

### `spec.md` — the contract
Concrete, not a template. Real endpoints, real field names from Phase 0, the
actual metrics and views wanted, and any known traps in the data (scale
mismatches, gaps, nulls). It must contain an **interface contract**: module
paths, function signatures, endpoints, command lines, file formats. Precise
enough that someone could write tests against it without ever seeing the
code, because that is exactly what happens next. Where a choice is open, say
it is open, so the test author does not pin it down by accident.

### `plan/test-plan.md` — what the test suite must prove
For each test file: what it proves and through which interface. Require one
regression test per failure mode (F1, F2, ...), a reconciliation test for
every reconciliation rule, and name the fixtures needed in `tests/fixtures/`
(built from the real data sample you saw in Phase 0). Say what is NOT to be
tested because it needs a human eye.

### `plan/tasks.json` — the build, cut into verifiable tasks
The driver runs one unattended session per task, on the model its tier names,
then re-runs that task's acceptance checks itself. Format:

```json
{
  "version": 1,
  "deliverable": "<the gate's argument>",
  "tasks": [
    {
      "id": "T1",
      "title": "short name",
      "tier": "complex | routine | support",
      "why_tier": "one line of justification",
      "depends_on": [],
      "writes": ["files this task creates or changes"],
      "brief": "what to build, pointing at spec sections",
      "gate_checks": ["check ids this task must turn green"],
      "tests": ["tests/test_x.py"]
    }
  ]
}
```

Rules for the plan:

- **Every task is verifiable.** At least one gate check or test file. A task
  nothing can fail is not a task.
- **Every gate check and every planned test file belongs to a task.** Earlier
  tasks' checks are re-run on every later task, so the build can only ratchet
  forward.
- **Small.** One concern, a handful of files. If a brief needs the word "and"
  twice, split it.
- **Tier by the cost of being subtly wrong, not by size:**

  | Tier | Model | Use for |
  |---|---|---|
  | `complex` | `opus` | Anything carrying a named failure mode or a reconciliation rule. Wiring across layers. Process lifecycle, concurrency, parsing of messy real data. Work where a plausible wrong answer would survive a casual look. |
  | `routine` | `sonnet` | One concern with a clear contract in the spec and an obvious pattern to follow. |
  | `support` | `haiku` | One obvious right answer: scaffolding, config, static assets, sample-data files, usage docs. |

  A task that carries a named failure mode starts at `complex`. Otherwise,
  when torn between two tiers, choose the lower: a task that fails escalates
  automatically, and the build report shows where the estimate was wrong.

### `CLAUDE.md` — always-loaded conventions
- The definition of done, stated as the literal gate command and test command.
- The contract the deliverable must satisfy, as a table.
- The failure-mode matrix (paste the output of `--matrix`).
- The environment facts from Phase 0 (absolute interpreter paths, ports).
- Guardrails: no secrets in code, no editing the harness, no git, scope of writes.
- An autonomy clause: work through gate failures independently; only stop if the
  same failure repeats 3 times or an external dependency is unreachable.

### A skill — the reusable procedure
At `.claude/skills/<project>-build/SKILL.md`: the steps to build this kind of
deliverable, in order, with a "common failures and their real causes" table.

### Not yours to build
The hooks, `settings.json`, and the outer loop are the kit. They exist. **A
self-verifying agent that can edit its own judge will eventually edit its own
judge**, which is why the judge is locked by a guard, by deny rules, and by a
tamper check in the driver that restores any locked file an agent changes.

---

## Phase 3 — Prove the whole thing

Before you tell me it is done:

1. `--selftest` passes: the gate discriminates good from broken for **every**
   named failure mode, each caught by a check that names it.
2. The hook logic is proven **by direct invocation** with THIS project's gate —
   pipe a simulated tool-use JSON payload into each hook script on stdin, with
   `LOOP_STAGE=build` set for that command, and confirm:
   - `gate_hook.py`: exit 2 with a useful message while the deliverable is
     missing or broken; exit 0 with a "HARNESS ERROR" message (not a code
     complaint) when a gate dependency or fixture is missing.
   - `guard.py`: exit 2 for a write to `verify/smoke_test.py`; exit 0 for a
     write to a file inside the deliverable.

   **Important:** do not claim you saw the gate hook fire on its own. In this
   session it is switched off on purpose (harness stage), so it CANNOT fire
   here. State clearly in your final report that the user must run the
   live-fire test themselves, in a fresh session.
3. Every absolute path in the harness has been verified to exist and run.
4. `<python> loop/run_loop.py doctor` is clean, and you have pasted the output
   of `<python> loop/run_loop.py build --dry-run` so I can check the routing.
5. Report: the exact gate command, the interpreter path, the failure-mode
   matrix, the task table (id, tier, why), the hook status (including the
   live-fire requirement above), and anything you discovered in Phase 0 that
   contradicted this brief.

Then stop. Do not write tests. Do not build the application. Those are
separate stages, started by me.

---

## Rules

- **Verify, don't assert.** Every claim about the environment must come from a
  command you ran, not from what is usually true.
- **Tell me when this brief is wrong.** If Phase 0 contradicts something above,
  say so plainly rather than working around it silently.
- Prefer fewer moving parts. Every dependency is something that can drift.
- Never edit kit files. Never run git.
