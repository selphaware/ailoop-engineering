# BOOTSTRAP (ML / data science) — design this build and build its judge

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

**Why this variant exists.** A modelling tool has no right answer on real
data. Its worst bugs produce a plausible number: a leaked feature, a score
computed on training rows, a join that quietly multiplies rows. Nothing
crashes and nothing looks wrong. So this gate does not judge real-data
scores at all. It manufactures ground truth: synthetic datasets where the
correct conclusion is known by construction, and it checks the tool reaches
that conclusion. `ML-GATE-PATTERNS.md` is the catalogue of those datasets.

---

## The project

<!-- ============================================================
     FILL THIS IN. Be concrete. Vagueness here costs iterations.
     See BOOTSTRAP-EXAMPLE.md (ML) for how specific to be.
     ============================================================ -->

**What it is:**
> <e.g. Python CLI that profiles a tabular dataset and reports how predictable
>  a chosen target is; pandas + scikit-learn; writes JSON and an HTML report>

**Data source:**
> <file paths / DB connection / API. One dataset or several to be joined; if
>  several, the join keys and the expected cardinality (one-to-one,
>  many-to-one). Paste the real header and a few rows of each.>

**The deliverable:**
> <the artifact(s) that must exist and work, and the single argument the gate
>  takes (usually the app folder). Name the tool's public entry point: the
>  command line or function the gate will drive.>

**What "working" looks like to a user:**
> <what they would SEE or GET: the report sections, the headline number, the
>  files written. Include reconciliation rules: row counts in the output equal
>  the source; numbers in the report equal the numbers in the JSON.>

**How it is measured (methodology):**
> - Task type(s): <classification / regression / both; how the tool decides>
> - Headline measure and its baseline: <e.g. ROC AUC on a holdout, against 0.5;
>   or skill versus predicting the mean>
> - Validation scheme: <holdout / k-fold / grouped by entity / time-ordered>,
>   and why that one fits this data
> - Model families in scope and the search budget: <which, how many, how long>
> - How the headline avoids best-of-many inflation: <untouched holdout / nested CV>
> - Reported alongside the headline: <fold spread, permutation p-value, ...>
> - Scale and runtime budget: <rows x columns expected; acceptable run time>
> - Fast profile: <the small configuration the gate runs on every edit>

**What "broken but passes tests" looks like:**
> <the silent failures you fear most, numbered F1, F2, F3 — each one a way of
>  producing a plausible, wrong number>

**Environment (fill in what you already know):**
> - Python interpreter: <absolute path, e.g. A:\envs\myproj\Scripts\python.exe>
>   **— this venv already exists; do not create a new one**
> - Already installed (gate dependencies): <pytest; playwright + Chromium only
>   if the gate must look at a rendered report in a browser>
> - You may install (app runtime dependencies): <e.g. pandas, scikit-learn>
>   — into the interpreter above, never into a new venv; pin versions in
>   `requirements.txt`, because a library upgrade can move a score
> - Anything else the project needs: <DB, env vars, GPU, thread settings>

> **Note on the venv:** it is created by the user *before* this session, because
> the gate self-tests using that interpreter. An agent that builds its own
> verification environment has nothing trustworthy to verify with. App runtime
> packages are different — install those as you discover you need them.

---

The "broken but passes tests" lines are the most important thing on this page.
**They define the gate, and the gate is the whole system.** Each one keeps its
id (F1, F2, ...) from here through the gate, the tests and the review.

The methodology lines are the second most important. The gate can prove the
tool is not leaking or miscounting. It cannot decide what "predictable" should
mean. That decision is the user's, it is written above, and you carry it into
`spec.md` unchanged. If it is missing or contradictory, stop and ask.

---

## Already installed: the loop kit. Use it. Do not rebuild or edit it.

The user installed these before this session. They are identical on every
project and already tested. Read them so you know the contracts you are
writing against; never modify them (the guard will block you).

| File | What it is |
|---|---|
| `verify/gatekit.py` | The gate framework: command line, exit codes, output format, `--selftest`, slow checks, score bands. **Your gate is built on it.** |
| `.claude/hooks/gate_hook.py` | Runs the gate's fast profile after every file edit during the build. Exit 2 feeds the failure back to the builder; exit 0 for harness errors. |
| `.claude/hooks/stop_gate.py` | A builder cannot finish while its task's checks and tests fail. Runs the slow checks too. |
| `.claude/hooks/guard.py` | Blocks writes to the gate, tests, plan and spec once their stage is over, and blocks git. |
| `.claude/settings.json` | Registers the three hooks with the absolute interpreter path. |
| `loop/run_loop.py` | The driver. Runs each later stage on its model, re-judges every run itself with the full gate, escalates, and stops for the human after three strikes. |
| `loop/loop.json` | Tier → model routing and limits. |
| `loop/examples/smoke_test.ml.example.py` | A complete small gate of this kind, for reference. Read it before writing yours. |
| `tests/pytest.ini` | Pins the test run so app code cannot reconfigure it. |

