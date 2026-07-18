# BOOTSTRAP — generate a build-loop harness for this project

You are going to build a **harness**: the deterministic scaffolding that lets an
agent build this project autonomously and verifiably. You are NOT building the
application yet. You are building the thing that will judge the application.

Read this whole file before doing anything.

---

## The project

<!-- ============================================================
     FILL THIS IN. Be concrete. Vagueness here costs iterations.
     See BOOTSTRAP-EXAMPLE.md for how specific to be.
     ============================================================ -->

**What it is:**
> <e.g. Python FastAPI service + vanilla JS dashboard frontend>

**Data source:**
> <API URL / DB connection / file paths. Include auth method, or state "none".>

**The deliverable:**
> <the artifact(s) that must exist and work, e.g. `dashboard.html`, or
>  `app.py` + `static/index.html`>

**What "working" looks like to a user:**
> <what they would SEE or GET if it worked. Be visual and concrete.>

**What "broken but passes tests" looks like:**
> <the failure mode you fear most — the one that would sail through lint,
>  type checks, and "it built successfully">

**Environment (fill in what you already know):**
> - Python interpreter: <absolute path, e.g. A:\envs\myproj\Scripts\python.exe>
> - Node/npm needed? <yes/no, path if yes>
> - Anything else the project needs: <DB, env vars, ports>

---

The "broken but passes tests" line is the most important thing on this page.
**It defines the gate, and the gate is the whole system.**

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
   and `file://` URIs behave differently there, and it is far cheaper to know now.
4. **Hit the data source once.** Print the raw response. Note the real field
   names, nesting, and types. If it errors, diagnose before proceeding — a 403
   is as likely to be a missing `User-Agent` header as a firewall.
5. **Report all of the above back to me before writing any files.**

---

## Phase 1 — Design the gate FIRST

The gate is the harness. Everything else is support. Build it before anything else.

**The gate must catch the failure mode named above**, not merely confirm the code
runs. Lint, type checks, and "it built successfully" do not catch a page that
renders blank, an API that returns `[]`, or a report with every field empty.

Pick the verification method that actually observes the deliverable:

| Deliverable | Gate must |
|---|---|
| HTML/JS frontend | load it in headless Chromium and assert real data is on screen |
| HTTP API | start it, make real requests, assert status + response shape |
| CLI tool | run it on fixture input, assert stdout/exit code |
| Data pipeline | run it, assert output row counts, schema, and value sanity |

Requirements for the gate:

- **Binary.** Exit 0 = pass, non-zero = fail. No warnings tier, no partial credit.
- **Specific failure messages.** Not "verification failed" but "0 populated KPI
  values (need >= 3) — check `.kpi-card .kpi-value` is non-empty". The message is
  fed back to the agent; a vague message costs an iteration.
- **Fast.** It runs on every edit. Seconds, not minutes.
- **Thresholds derived from the real data**, not invented. If the source only
  supports 2 metrics, a gate demanding 3 can never pass and the agent will thrash
  forever inventing filler. Check the actual data before setting numbers.
- **Distinguishes harness failure from deliverable failure.** If a dependency is
  missing or the interpreter is wrong, say "HARNESS ERROR — this is not a
  deliverable problem" and do NOT blame the code.

**Then prove the gate works.** Add a `--selftest` mode that:
- writes a known-GOOD artifact and asserts the gate passes it
- writes a known-BROKEN artifact and asserts the gate fails it
- runs both from a local temp dir and from the project dir, and reports if they
  disagree

Run the self-test. **A gate you have not watched fail is not a gate.** Do not
proceed until it discriminates correctly.

---

## Phase 2 — Build the rest of the harness

### `CLAUDE.md` — always-loaded conventions
- The definition of done, stated as the literal gate command.
- The contract the deliverable must satisfy, as a table.
- The environment facts from Phase 0 (absolute interpreter paths).
- Guardrails: no secrets in code, no editing the harness, scope of writes.
- An autonomy clause: work through gate failures independently; only stop if the
  same failure repeats 3 times or an external dependency is unreachable.

### The verification hook — the inner loop
- A `PostToolUse` hook matching `Write|Edit` that runs the gate.
- Exit 2 on failure, with the gate output on stderr — this feeds the failure back
  to the model mid-run, so it corrects itself before it can declare done.
- Exit 0 for harness errors, so a broken environment never gets blamed on the code.
- **Pin the interpreter with an absolute path in the hook command.** A bare
  `python` that resolves to a stub makes the hook die silently — no error, just
  no verification, and you will not notice.
- Write the hook in a language that needs no extra tooling (Python stdlib is
  ideal; avoid bash/jq dependencies on Windows).

### A skill — the reusable procedure
The steps to build this kind of deliverable, in order, with a
"common failures and their real causes" table.

### `settings.json`
- Register the hook with the absolute interpreter path.
- Allowlist the tools needed to run unattended.
- **Deny edits to the gate and the harness directory.** A self-verifying agent
  that can edit its own judge will eventually edit its own judge.

### The task spec (`spec.md`)
Concrete, not a template. Real endpoints, real field names from Phase 0, the
actual metrics and views wanted, and any known traps in the data (scale
mismatches, gaps, nulls).

### An outer loop script (optional)
Headless run → gate → resume with failure → escalate after N iterations. Only
build this once the interactive loop is proven.

---

## Phase 3 — Prove the whole thing

Before you tell me it is done:

1. `--selftest` passes (gate discriminates good from broken).
2. The hook fires: deliberately write a broken deliverable, confirm the hook
   blocks it with exit 2 and a useful message, then restore.
3. Every absolute path in the harness has been verified to exist and run.
4. Report: the gate command, the interpreter, the hook status, and anything you
   discovered in Phase 0 that contradicted this brief.

Then stop. Do not build the application. I will start that in a fresh session.

---

## Rules

- **Verify, don't assert.** Every claim about the environment must come from a
  command you ran, not from what is usually true.
- **Tell me when this brief is wrong.** If Phase 0 contradicts something above,
  say so plainly rather than working around it silently.
- Prefer fewer moving parts. Every dependency is something that can drift.
