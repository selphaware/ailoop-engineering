# BOOTSTRAP — generate a build-loop harness for this project

> **This is a worked EXAMPLE**, not a template to run as-is. It shows how
> specific to be when filling in the project section. Note that this project is
> a *different shape* to a static dashboard — it has a server — which changes
> what the gate has to do.
>
> Annotations in `>` blocks explain why each answer is written that way. Delete
> them in your real version.

You are going to build a **harness**: the deterministic scaffolding that lets an
agent build this project autonomously and verifiably. You are NOT building the
application yet. You are building the thing that will judge the application.

Read this whole file before doing anything.

---

## The project

**What it is:**
> A Python FastAPI service that reads a sales pipeline export (CSV) into SQLite
> and exposes it over a small JSON API, plus a single-page HTML/JS dashboard
> served from the same app that visualises the pipeline.

*Why this is a good answer: it names the language, the framework, the storage,
and the fact that there are two halves (API + frontend). The agent now knows it
must verify both.*

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

**What "working" looks like to a user:**
> They run the app, open `http://localhost:8000`, and see: a funnel chart of deal
> count and value by stage; KPI cards for total pipeline value, weighted value,
> deal count, and average deal size; a sortable table of deals; and working
> filters for stage, region, and owner that update both the chart and the table.
> The numbers reconcile with the CSV — total pipeline value equals the sum of
> `value_gbp` for non-closed deals.

*Why this is a good answer: it describes what is **on screen**, and it names a
reconciliation rule. That last sentence gives the gate something objective to
check beyond "there are numbers".*

**What "broken but passes tests" looks like:**
> 1. The API returns `200 OK` with `[]` because the CSV loader silently failed on
>    a date parse, so the dashboard renders with every KPI showing `£0` and an
>    empty table — and nothing errors.
> 2. The filters render as dropdowns but don't actually filter — clicking a
>    region changes nothing, and the page looks perfectly fine.
> 3. The weighted value is computed but always equals the unweighted total
>    because the stage-probability lookup silently returns 1.0 for unknown keys.

*Why this is a good answer: three specific, plausible silent failures. Each one
would pass a build, pass a lint, and probably pass a naive "does the endpoint
return 200" test. This paragraph is what forces the gate to (a) assert non-zero
row counts, (b) actually click a filter and compare before/after, and (c) check
that weighted ≠ unweighted. Without this, the gate would be useless.*

**Environment:**
> - Python interpreter: `A:\envs\pipeline\Scripts\python.exe`
> - Node/npm needed? No — vanilla JS, Chart.js from CDN.
> - Needs: `fastapi`, `uvicorn`, `playwright` (for the gate). Port 8000 free.

---

## Phase 0 — Discover the environment. Do not skip. Do not assume.

Assumptions about the environment are the single biggest source of wasted
iterations. Establish facts first, and **write them down** in the harness.

1. **Find the real Python interpreter.**
   - On Windows, bare `python` may resolve to the Microsoft Store alias stub at
     `...\WindowsApps\python.exe`, which is a 0-byte shim that cannot execute.
     Detect and reject it explicitly.
   - Report the absolute path you will use. Verify with `<path> --version`.
2. **Find the Node/npm toolchain** if the project needs one. Same rule: absolute
   path, verified by running it.
3. **Check the project location.** Resolve the working directory to an absolute
   path. If it is a mapped network drive or UNC path, say so — headless browsers
   and `file://` URIs behave differently there.
4. **Inspect the real data source.** Read the actual CSV header and a few rows.
   Report the true column names, types, date formats, and row count. If they
   differ from the brief above, say so — the file is the truth.
5. **Check the port is free** and that `fastapi`/`uvicorn` are installed.
6. **Report all of the above back to me before writing any files.**

---

## Phase 1 — Design the gate FIRST

The gate is the harness. Everything else is support. Build it before anything else.

**The gate must catch the three failure modes named above**, not merely confirm
the code runs.

For this project the gate must:

1. **Start the app** (uvicorn on a test port) and wait for it to be ready.
2. **Hit the API directly:**
   - `GET /api/deals` returns ≥ 1 row (catches the silent-empty failure)
   - `GET /api/deals?stage=Proposal` returns **fewer** rows than unfiltered, and
     every returned row has `stage == "Proposal"` (catches dead filters at the
     API layer)
   - `GET /api/summary` returns a weighted value that is **strictly less than**
     the unweighted total (catches the probability-lookup bug)
   - totals reconcile against a direct read of the CSV
