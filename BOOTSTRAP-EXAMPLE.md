# BOOTSTRAP — design this build and build its judge

> **This is a worked EXAMPLE**, not a template to run as-is. It shows how
> specific to be when filling in the project section, and how Phases 0–3 are
> adapted to one project's shape. This project has a server, which changes
> what the gate has to do.
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

---

## The project

**What it is:**
> A Python FastAPI service that reads a sales pipeline export (CSV) into SQLite
> and exposes it over a small JSON API, plus a single-page HTML/JS dashboard
> served from the same app that visualises the pipeline.

*Why this is a good answer: it names the language, the framework, the storage,
and the fact that there are two halves (API + frontend). The agent now knows it
must verify both, and that the task plan has a natural seam between them.*

**Data source:**
> `data/pipeline_export.csv` — a monthly export, roughly 2,000 rows.
> Columns (verify against the real file, don't trust this list):
> `deal_id, client_name, sector, region, owner, stage, value_gbp,
> created_date, expected_close_date, last_activity_date`.
> `stage` is one of: Prospect, Qualified, Proposal, Negotiation, Closed Won,
> Closed Lost. No auth, no network calls.

*Why this is a good answer: it gives the real column names AND explicitly tells
the agent to verify them rather than trust the brief. It also names the
categorical values, which the gate will need to check filters work.*

**The deliverable:**
> - `app/main.py` — FastAPI app with these endpoints:
>   - `GET /api/deals` — all deals, filterable by `stage`, `region`, `owner`
>   - `GET /api/summary` — totals by stage, by region, and overall weighted value
>   - `GET /` — serves the dashboard
> - `app/static/index.html` — the dashboard (self-contained JS, Chart.js from CDN)
> - `app/load.py` — loads the CSV into SQLite
>
> The gate takes one argument: the `app` folder.

*Why this is a good answer: exact paths, and it settles the gate's single
argument. With more than one file, the gate judges the folder.*

**What "working" looks like to a user:**
> They run the app, open `http://localhost:8000`, and see: a funnel chart of deal
> count and value by stage; KPI cards for total pipeline value, weighted value,
> deal count, and average deal size; a sortable table of deals; and working
> filters for stage, region, and owner that update both the chart and the table.
> The numbers reconcile with the CSV — total pipeline value equals the sum of
> `value_gbp` for non-closed deals.

*Why this is a good answer: it describes what is **on screen**, and it names a
reconciliation rule. That last sentence gives the gate and the test suite
something objective to check beyond "there are numbers".*

**What "broken but passes tests" looks like:**
> - **F1.** The API returns `200 OK` with `[]` because the CSV loader silently
>   failed on a date parse, so the dashboard renders with every KPI showing `£0`
>   and an empty table — and nothing errors.
> - **F2.** The filters render as dropdowns but don't actually filter — clicking
>   a region changes nothing, and the page looks perfectly fine.
> - **F3.** The weighted value is computed but always equals the unweighted
>   total because the stage-probability lookup silently returns 1.0 for
>   unknown keys.

*Why this is a good answer: three specific, plausible silent failures, each
with an id. Each one would pass a build, pass a lint, and probably pass a
naive "does the endpoint return 200" test. This list is what forces the gate
to (a) assert non-zero row counts, (b) actually click a filter and compare
before/after, and (c) check that weighted ≠ unweighted. The ids follow each
failure into the gate's checks, the regression tests, the task tiers and the
final review.*

**Environment:**
> - Python interpreter: `A:\envs\pipeline\Scripts\python.exe`
>   **(already created by me before this session — see below)**
> - Node/npm needed? No — vanilla JS, Chart.js from CDN.
> - Already installed (gate dependencies): `pytest`, `playwright` + Chromium
> - You will need to install (app runtime): `fastapi`, `uvicorn` — install them
>   into the interpreter above, not a new venv.
> - Port 8000 must be free. The gate uses a different, free test port.

*Why this is a good answer: it separates **gate dependencies** from **app
dependencies**. The venv, pytest and Playwright must already exist before this
session starts, because the gate self-tests itself using that interpreter — an
agent that creates its own verification environment has nothing trustworthy to
verify with. App runtime packages are different: the builders discover and
install those as they build, into the same venv.*

---

The "broken but passes tests" lines are the most important thing on this page.
**They define the gate, and the gate is the whole system.**

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
   - Report the absolute path you will use. Verify with
     `A:\envs\pipeline\Scripts\python.exe --version`.
   - Confirm it is the same interpreter the hooks in `.claude/settings.json`
     are registered with. If not, stop and say so.
2. **Find the Node/npm toolchain** — not needed here; confirm nothing in the
   project requires it.
3. **Check the project location.** Resolve the working directory to an absolute
   path. If it is a mapped network drive or UNC path, say so — headless browsers
   and `file://` URIs behave differently there.
4. **Inspect the real data source.** Read the actual CSV header and a few rows.
   Report the true column names, types, date formats, the distinct `stage`,
   `region` and `owner` values, and the row count. If they differ from the
   brief above, say so — the file is the truth.
5. **Check the port is free** and whether `fastapi`/`uvicorn` are installed.
6. **Check the kit.** Run `A:\envs\pipeline\Scripts\python.exe loop/run_loop.py doctor`
   and read `verify/gatekit.py` and `loop/loop.json`. Report anything doctor flags.
7. **Report all of the above back to me before writing any files.**

*Adapted from the template: step 4 is file-shaped (header + sample rows +
distinct values, because the filters depend on them), and step 5 is added
because this project has a server.*

---

## Phase 1 — Design the gate FIRST

The gate is the harness. Everything else is support. Build it before anything else.

**The gate must catch the three failure modes named above**, not merely confirm
the code runs.

For this project the gate must:

1. **Setup: start the app** (uvicorn on a free test port, against a copy of
   the fixture CSV) and wait for it to be ready. A port that cannot be bound
   is a `ctx.harness_error`. An app that will not start is a deliverable failure.
2. **Hit the API directly** — each a separate check:

   | Check id | Catches | Asserts |
   |---|---|---|
   | `api.deals_nonempty` | F1 | `GET /api/deals` returns the same number of rows as the CSV has data lines |
   | `api.filter_stage` | F2 | `GET /api/deals?stage=Proposal` returns **fewer** rows than unfiltered, and every returned row has `stage == "Proposal"` |
   | `api.weighted_below_total` | F3 | `GET /api/summary` returns a weighted value **strictly less than** the unweighted total |
   | `api.total_reconciles` | F1 | total pipeline value equals the sum of `value_gbp` for non-closed deals, computed by the gate from the CSV |

3. **Load the dashboard in headless Chromium:**

   | Check id | Catches | Asserts |
   |---|---|---|
   | `ui.kpis_populated` | F1 | KPI cards are populated and not `£0` |
   | `ui.table_rows` | F1 | the table has ≥ 1 row |
   | `ui.chart_drawn` | F1 | a chart canvas has actually drawn pixels |
   | `ui.filter_changes_table` | F2 | **click a filter, then assert the table row count changed** |
   | `ui.no_console_errors` | — (`why=`: a console error means a check above may be reading a half-rendered page) | no console errors |

4. **Teardown: shut the app down cleanly**, even on failure. No orphan processes.

*Why this shape: every named failure maps to at least one check, at both the
API and the UI layer where it can occur. The checks are small and named so the
task plan can hand `api.*` to the backend tasks and `ui.*` to the frontend
tasks. The one check that catches no named failure says why it exists.*

Requirements for the gate:

- **Built on `gatekit`.** One `@gate.check(...)` per row above.
- **Binary.** Exit 0 = pass, non-zero = fail. No warnings tier.
- **Specific failure messages.** Not "verification failed" but
  `"filter test: /api/deals?stage=Proposal returned 2000 rows, same as
  unfiltered — filter is not applied"`. The message is fed back to the builder;
  a vague message costs an iteration.
- **Fast.** It runs on every edit. Seconds, not minutes. Start the server once
  in setup, not once per check.
- **Thresholds derived from the real data.** Read the CSV first. If it has 6
  stages, don't hard-code 5. If `Proposal` has no rows in the real file, pick a
  stage that does and say so.
- **Reconciles independently.** The gate reads the CSV itself.
- **Offline and deterministic.** Chart.js comes from a CDN in the real app; the
  gate must not depend on the network, so serve a vendored copy from
  `verify/fixtures/` by route interception.
- **Distinguishes harness failure from deliverable failure.** Port already in
  use, missing dependency, wrong interpreter → "HARNESS ERROR — this is not
  a deliverable problem", exit 3, and do NOT blame the code.
- **Writes only to `verify/artifacts/`** (screenshots, the test SQLite file).

**Standard layout — do not deviate:** the gate lives at `verify/smoke_test.py`,
takes the deliverable path (`app`) as its argument, supports `--selftest`,
`--list`, `--only` and `--json`, and writes any screenshots to
`verify/artifacts/`. (Yes, even though this gate starts a server — the
entrypoint stays the same so the same driver works on every project.)

**Then prove the gate works.** Register fixtures and run `--selftest`:

- a known-GOOD fixture app that passes every check
- `F1`: a fixture whose loader returns nothing (API answers `[]`)
- `F2`: a fixture whose filters are accepted and ignored
- `F3`: a fixture whose weighted value equals the unweighted total
- each broken fixture must fail **on a check that names its failure mode**

Run the self-test. **A gate you have not watched fail is not a gate.** Do not
proceed until it discriminates correctly for all three.

---

## Phase 2 — Write the design the other stages build from

### `spec.md` — the contract
Concrete: the real column names from Phase 0, the exact endpoints with their
query parameters and response shapes, the KPI definitions (including the
stage-probability weights as a table, and what happens for an unknown stage:
it raises, it never defaults), the chart types, and the reconciliation rule.
**Interface contract:** `app.load.load_csv(csv_path, db_path) -> int` (rows
loaded; raises `ValueError` naming the line on a bad date), the JSON shape of
`/api/deals` and `/api/summary`, and the element ids the dashboard exposes
(`#kpi-total`, `#deals-table`, `#filter-stage`, ...), so the test author and
the frontend builder agree without seeing each other's work.

### `plan/test-plan.md` — what the test suite must prove
- `tests/test_skeleton.py` — the package imports and exposes the entry points
  the spec names.
- `tests/test_load.py` — loader row count equals the CSV; a malformed date
  raises instead of dropping the row (`test_f1_...`).
- `tests/test_api_deals.py` — unfiltered count; each filter narrows and only
  returns matching rows (`test_f2_...`); combined filters.
- `tests/test_api_summary.py` — totals reconcile with a sum computed in the
  test from the fixture CSV; weighted < unweighted (`test_f3_...`); unknown
  stage raises.
- `tests/test_readme.py` — every command the README tells a user to run names
  a file that exists.
- Fixtures: `tests/fixtures/pipeline_small.csv`, 30 rows cut from the real
  export covering every stage and region, plus one row with a bad date.
- Not tested here: how the dashboard looks. The gate checks it renders and
  responds; a human judges whether it reads well.

### `plan/tasks.json` — the build, cut into verifiable tasks
Deliverable: `app`. Expected shape (adjust to what Phase 0 shows):

| Task | Tier | Why that tier | Acceptance |
|---|---|---|---|
| T1 package skeleton, `requirements.txt` | support | one obvious right answer | `tests/test_skeleton.py` |
| T2 CSV → SQLite loader | complex | carries F1; messy real dates | `tests/test_load.py` |
| T3 `GET /api/deals` with filters | complex | carries F2 | `api.deals_nonempty`, `api.filter_stage`, `tests/test_api_deals.py` |
| T4 `GET /api/summary` | complex | carries F3 and the reconciliation rule | `api.weighted_below_total`, `api.total_reconciles`, `tests/test_api_summary.py` |
| T5 static dashboard shell: layout, KPI cards, table | routine | clear contract, element ids given | `ui.kpis_populated`, `ui.table_rows`, `ui.no_console_errors` |
| T6 funnel chart | routine | one component, pattern in the skill | `ui.chart_drawn` |
| T7 filter controls wired to API | complex | carries F2 at the UI layer | `ui.filter_changes_table` |
| T8 README with run instructions | support | prose from known facts | `tests/test_readme.py` (commands named in the README exist) |

*Why this split: the three tasks that carry a named failure start on the
strongest coding model. The frontend shell and chart have a clear contract, so
they start a tier down and escalate only if they fail. Every gate check and
every test file is owned by exactly one task.*

### `CLAUDE.md` — always-loaded conventions
- The definition of done, stated as the literal gate command and test command.
- The contract the deliverable must satisfy, as a table.
- The failure-mode matrix (paste the output of `--matrix`).
- The environment facts from Phase 0 (absolute interpreter path, port, deps).
- Guardrails: no secrets in code, no editing the harness, no git, scope of writes.
- An autonomy clause: work through gate failures independently; only stop if the
  same failure repeats 3 times or a dependency is unreachable.

### A skill — the reusable procedure
At `.claude/skills/pipeline-build/SKILL.md`: the steps to build a FastAPI +
static frontend of this kind, in order, with a "common failures and their real
causes" table (chart animation still running when the gate reads the canvas;
uvicorn left running on the port; date formats mixed within one column).

