# BOOTSTRAP (ML / data science) — design this build and build its judge

> **This is a worked EXAMPLE**, not a template to run as-is. It shows how
> specific to be when filling in the project section of the ML template, and
> how Phases 0–3 are adapted to one project's shape: two tables that must be
> joined, a binary target, and a report whose headline is a single number.
>
> Annotations in *italics* explain why each answer is written that way. Delete
> them in your real version.

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
data. Its worst bugs produce a plausible number. So this gate does not judge
real-data scores at all. It manufactures ground truth: synthetic datasets
where the correct conclusion is known by construction, and it checks the tool
reaches that conclusion.

---

## The project

**What it is:**
> A Python command-line tool that takes a customer table and a transactions
> table, joins them, and reports how predictable customer churn is. pandas and
> scikit-learn. It writes `profile.json` and a self-contained `report.html`.

*Why this is a good answer: language, libraries, the fact that a join is
involved, and both output files. The agent knows there is a data-handling
half and a modelling half, and that the task plan has a seam between them.*

**Data source:**
> - `data/customers.csv` — one row per customer, about 8,000 rows. Columns
>   (verify against the file): `customer_id, signup_date, plan, region,
>   monthly_fee, support_tickets, cancellation_date, churned`.
> - `data/transactions.csv` — many rows per customer, about 190,000 rows.
>   Columns: `txn_id, customer_id, txn_date, amount, channel`.
> - Join: `transactions` → `customers` on `customer_id`, **many-to-one**.
>   Transactions are aggregated to one row per customer before the join.
> - Target: `churned` (0/1), in `customers.csv`. No auth, no network.

*Why this is a good answer: it states the cardinality of the join and that
aggregation comes first. Those two facts are where most of the silent
failures below come from, so they are pinned before anything is built.*

**The deliverable:**
> - `app/cli.py` — entry point: `python -m app.cli profile --config run.json`
> - `app/load.py` — reads, types and joins the tables
> - `app/model.py` — splitting, fitting, scoring
> - `app/report.py` — writes `profile.json` and `report.html` to the output folder
>
> The gate takes one argument: the `app` folder. It drives the tool only
> through `python -m app.cli profile --config <file>`.

*Why this is a good answer: one public entry point, named. The gate uses the
command line a user would, so the builder stays free to reorganise the inside.*

**What "working" looks like to a user:**
> They run the command and get `report.html` with: a data summary (rows per
> table, rows after the join, customers with no transactions); the headline
> "predictability" figure with its baseline; a table of the models tried; the
> top features; and a warnings panel listing any column excluded as a
> suspected leak. `profile.json` carries the same numbers.
> Reconciliation: joined rows equal the number of customers; every number in
> the report equals the number in `profile.json`.

*Why this is a good answer: it says what is on the page and gives two
reconciliation rules the gate can compute for itself.*

**How it is measured (methodology):**
> - Task type: binary classification only.
> - Headline: ROC AUC on a 25% holdout that no fitted step has seen, reported
>   as lift over the 0.5 baseline. AUC rather than accuracy because churn is
>   rare (about 9% in the sample).
> - Validation: the holdout is split off first, stratified on the target. The
>   model is chosen by 5-fold cross-validation on the other 75% only. One row
>   per customer after aggregation, so no grouping is needed; the tool must
>   refuse to continue if `customer_id` is not unique after the join.
> - Models: logistic regression, random forest, gradient boosting, all
>   scikit-learn, default settings plus a grid of at most 12 combinations each.
> - Inflation: the headline is the chosen model's score on the holdout, never
>   the best cross-validation score.
> - Alongside: the spread across folds, and a permutation p-value (target
>   shuffled 200 times).
> - Scale: up to 100,000 customers; a full run within 10 minutes on 8 cores.
> - Fast profile: `"profile": "fast"` in the config — logistic regression and
>   a 20-tree forest, no grid, no permutation test, at most 2,000 customers.

*Why this is a good answer: every line removes a decision the builder would
otherwise make silently. "Holdout split off first" and "headline from the
holdout, never the best fold" are the two sentences that separate a real
measurement from an inflated one. The fast profile is what lets the gate run
on every edit.*