In this session the guard is live with the **harness** policy: you may write
the gate, spec, plan, `CLAUDE.md` and the skill. You may not touch the kit.

---

## Phase 0 — Discover the environment and the data. Do not skip. Do not assume.

Assumptions about the environment are the single biggest source of wasted
iterations. Establish facts first, and **write them down** in the harness.

1. **Find the real Python interpreter.**
   - On Windows, bare `python` may resolve to the Microsoft Store alias stub at
     `...\WindowsApps\python.exe`, which is a 0-byte shim that cannot execute.
     Detect and reject it explicitly.
   - Report the absolute path you will use. Verify with `<path> --version`.
   - Confirm it is the same interpreter the hooks in `.claude/settings.json`
     are registered with. If not, stop and say so.
2. **Record the modelling stack.** Which of pandas, numpy, scikit-learn and
   any boosting library are installed, and their exact versions. Report the
   CPU thread count. These go into `CLAUDE.md`; a score that moves after an
   upgrade must be traceable.
3. **Check the project location.** Resolve the working directory to an absolute
   path. If it is a mapped network drive or UNC path, say so.
4. **Inspect every dataset once.** For each: row count, columns and dtypes as
   loaded, missing-value counts, exact duplicate rows. For the target: its
   type and distribution (class balance, or range and skew). For each join
   key: uniqueness on both sides, type on both sides, and how many keys match.
   Note any date or time column and whether rows are ordered by it. Note any
   column that looks like it is only known after the outcome. The data is the
   truth, not this brief.
5. **Time one tiny fit.** Fit the simplest in-scope model on a small sample
   and report the seconds. This sets what the per-edit gate can afford.
6. **Check the kit.** Run `<python> loop/run_loop.py doctor` and read
   `verify/gatekit.py` and `loop/loop.json`. Report anything doctor flags.
7. **Report all of the above back to me before writing any files.** Say
   plainly where the data contradicts the methodology above: a grouped
   structure with an ungrouped scheme, a time order with a random split, a
   target too rare for the chosen metric.

---

## Phase 1 — Design the gate FIRST

The gate is the harness. Everything else is support. Build it before anything else.

**The gate must catch every failure mode named above**, not merely confirm the
code runs. For a modelling tool, "it ran and wrote a report with numbers in
it" is exactly what every failure mode above also does.

**How this kind of gate observes the deliverable:**

| What is judged | Gate must |
|---|---|
| The modelling conclusion | run the tool on synthetic data with a known answer and assert the conclusion: signal found where it was planted, none found in noise, the leak flagged |
| Data handling | run the tool on small crafted tables and reconcile: rows in equals rows accounted for, join cardinality as declared |
| The output | read the files the tool wrote and assert every required section is populated, no NaN or infinity, and the report's numbers equal the JSON's |

Requirements for the gate:

- **Built on `gatekit`.** One `@gate.check("area.what", catches=["F1"], doc=...)`
  per concern. Small checks with stable ids, because the task plan assigns
  each check to the task that must make it pass.
- **Every check names the failure mode it catches.** A check that catches
  nothing you can name is decoration; gatekit refuses it unless you give a
  written reason.
- **Synthetic ground truth, generated by the gate.** Each dataset is built in
  code from a fixed seed into `verify/artifacts/`, small enough to run in
  seconds. Use the patterns in `ML-GATE-PATTERNS.md`: at minimum a
  planted-signal set, a pure-noise set, and one set per named failure mode.
- **Never assert a score on real data.** On the user's real data the gate may
  check structure only: row reconciliation, schema, join cardinality. There
  is no known right score there, so a threshold would be invented.
- **Scores are asserted as bands, and the bands are measured.** Use
  `ctx.require_between(value, low, high, label)`. To set a band: run the
  known-good fixture over at least five data seeds, take the observed range,
  add a margin, and confirm every broken fixture lands outside it on every
  seed. Write the measured ranges in a comment beside the band. A band you
  guessed is a threshold you invented.
- **Deterministic.** Fixed seeds everywhere, and single-threaded inside the
  gate (set the library's job count to 1 and the thread environment variables
  before the tool starts). Record every measured value with `ctx.record` or
  the band helpers: `--selftest` runs the good fixture twice and fails if
  anything moves.