3. **Load the dashboard in headless Chromium:**
   - KPI cards are populated and not `£0`
   - the table has ≥ 1 row
   - a chart canvas has actually drawn pixels
   - **click a filter, then assert the table row count changed** (catches dead
     filters at the UI layer)
   - no console errors
4. **Shut the app down cleanly**, even on failure.

Requirements for the gate:

- **Binary.** Exit 0 = pass, non-zero = fail. No warnings tier.
- **Specific failure messages.** Not "verification failed" but
  `"filter test: /api/deals?stage=Proposal returned 2000 rows, same as
  unfiltered — filter is not applied"`. The message is fed back to the agent;
  a vague message costs an iteration.
- **Fast.** It runs on every edit. Seconds, not minutes.
- **Thresholds derived from the real data.** Read the CSV first. If it has 6
  stages, don't hard-code 5.
- **Distinguishes harness failure from deliverable failure.** Port already in
  use, missing dependency, wrong interpreter → say "HARNESS ERROR — this is not
  a deliverable problem" and do NOT blame the code.

**Then prove the gate works.** Add a `--selftest` mode that:
- builds a known-GOOD fixture app and asserts the gate passes it
- builds a known-BROKEN fixture (returns `[]`, and a dead filter) and asserts the
  gate fails it, naming the right reason
- reports clearly if the two disagree

Run the self-test. **A gate you have not watched fail is not a gate.** Do not
proceed until it discriminates correctly.

---

## Phase 2 — Build the rest of the harness

### `CLAUDE.md` — always-loaded conventions
- The definition of done, stated as the literal gate command.
- The contract the deliverable must satisfy, as a table.
- The environment facts from Phase 0 (absolute interpreter path, port, deps).
- Guardrails: no secrets in code, no editing the harness, scope of writes.
- An autonomy clause: work through gate failures independently; only stop if the
  same failure repeats 3 times or a dependency is unreachable.

### The verification hook — the inner loop
- A `PostToolUse` hook matching `Write|Edit` that runs the gate.
- Exit 2 on failure, with the gate output on stderr — this feeds the failure back
  to the model mid-run, so it corrects itself before it can declare done.
- Exit 0 for harness errors, so a broken environment never gets blamed on the code.
- **Pin the interpreter with an absolute path in the hook command.** A bare
  `python` that resolves to a stub makes the hook die silently.
- Python stdlib only — no bash/jq dependency.
- Because this gate starts a server, make sure it can't leave orphan processes.

### A skill — the reusable procedure
The steps to build a FastAPI + static frontend of this kind, in order, with a
"common failures and their real causes" table.

### `settings.json`
- Register the hook with the absolute interpreter path.
- Allowlist the tools needed to run unattended.
- **Deny edits to the gate and the harness directory.** A self-verifying agent
  that can edit its own judge will eventually edit its own judge.

### The task spec (`spec.md`)
Concrete: the real column names from Phase 0, the exact endpoints, the KPI
definitions (including the stage-probability weights), the chart types, and the
reconciliation rule.

### An outer loop script (optional)
Headless run → gate → resume with failure → escalate after N iterations. Only
build this once the interactive loop is proven.

---

## Phase 3 — Prove the whole thing

Before you tell me it is done:

1. `--selftest` passes (gate discriminates good from broken, for all three
   named failure modes).
2. The hook fires: deliberately make `/api/deals` return `[]`, confirm the hook
   blocks the write with a useful message, then restore.
3. Every absolute path in the harness has been verified to exist and run.
4. No orphan uvicorn processes are left running after a gate run.
5. Report: the gate command, the interpreter, the hook status, and anything you
   discovered in Phase 0 that contradicted this brief.

Then stop. Do not build the application. I will start that in a fresh session.

---

## Rules

- **Verify, don't assert.** Every claim about the environment must come from a
  command you ran, not from what is usually true.
- **Tell me when this brief is wrong.** If Phase 0 contradicts something above,
  say so plainly rather than working around it silently.
- Prefer fewer moving parts. Every dependency is something that can drift.