**What "broken but passes tests" looks like:**
> - **F1.** The score is computed on rows a fitted step has seen: the scaler or
>   the model is fitted on all rows before the split. The headline looks
>   excellent and means nothing.
> - **F2.** `cancellation_date` is only filled in for churned customers. It is
>   used as a feature, the model scores near 1.0, and the report calls churn
>   "highly predictable".
> - **F3.** Transactions are joined without aggregating. Each customer becomes
>   dozens of rows, the same customer sits on both sides of the split, and the
>   row count quietly becomes 190,000.
> - **F4.** `customer_id` is read as an integer in one table and text in the
>   other. Most transactions fail to match and every spending feature is zero
>   for most customers. Nothing errors.
> - **F5.** The headline is the best cross-validation score of the many models
>   tried, not the holdout score. On data with no signal it still shows lift.
> - **F6.** Accuracy is reported as the headline. With 9% churn, predicting
>   "nobody churns" scores 91% and the report presents that as predictability.

*Why this is a good answer: six ways to produce a confident, wrong number,
each tied to this project's own data. Each becomes a synthetic dataset the
gate builds, a broken reference implementation that proves the gate notices,
a regression test, and a reason to put a task on the strongest coding model.*

**Environment:**
> - Python interpreter: `A:\envs\churn-profiler\Scripts\python.exe`
>   **(already created by me before this session)**
> - Already installed (gate dependencies): `pytest`. No browser: the gate
>   reads `report.html` as text.
> - You will need to install (app runtime): `pandas`, `scikit-learn`, `jinja2`
>   — into the interpreter above, pinned in `requirements.txt`.
> - 16 cores available. No GPU needed. No network at run time.

*Why this is a good answer: gate dependencies and app dependencies are
separated, and versions are to be pinned, because a library upgrade can move
a score and the bands in the gate are measured against specific versions.*

---

The "broken but passes tests" lines are the most important thing on this page.
**They define the gate, and the gate is the whole system.**

The methodology lines are the second most important. You carry them into
`spec.md` unchanged. If Phase 0 shows the data argues against them, say so
and stop; do not choose a different methodology yourself.

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
| `loop/examples/smoke_test.ml.example.py` | A complete small gate of this kind, for reference. |
| `tests/pytest.ini` | Pins the test run so app code cannot reconfigure it. |

In this session the guard is live with the **harness** policy: you may write
the gate, spec, plan, `CLAUDE.md` and the skill. You may not touch the kit.

---

## Phase 0 — Discover the environment and the data. Do not skip. Do not assume.

1. **Find the real Python interpreter.**
   - On Windows, bare `python` may resolve to the Microsoft Store alias stub at
     `...\WindowsApps\python.exe`, which is a 0-byte shim that cannot execute.
     Detect and reject it explicitly.
   - Verify with `A:\envs\churn-profiler\Scripts\python.exe --version`.
   - Confirm it is the same interpreter the hooks in `.claude/settings.json`
     are registered with. If not, stop and say so.
2. **Record the modelling stack.** Whether pandas, numpy and scikit-learn are
   installed, and their exact versions. Report the CPU thread count.
3. **Check the project location.** Resolve the working directory to an absolute
   path. If it is a mapped network drive or UNC path, say so.
4. **Inspect both tables.**
   - `customers.csv`: row count; dtypes as pandas loads them; missing values
     per column; duplicate `customer_id` values; the share of `churned == 1`;
     and for `cancellation_date`, how many rows are filled in for churned and
     for retained customers separately.
   - `transactions.csv`: row count; dtypes; date range; transactions per
     customer (min, median, max).
   - The join: the dtype of `customer_id` on each side; how many customer ids
     have no transactions; how many transaction ids match no customer.
5. **Time one tiny fit.** Logistic regression on 2,000 customers: report the
   seconds. This sets what the fast profile can afford.
6. **Check the kit.** Run `A:\envs\churn-profiler\Scripts\python.exe loop/run_loop.py doctor`,
   and read `verify/gatekit.py`, `loop/loop.json` and the example gate.
7. **Report all of the above back to me before writing any files.** In
   particular: whether `cancellation_date` is the leak the brief suspects,
   whether any other column is only known after the outcome, and whether 9%
   churn leaves enough positives in a 25% holdout for a stable AUC.

*Adapted from the template: step 4 asks for exactly the facts the six failure
modes depend on, and step 7 names the three places where this data could
argue against the methodology.*

---

## Phase 1 — Design the gate FIRST

The gate is the harness. Everything else is support. Build it before anything else.

**The gate must catch the six failure modes named above.** It runs the tool
through `python -m app.cli profile --config <file>` with `"profile": "fast"`,
on datasets it generates itself, and reads `profile.json` and `report.html`.