- **A fast profile for the per-edit run.** The tool must expose a small
  configuration (tiny data, few models, no search). The gate uses it. Mark
  any check that still takes more than a few seconds `slow=True`: it is
  skipped on each edit and run when a builder finishes and whenever the
  driver judges. Use `ctx.fast` in setup to skip heavy preparation. Aim for
  the per-edit run to finish within the budget `doctor` reports.
- **Through the public interface.** Drive the tool the way a user would (its
  command line or its documented function) and read what it wrote. Never
  import internals; the builder is free to change those.
- **Binary.** Exit 0 = pass, non-zero = fail. No warnings tier, no partial credit.
- **Specific failure messages.** Not "score check failed" but "lift on the
  pure-noise data is 0.47, expected between -0.2 and 0.2: the score is being
  computed on rows the model was fitted on". The message is fed back to the
  builder; a vague message costs an iteration.
- **Reconciles independently.** The gate counts rows and recomputes simple
  totals itself from the source. It never trusts a count the tool reports.
- **Distinguishes harness failure from deliverable failure.** A missing
  library, an unwritable artifacts folder or a missing fixture is
  `ctx.harness_error(...)`: exit 3, the words "HARNESS ERROR", and the code
  is NOT blamed.
- **Writes only to `verify/artifacts/`.** Anything the gate writes elsewhere
  under `verify/` will be treated as tampering by the driver. Point the tool's
  own output at a folder under `verify/artifacts/` during gate runs.

**Standard layout — do not deviate:** the gate lives at `verify/smoke_test.py`,
takes the deliverable path as its argument, supports `--selftest`, `--list`,
`--only`, `--fast` and `--json` (gatekit provides all five), and writes its
datasets and any outputs to `verify/artifacts/`. A consistent layout means the
same driver and hooks work on every project.

**Then prove the gate works.** For every failure mode, register a
`@gate.failure_mode("F1", ...)` fixture: a small implementation of the tool's
interface that is broken in exactly that way and no other. Register one
`@gate.good_fixture`: a small correct implementation. Then `--selftest`:

- passes the known-GOOD fixture on every check, twice, with identical values
- fails each known-BROKEN fixture, **on a check that names that failure mode**
- runs both from a temp dir and from the project dir, and reports if they
  disagree

The fixtures are reference implementations of the interface, a few dozen
lines each. Writing them is also the first real test of your interface
contract: if the good fixture is awkward to write, the contract is wrong.

Run the self-test. **A gate you have not watched fail is not a gate.** Do not
proceed until it discriminates correctly for every failure mode.

---

## Phase 2 — Write the design the other stages build from

You are the only stage that sees the whole problem with the strongest model.
Spend that here.

### `spec.md` — the contract
Concrete, not a template. It must contain:

- **The methodology, as decided above**, restated precisely enough to
  implement: the split, what is fitted on which rows, how the model is
  chosen, which rows the headline is computed on, the baseline, the seed
  policy. A reader must be able to tell from the spec alone whether a given
  implementation leaks.
- **An interface contract:** the command line and its options, the function
  signatures, the config file format, and the exact schema of the output
  (every key in the JSON, its type and its meaning; the report's section
  ids). Precise enough that someone could write tests against it without ever
  seeing the code, because that is exactly what happens next.
- **The data facts from Phase 0** and the traps found there.
- **What happens at the edges:** an unknown column type, a constant column, a
  target with one class, an unmatched join key, a dataset too small to split.
  Each one either raises a named error or is reported in the output. None is
  silently skipped.
- **What is open.** Where the builder may choose freely, say so, so the test
  author does not pin it down by accident.

### `plan/test-plan.md` — what the test suite must prove
For each test file: what it proves and through which interface. Require:

- one regression test per failure mode (F1, F2, ...)
- **exact tests of the arithmetic**: every metric, baseline and split
  function checked against values worked out by hand on arrays of five to ten
  elements
- **structural tests of every split**: no row in two folds, no entity on both
  sides of a grouped split, no future row in a time-ordered training set
- **join tests**: one-to-one, many-to-one, duplicate keys, mismatched key
  types, unmatched keys, each with the outcome the spec gives
- **invariants** that must hold whatever the model does: shuffling the target
  removes the signal; adding a constant column changes nothing; the same seed
  gives the same result
- reconciliation tests for every reconciliation rule
- the fixtures needed in `tests/fixtures/`, small and built from the real
  data shape seen in Phase 0