### Not yours to build
The hooks, `settings.json`, and the outer loop are the kit. They exist. **A
self-verifying agent that can edit its own judge will eventually edit its own
judge**, which is why the judge is locked by a guard, by deny rules, and by a
tamper check in the driver that restores any locked file an agent changes.

---

## Phase 3 — Prove the whole thing

Before you tell me it is done:

1. `--selftest` passes: the gate discriminates good from broken for all three
   named failure modes, each caught by a check that names it.
2. The hook logic is proven **by direct invocation** with this project's gate —
   pipe a simulated tool-use JSON payload into each hook script on stdin, with
   `LOOP_STAGE=build` set for that command, and confirm:
   - `gate_hook.py`: exit 2 with a useful message while `app` does not exist;
     exit 0 with a "HARNESS ERROR" message (not a code complaint) when the
     fixture CSV is temporarily renamed.
   - `guard.py`: exit 2 for a write to `verify/smoke_test.py`; exit 0 for a
     write to `app/main.py`.

   **Important:** do not claim you saw the gate hook fire on its own. In this
   session it is switched off on purpose (harness stage), so it CANNOT fire
   here. State clearly in your final report that the user must run the
   live-fire test themselves, in a fresh session.
3. Every absolute path in the harness has been verified to exist and run.
4. No orphan uvicorn processes are left running after a gate run or a self-test.
5. `A:\envs\pipeline\Scripts\python.exe loop/run_loop.py doctor` is clean, and
   you have pasted the output of `... loop/run_loop.py build --dry-run` so I
   can check the routing.
6. Report: the exact gate command, the interpreter path, the failure-mode
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