**Synthetic datasets, each generated from a fixed seed into
`verify/artifacts/data/`, about 1,500 customers each:**

| Dataset | Built so that | The right conclusion |
|---|---|---|
| `signal` | churn depends on `support_tickets` and mean transaction amount | clear lift |
| `noise` | churn is a 9% coin flip, independent of everything | no lift |
| `leak` | as `signal`, plus `cancellation_date` filled only where churned | the column is excluded and listed |
| `fanout` | 30 transactions per customer, spending unrelated to churn | 1,500 rows after the join; no lift |
| `keytypes` | ids `00123` as text in one table, `123` as integer in the other | the mismatch is reported; no silent zeros |

**Checks:**

| Check id | Catches | Dataset | Asserts |
|---|---|---|---|
| `data.rows_reconcile` | F3 | `fanout` | joined rows in `profile.json` equal the number of customers, counted by the gate |
| `data.unmatched_reported` | F4 | `keytypes` | the tool either matches every id or stops with the named error; it never reports more than a handful of customers with no transactions |
| `leak.excluded` | F2 | `leak` | `cancellation_date` is listed in `warnings.leakage` and absent from the features used |
| `model.signal_found` | — (`why=`: proves the tool can find signal at all, so "no lift" elsewhere means something) | `signal` | headline lift inside the measured band |
| `model.noise_flat` | F1, F5 | `noise` | headline lift inside a band around zero |
| `model.headline_is_holdout` | F5 | `noise` | the headline equals the holdout score in `profile.json`, and is not the maximum of the cross-validation scores |
| `model.metric_is_auc` | F6 | `noise` | headline metric is named `roc_auc`, baseline is 0.5, and the headline is not within 0.02 of the majority-class share |
| `model.permutation` (slow) | F1 | `noise` | with `"profile": "full"` on 400 customers, the permutation p-value is above 0.05 |
| `report.matches_json` | — (`why=`: a report that disagrees with its own data makes every other check meaningless to the reader) | `signal` | every number shown in `report.html` equals the value in `profile.json` |
| `report.sections` | — (`why=`: a blank section looks like a result) | `signal` | each required section id is present and non-empty; no `NaN` or `inf` anywhere |

*Why this shape: F1 and F5 are both caught by the noise dataset, because a
tool that leaks or picks its best fold finds "signal" in a coin flip. F3 and
F4 are caught by reconciliation, not by scores. The only check that needs the
full profile is marked slow, so the per-edit run stays in seconds.*

Requirements for the gate:

- **Built on `gatekit`.** One `@gate.check(...)` per row above.
- **Never assert a score on the real `data/` files.** The gate may run the
  tool on them once, in a slow check, to reconcile row counts only.
- **Scores are bands, and the bands are measured.** For `model.signal_found`
  and `model.noise_flat`: run the good fixture over five data seeds, take the
  observed range of lift, add a margin, confirm each broken fixture lands
  outside it on every seed, and write the ranges beside the band. Verify
  against the real measurements in this session; do not reuse numbers from
  this brief.
- **Deterministic.** `random_state` fixed in every dataset generator and
  passed to the tool through the config; `n_jobs = 1` and
  `OMP_NUM_THREADS=1` for gate runs. Record every score with the band helpers.
- **Fast.** The per-edit run uses `"profile": "fast"` and skips
  `model.permutation`. Start from the timing in Phase 0 step 5 and keep the
  per-edit run inside the budget `doctor` reports. Run the tool once per
  dataset in setup and let the checks read the outputs; do not rerun it per check.
- **Binary.** Exit 0 = pass, non-zero = fail. No warnings tier.
- **Specific failure messages**, e.g. `"lift on the noise dataset is 0.31,
  expected between -0.06 and 0.06: a fitted step has seen the holdout rows, or
  the headline is the best fold rather than the holdout"`.
- **Distinguishes harness failure from deliverable failure.** scikit-learn
  missing, or `verify/artifacts/` not writable → "HARNESS ERROR — this is not
  a deliverable problem", exit 3, and do NOT blame the code. The tool exiting
  non-zero is a deliverable failure.
- **Writes only to `verify/artifacts/`**: the datasets, the configs, and the
  tool's outputs for each gate run.

**Standard layout — do not deviate:** the gate lives at `verify/smoke_test.py`,
takes the deliverable path (`app`) as its argument, supports `--selftest`,
`--list`, `--only`, `--fast` and `--json`, and writes to `verify/artifacts/`.