Say what is NOT tested because it needs a human eye, and say that the tests
must run on tiny data: the suite is for correctness, the gate's synthetic
sets are for the modelling conclusion.

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
- **Data handling before modelling.** Loading, typing, joining and splitting
  are built and verified first. A model fitted on a wrong table proves nothing.
- **Tier by the cost of being subtly wrong, not by size:**

  | Tier | Model | Use for |
  |---|---|---|
  | `complex` | `opus` | Anything that decides which rows a number is computed on: splitting, validation, fitting preprocessing, metric and baseline computation, model selection, leakage detection, joins, target handling. Anything carrying a named failure mode. |
  | `routine` | `sonnet` | One concern behind an interface that already exists: another model family, another report section, command-line plumbing, config parsing. |
  | `support` | `haiku` | One obvious right answer: scaffolding, `requirements.txt`, static report assets, usage docs. |

  A task that carries a named failure mode starts at `complex`. Otherwise,
  when torn between two tiers, choose the lower: a task that fails escalates
  automatically, and the build report shows where the estimate was wrong.

### `CLAUDE.md` — always-loaded conventions
- The definition of done, stated as the literal gate command and test command.
- The methodology in five lines, and the sentence: "the headline is computed
  only on rows no fitted step has seen".
- The output schema, as a table.
- The failure-mode matrix (paste the output of `--matrix`).
- The environment facts from Phase 0: interpreter path, library versions,
  seed policy, thread settings.
- Guardrails: no secrets in code, no editing the harness, no git, scope of
  writes, no network at run time, new dependencies pinned in `requirements.txt`.
- An autonomy clause: work through gate failures independently; only stop if the
  same failure repeats 3 times or an external dependency is unreachable.

### A skill — the reusable procedure
At `.claude/skills/<project>-build/SKILL.md`: the steps to build this kind of
tool, in order, with a "common failures and their real causes" table (a
scaler fitted before the split; a pipeline refitted on the full data before
scoring; an id column left in the features; float keys in a join).

### Not yours to build
The hooks, `settings.json`, and the outer loop are the kit. They exist. **A
self-verifying agent that can edit its own judge will eventually edit its own
judge**, which is why the judge is locked by a guard, by deny rules, and by a
tamper check in the driver that restores any locked file an agent changes.
For a modelling tool the temptation has a specific shape: widening a band
until a wrong score fits. The bands are yours, set by measurement, and locked.

---

## Phase 3 — Prove the whole thing

Before you tell me it is done:

1. `--selftest` passes: the gate discriminates good from broken for **every**
   named failure mode, each caught by a check that names it, and the good
   fixture gives identical values on both runs.
2. For every band, you have reported the measured range over the seeds you
   tried, for the good fixture and for each broken one, and the gap between them.
3. The hook logic is proven **by direct invocation** with THIS project's gate —
   pipe a simulated tool-use JSON payload into each hook script on stdin, with
   `LOOP_STAGE=build` set for that command, and confirm:
   - `gate_hook.py`: exit 2 with a useful message while the deliverable is
     missing or broken; exit 0 with a "HARNESS ERROR" message (not a code
     complaint) when a gate dependency is missing.
   - `guard.py`: exit 2 for a write to `verify/smoke_test.py`; exit 0 for a
     write to a file inside the deliverable.

   **Important:** do not claim you saw the gate hook fire on its own. In this
   session it is switched off on purpose (harness stage), so it CANNOT fire
   here. State clearly in your final report that the user must run the
   live-fire test themselves, in a fresh session.
4. Every absolute path in the harness has been verified to exist and run.
5. `<python> loop/run_loop.py doctor` is clean, including its gate timing line
   (per-edit run within budget) and no determinism failure, and you have
   pasted the output of `<python> loop/run_loop.py build --dry-run` so I can
   check the routing.
6. Report: the exact gate command, the interpreter path and library versions,
   the failure-mode matrix, the bands and how they were measured, the task
   table (id, tier, why), the hook status (including the live-fire requirement
   above), anything in Phase 0 that contradicted this brief, and **every
   place where the data argues against the methodology as written**.

Then stop. Do not write tests. Do not build the application. Those are
separate stages, started by me.

---

## Rules

- **Verify, don't assert.** Every claim about the environment or the data must
  come from a command you ran, not from what is usually true.
- **Tell me when this brief is wrong.** If Phase 0 contradicts something above,
  say so plainly rather than working around it silently.
- **Never tune the judge to the result.** A band, a seed or a fixture is
  changed only because it was measured wrong, never because a build missed it.
- **Do not decide the methodology.** Flag what the data argues against, and stop.
- Prefer fewer moving parts. Every dependency is something that can drift.
- Never edit kit files. Never run git.