**Then prove the gate works.** Register fixtures and run `--selftest`:

- a known-GOOD fixture: a small, correct implementation of the command-line
  contract (one file, logistic regression only is enough)
- `F1`: the scaler is fitted on all rows before the split
- `F2`: the leak check is removed
- `F3`: the aggregation step is removed
- `F4`: ids are compared without normalising their type
- `F5`: the headline is `max(cv_scores)`
- `F6`: the headline is accuracy
- each broken fixture must fail **on a check that names its failure mode**,
  and the good fixture must give identical values on both self-test runs

Run the self-test. **A gate you have not watched fail is not a gate.** Do not
proceed until it discriminates correctly for all six.

---

## Phase 2 — Write the design the other stages build from

### `spec.md` — the contract
- **The methodology**, restated so that leakage is decidable from the text:
  the order of operations (aggregate → join → assert unique `customer_id` →
  stratified holdout split → everything fitted on the 75% only → 5-fold
  selection inside the 75% → refit on the 75% → score once on the 25%).
- **Interface contract:** the config file keys (`customers`, `transactions`,
  `target`, `out_dir`, `profile`, `seed`); the exit codes; the full schema of
  `profile.json` (`data.rows_customers`, `data.rows_joined`,
  `data.customers_without_transactions`, `headline.metric`, `headline.score`,
  `headline.baseline`, `headline.lift`, `cv.scores`, `models[]`,
  `warnings.leakage[]`, ...); the section ids in `report.html`
  (`#data-summary`, `#headline`, `#models`, `#features`, `#warnings`).
- **The leak rule**, precisely: a column is excluded and listed when it is
  missing for more than 95% of one class and less than 5% of the other, or
  when it alone separates the target with AUC above 0.99. Verify the
  thresholds against the real data in Phase 0.
- **Edges:** a non-unique `customer_id` after the join raises `JoinError`;
  mismatched key types are normalised to text and the count of unmatched ids
  is reported; a target with one class raises; fewer than 50 positives in the
  holdout is reported as a warning in the output.
- **Open:** how features are engineered from transactions beyond count, sum
  and mean; the report's styling.

### `plan/test-plan.md` — what the test suite must prove
- `tests/test_skeleton.py` — the package imports; `python -m app.cli --help` exits 0.
- `tests/test_types.py` — each table loads with the dtypes the spec gives;
  dates parse; a malformed date raises rather than becoming missing.
- `tests/test_load.py` — aggregation gives one row per customer; a
  duplicate id raises `JoinError` (`test_f3_...`); text and integer ids match
  after normalisation and the unmatched count is right (`test_f4_...`).
- `tests/test_split.py` — the holdout and the training rows are disjoint; the
  holdout is 25% and stratified; folds partition the training rows; the same
  seed gives the same split.
- `tests/test_metrics.py` — AUC, baseline and lift against hand-worked values
  on eight-element arrays; the headline metric is AUC, not accuracy (`test_f6_...`).
- `tests/test_model.py` — a recording fake estimator proves no fitted step
  ever receives a holdout row (`test_f1_...`); the headline equals the
  holdout score, not the best fold (`test_f5_...`); shuffling the target
  removes the lift on a small planted-signal table.
- `tests/test_model_families.py` — each model family runs behind the same
  interface and returns scores in [0, 1] on a small planted-signal table.
- `tests/test_leakage.py` — the leak rule on crafted columns (`test_f2_...`),
  including a column that is merely predictive and must NOT be flagged.
- `tests/test_profile_schema.py` — `profile.json` has every key in the spec,
  with the right types, and no `NaN`.
- `tests/test_report.py` — every number in the HTML equals the JSON; each
  section is present and non-empty.
- `tests/test_readme.py` — every command the README tells a user to run names
  a file that exists.
- Fixtures: `tests/fixtures/customers_small.csv` and
  `transactions_small.csv`, 60 customers cut from the real shape, plus the
  crafted tables above. The suite runs on tiny data in well under a minute.
- Not tested here: whether the report reads well, and whether the chosen
  features are sensible for the business. A human judges those.

### `plan/tasks.json` — the build, cut into verifiable tasks
Deliverable: `app`. Expected shape (adjust to what Phase 0 shows):

| Task | Tier | Why that tier | Acceptance |
|---|---|---|---|
| T1 package skeleton, CLI stub, `requirements.txt` | support | one obvious right answer | `tests/test_skeleton.py` |
| T2 load and type both tables | routine | clear contract from Phase 0 | `tests/test_types.py` |
| T3 aggregate and join | complex | carries F3 and F4 | `data.rows_reconcile`, `data.unmatched_reported`, `tests/test_load.py` |
| T4 holdout split and folds | complex | decides which rows every number is computed on | `tests/test_split.py` |
| T5 metrics, baseline, lift | complex | carries F6; exact arithmetic | `model.metric_is_auc`, `tests/test_metrics.py` |
| T6 fit, select, score | complex | carries F1 and F5 | `model.signal_found`, `model.noise_flat`, `model.headline_is_holdout`, `tests/test_model.py` |
| T7 leak detection | complex | carries F2 | `leak.excluded`, `tests/test_leakage.py` |
| T8 random forest and gradient boosting behind the T6 interface | routine | one concern behind an existing interface | `tests/test_model_families.py` |
| T9 permutation test and the full profile | complex | touches the headline's validity | `model.permutation` |
| T10 `profile.json` writer | routine | schema is given | `tests/test_profile_schema.py` |
| T11 `report.html` | routine | clear contract, section ids given | `report.matches_json`, `report.sections`, `tests/test_report.py` |
| T12 README with run instructions | support | prose from known facts | `tests/test_readme.py` |

*Why this split: data handling is built and verified before any model exists.
Every task that decides which rows a number is computed on starts on the
strongest coding model. Adding model families and rendering the report sit
behind interfaces that already exist by then, so they start a tier down. Each
gate check and each test file is owned by exactly one task.*

### `CLAUDE.md` — always-loaded conventions
- The definition of done, stated as the literal gate command and test command.
- The methodology in five lines, and the sentence: "the headline is computed
  only on rows no fitted step has seen".
- The `profile.json` schema, as a table.
- The failure-mode matrix (paste the output of `--matrix`).
- The environment facts from Phase 0: interpreter path, library versions,
  seed policy, `n_jobs` and thread settings.
- Guardrails: no secrets in code, no editing the harness, no git, scope of
  writes, no network at run time, new dependencies pinned in `requirements.txt`.
- An autonomy clause: work through gate failures independently; only stop if the
  same failure repeats 3 times or a dependency is unreachable.

### A skill — the reusable procedure
At `.claude/skills/churn-profiler-build/SKILL.md`: the steps to build a
tabular profiling tool of this kind, in order, with a "common failures and
their real causes" table (scaler fitted before the split; pipeline refitted
on all rows before scoring; id column left in the features; ids read as
floats; `n_jobs=-1` making a score move between runs).

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

1. `--selftest` passes: the gate discriminates good from broken for all six
   named failure modes, each caught by a check that names it, and the good
   fixture gives identical values on both runs.
2. For `model.signal_found` and `model.noise_flat` you have reported the
   measured range of lift over five seeds for the good fixture and for each
   broken one, and the gap between them.
3. The hook logic is proven **by direct invocation** with this project's gate —
   pipe a simulated tool-use JSON payload into each hook script on stdin, with
   `LOOP_STAGE=build` set for that command, and confirm:
   - `gate_hook.py`: exit 2 with a useful message while `app` does not exist;
     exit 0 with a "HARNESS ERROR" message (not a code complaint) when
     `verify/artifacts/` is temporarily made unwritable or scikit-learn is hidden.
   - `guard.py`: exit 2 for a write to `verify/smoke_test.py`; exit 0 for a
     write to `app/model.py`.

   **Important:** do not claim you saw the gate hook fire on its own. In this
   session it is switched off on purpose (harness stage), so it CANNOT fire
   here. State clearly in your final report that the user must run the
   live-fire test themselves, in a fresh session.
4. Every absolute path in the harness has been verified to exist and run.
5. `A:\envs\churn-profiler\Scripts\python.exe loop/run_loop.py doctor` is
   clean, including its gate timing line and no determinism failure, and you
   have pasted the output of `... loop/run_loop.py build --dry-run` so I can
   check the routing.
6. Report: the exact gate command, the interpreter path and library versions,
   the failure-mode matrix, the bands and how they were measured, the task
   table (id, tier, why), the hook status (including the live-fire requirement
   above), anything in Phase 0 that contradicted this brief, and every place
   where the data argues against the methodology as written.

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
