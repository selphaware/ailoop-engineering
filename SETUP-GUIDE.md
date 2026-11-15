# Loop Engineering — Setup Guide

How to set up an autonomous, model-routed build loop for any Python +
HTML/JS project, on Windows.

**The idea:** you don't ask an agent to build something and hope. You define
"done" as a program that returns pass/fail, then let agents iterate against it
until it passes. The program that judges is called the **gate**. The gate plus
its supporting files is called the **harness**. A small script, the
**driver**, runs each stage of the work on the model that stage calls for and
re-judges every result itself.

| Stage | Command | Model | You |
|---|---|---|---|
| Brief | (claude.ai Project, or by hand) | Fable | answer the interview |
| Harness | `run_loop.py harness` | `fable`, xhigh, interactive | approve Phase 0, review, **commit** |
| Tests | `run_loop.py tests` | `opus` | skim the report, **commit** |
| Build | `run_loop.py build` | per task: `opus` / `sonnet` / `haiku` | nothing, unless it stops |
| Review | `run_loop.py review` | `fable`, read-only | read it, judge, **commit** |

`run_loop.py go` runs tests → build → review in one unattended pass.

You never pick a model by hand. Routing lives in `loop/loop.json`; see
`MODEL-ROUTING.md`.

**Convention:** anything in `<angle brackets>` in this guide — `<project>`,
`<deliverable>`, `<you>` — is a placeholder. Replace it with your real value
before pasting; never paste the brackets themselves. `<py>` always means your
project's interpreter, e.g. `A:\envs\fx-monitor\Scripts\python.exe`.

Worked examples, stratified across three project shapes. **Each column is one
coherent project — read downwards:**

| Placeholder | ① Static dashboard | ② API + frontend | ③ Data pipeline | ④ Modelling tool |
|---|---|---|---|---|
| `<you>` (GitHub owner) | `usman-dev` | `acuity-analytics` | `usman-dev` | `usman-dev` |
| `<project>` (repo + venv name) | `fx-monitor` | `sales-pipeline` | `etl-refresh` | `churn-profiler` |
| `<py>` | `A:\envs\fx-monitor\Scripts\python.exe` | `A:\envs\sales-pipeline\Scripts\python.exe` | `A:\envs\etl-refresh\Scripts\python.exe` | `A:\envs\churn-profiler\Scripts\python.exe` |
| Brief template | `generic\` | `generic\` | `generic\` | `ML\` |
| `<deliverable>` (gate argument) | `dashboard.html` | `app` | `output\monthly_report.csv` | `app` |
| File to break in step 3.4 | `dashboard.html` | `app\static\index.html` | `etl\transform.py` | `app\model.py` |

Note the last two rows **diverge** once the deliverable is more than one file:

- **② API + frontend:** the gate's argument is the app folder (it starts the
  server and verifies API + UI together), but the live-fire test breaks one
  concrete file inside it.
- **③ Data pipeline:** the gate *runs the pipeline, then checks the output* —
  so breaking `output\monthly_report.csv` directly would prove nothing (the gate
  regenerates it). You must break the **code that produces it**. Break the thing
  the gate reads; for pipelines, the gate effectively reads what your code does.
- **④ Modelling tool:** the gate runs the tool on synthetic data it generates
  itself, so there is no data file to break either. Break the modelling code.

---

## Files in this set

| File | What it's for |
|---|---|
| `SETUP-GUIDE.md` | This file. The steps. |
| `MODEL-ROUTING.md` | Which model does what, why, and the one file to edit when models change. |
| `kit/` | The fixed, tested machinery: hooks, driver, gate framework, installer. Copied into each project. Shared by both kinds of project. |
| `generic/BOOTSTRAP-TEMPLATE.md` | The brief for an application. Copy into a new project, fill in the top, hand to the harness stage. |
| `generic/BOOTSTRAP-EXAMPLE.md` | That template filled in for a real project, so you can see what "good" looks like. |
| `generic/PROJECT-INSTRUCTIONS.md` | Instructions for the claude.ai Project that interviews you and writes the bootstrap. |
| `ML/` | The same three files for modelling tools, plus `ML-GATE-PATTERNS.md`. |

**Generic or ML?** If the tool's output is a model, a score or a statistical
conclusion (a profiler, a training pipeline, an evaluation tool), use the
`ML/` files. Otherwise use `generic/`. Every step in this guide is the same
for both; where an ML project differs, the step says so.

---

# Part 1 — One-time machine setup

Do this once. Skip if already done.

### 1.1 Kill the Microsoft Store Python stubs

Windows ships fake `python.exe` shims that break everything silently.

**Settings → Apps → Advanced app settings → App execution aliases →
turn OFF `python.exe` and `python3.exe`.**

### 1.2 Install or update Claude Code

```powershell
irm https://claude.ai/install.ps1 | iex
```
Restart PowerShell, run `claude` once, authenticate in the browser. Already
installed? Update it — the driver needs **2.1.302 or later**:

```powershell
claude update
claude --version
```

### 1.3 Make sure Fable is usable unattended

In an interactive session run `/model fable` once and accept anything it asks.
On some plans Fable bills to usage credits and needs a one-time consent; an
unattended run cannot answer that prompt.

### 1.4 Check you have Python 3.10+

```powershell
A:\envs\py312\python.exe --version
```
Use your own path. Note it down — you'll need it constantly.

### 1.5 Get the kit

```powershell
cd D:\tools
git clone https://github.com/<you>/ailoop-engineering.git
```

Optional but worth two minutes: run the kit's own tests, so you have seen it
work on your machine before you trust it.

```powershell
A:\envs\py312\python.exe -m pip install pytest
A:\envs\py312\python.exe -m pytest D:\tools\ailoop-engineering\kit\tests -q
```

---

# Part 2 — Per-project setup

### 2.1 Create the repo and clone it locally

```powershell
cd D:\sandbox
git clone https://github.com/<you>/<project>.git
cd <project>
```

**Use a local disk.** Not a mapped network drive (`R:\`), not a UNC path.
Headless browsers behave differently on those and it wastes an afternoon.
(No remote yet? `git init` in a new folder works the same.)

### 2.2 Create a virtual environment for this project

**You create this, not Claude Code.**

```powershell
A:\envs\py312\python.exe -m venv A:\envs\<project>
A:\envs\<project>\Scripts\python.exe -m pip install pytest playwright
A:\envs\<project>\Scripts\python.exe -m playwright install chromium
```

Write down the absolute path: `A:\envs\<project>\Scripts\python.exe`. This is `<py>`.
(Put the venv on a local disk too — a venv on a network share adds latency to
every single gate run. Skip Playwright if nothing in the project is judged in
a browser.)

**Install only the gate's dependencies now** (pytest, Playwright + Chromium).
Leave the app's runtime packages — `fastapi`, `pandas`, whatever — for the
agents to install into this same venv as they discover they need them.

> Why you and not the agent: the harness pins this interpreter, and the gate
> self-tests using it. An agent that creates its own verification environment has
> nothing trustworthy to verify with — and when it goes wrong, it goes wrong at
> the exact moment you have least ability to diagnose it.

### 2.3 Install the kit into the project

Run the installer **with the project's interpreter**. Whichever Python runs
it is the one pinned into the hooks.

```powershell
<py> D:\tools\ailoop-engineering\kit\install_kit.py .
```

It copies the hooks, driver and gate framework in, writes
`.claude\settings.json` with `<py>` as an absolute path, and adds the state
folders to `.gitignore`. It is safe to re-run after you update the kit.

### 2.4 Write the bootstrap

Either let the claude.ai Project interview you and produce `BOOTSTRAP.md`, or
copy the template into the project folder as `BOOTSTRAP.md` and complete the
project block at the top: `generic\BOOTSTRAP-TEMPLATE.md` (six fields) for an
application, `ML\BOOTSTRAP-TEMPLATE.md` (seven fields) for a modelling tool.

**Spend real time on this — 15 minutes, not 2.** Especially these lines:

> *What "broken but passes tests" looks like*

Those sentences become your gate, your regression tests and the reviewer's
checklist. They are the single highest-leverage thing you write. Number them
F1, F2, F3. See the `BOOTSTRAP-EXAMPLE.md` beside your template for how
specific to be.

For a modelling tool, give the **methodology** field the same care: what the
headline number is, against which baseline, under which validation scheme.
The gate can prove the tool is not leaking or miscounting. It cannot decide
what "predictable" should mean. That is your call, and it is made here.

### 2.5 Commit, then check

```powershell
git add -A
git commit -m "Add loop kit and bootstrap"
<py> loop\run_loop.py doctor
```

The first time on a machine, also run the live check. It makes one tiny real
call on Haiku and confirms that Claude Code accepts every flag the driver
uses and can run a command unattended:

```powershell
<py> loop\run_loop.py doctor --live
```

If that fails, fix it before going further. Everything unattended depends on it.

---

# Part 3 — Build the harness

### 3.1 Run the harness stage

```powershell
cd D:\sandbox\<project>
<py> loop\run_loop.py harness
```

This opens an interactive Claude Code session on **Fable at xhigh effort**
and hands it `BOOTSTRAP.md`.

> Why Fable here: this stage discovers an unfamiliar environment, designs the
> gate, writes the contract the tests are derived from, and decides which
> model each task deserves. Every later stage inherits its mistakes. It is
> the highest-leverage place to spend the strongest model.

It will report its environment findings and **wait for you** before writing
files. Read that report. Then it builds the gate, self-tests it, writes
`spec.md`, `plan\test-plan.md`, `plan\tasks.json`, `CLAUDE.md` and a skill,
and stops. **It should not write tests or build your application.**

### 3.2 Review what it produced

Ten minutes here saves hours later. Check three things:

1. **The failure-mode matrix.** `<py> verify\smoke_test.py --matrix` — every
   F-number has a check that catches it, and you believe the check.
2. **The routing.** `<py> loop\run_loop.py build --dry-run` — each task, its
   tier, and its escalation path. Tasks that carry a named failure should
   start on `opus`. Boilerplate should not.
3. **The interface contract in `spec.md`.** The test author will write tests
   from it without seeing any code. If you could not, neither can it.

For a modelling tool, two more:

4. **The bands.** The harness report should show, for every score check, the
   range measured over several seeds for the good reference implementation
   and for each broken one. A wide gap between them is what you want. A band
   with no measurements behind it is a guess.
5. **The methodology in `spec.md`** matches what you wrote in the brief, and
   the report lists anywhere the data argued against it.

To change anything, reopen a harness session with the judge unlocked:

```powershell
<py> loop\run_loop.py harness --open
```

### 3.3 Confirm the hooks loaded

```powershell
<py> loop\run_loop.py doctor
claude
```
then inside the session:
```
/hooks
```

You should see a `PreToolUse`, a `PostToolUse` and a `Stop` hook, each using
the **absolute interpreter path** (`A:\envs\...\python.exe`), not bare
`python`. If one is missing or shows bare `python`, stop and re-run the
installer. Everything downstream depends on this.

`doctor` also runs the gate's self-test and reports two things worth reading:
a timing line (how long the gate takes on each edit, against a budget) and,
if the gate gave different results on two identical runs, a `NOT
DETERMINISTIC` failure. Fix either through `harness --open` before going on.

### 3.4 Prove the hooks actually fire ⚠️

Never trust a harness you haven't watched reject something. In that same
plain `claude` session (no model choice matters here), two probes.

**Probe 1 — the gate fires on its own.** No real deliverable exists yet, so
give the gate something to fail:

```
Write a deliberately broken placeholder <file to break> — one the gate must
fail. Make only that one write, then stop. Do not fix it.
```

**Expected:** immediately after the write, the gate's complaint appears **on its
own** — you didn't ask for verification and the agent didn't choose to run it.

(Note what a `PostToolUse` hook actually does: it runs *after* the write, so the
file does get written — nothing is rolled back. Exit 2 feeds the failure straight
back into the model. The thing you're looking for is that **automatic feedback**,
not a prevented edit.)

**Probe 2 — the judge is locked.**

```
Add a comment line to verify/smoke_test.py. Make only that one edit, then stop.
```

**Expected:** the edit is refused with "BLOCKED by the harness guard".

**If either probe does nothing:** the hooks are dead. The usual suspects are a
wrong interpreter path in `.claude\settings.json`, or a session that was
already open when the kit was installed (settings changes are normally picked
up live, but a restart is the reliable fix). Fix before continuing.

Then clean up:
```
Delete the placeholder.
```

### 3.5 Commit the harness

```powershell
git add -A
git commit -m "Add build-loop harness"
```

This commit is the baseline the driver holds every agent to. It refuses to
start a stage while the gate, plan, spec or kit have uncommitted changes, so
the thing agents are judged against is always something you reviewed.

---

# Part 4 — Build the application

### 4.1 Write the tests

```powershell
<py> loop\run_loop.py tests
```

Opus writes the pytest suite from `spec.md` and `plan\test-plan.md`, with no
application in sight. The driver then checks the suite is **red**: every test
that depends on the application must fail now, or it proves nothing.

Read `loop\state\tests-report.md`. It lists any test that *already passes*.
That is fine for a test of fixtures or source data and a defect for anything
else. Then:

```powershell
git add -A
git commit -m "Add test suite"
```

From this point the tests are locked. Builders cannot edit them.

### 4.2 Run the build

```powershell
<py> loop\run_loop.py build
```

One unattended Claude Code run per task, on the model its tier names. After
each run the driver re-runs that task's gate checks and tests itself, plus
everything earlier tasks turned green. Then:

- **Pass** → next task.
- **Fail** → retry on the same model with the failure fed back; then escalate
  (`haiku` → `sonnet` → `opus`).
- **Fails on every tier** → the build **stops**. Fable writes a read-only
  diagnosis to `loop\state\escalations\<task>.md`. Nothing in the spec, plan,
  gate or tests is changed for you. See Part 5.

When every task has passed, the full gate and the full suite run together.

You can stop it (Ctrl+C) and run the same command again; finished tasks are
not repeated.

### 4.3 Run the review

```powershell
<py> loop\run_loop.py review
```

Fable, with fresh context and no write access, looks for what the gate and
tests cannot judge: output that passes but is wrong, code that behaves
differently under test, failure modes nobody named. The report lands in
`loop\state\review.md` with a verdict.

### 4.4 Review what the machine can't judge

The gate proved it runs and the data landed. The tests proved the contract.
The review looked for cheating and gaps. Your job is whether it's the *right*
chart, the right story, the sensible axis. For a modelling tool: whether the
number means what the report says it means, and whether a score on your real
data is believable. Nothing in the loop has an opinion on that.

**If it's wrong, fix the judge, not the output.** Open
`run_loop.py harness --open`, have Fable turn the problem into a sharper spec,
a new gate check or a new task, commit, and re-run. Don't hand-patch the
output — that breaks the loop's premise, and the same defect comes back next time.

### 4.5 Commit, then tune your routing

```powershell
git add -A
git commit -m "Build <deliverable> via loop"
```

Now read `loop\state\build-report.md`. It shows, per task, the tier you
planned and the model that actually passed it.

- Tasks that **escalated**: that kind of work needs a higher tier next time.
- `complex` tasks that passed **first time, quickly**: candidates for
  `routine`. Try it on the next project, or re-run this one with
  `build --restart` after lowering the tier.

That table, over a few projects, is how you find your cheapest reliable routing.

---

# Part 5 — Operating it day to day

**You touch the brief and the plan. That's it.** New work = new tasks in
`plan\tasks.json` (through a `harness --open` session), then `tests`, then
`build`. The harness is capital; the plan is the per-task cost.

**When the driver stops, it tells you why.** Exit codes:

| Code | Meaning | What to do |
|---|---|---|
| 0 | Done | Review and commit |
| 1 | The stage ran and did not pass | Read the report it names |
| 2 | **Stopped — needs you** | See below |
| 3 | **HARNESS ERROR** — environment, never the code | `run_loop.py doctor`, fix, re-run |

**The three-strikes rule, now enforced.** If a task fails on every tier, the
problem is your spec, your gate, your tests or the task split — **not the
model**. More attempts won't help, so the driver doesn't make them. Read the
escalation file: it says whether every attempt failed the *same* way (spec or
gate at fault) or *differently* (task too big), and gives Fable's diagnosis
with a proposed fix. Apply the fix you agree with through `harness --open`,
commit, run `build` again.

- *Spec too vague* → builders guess wrong. Paste the real data shape into `spec.md`.
- *Gate mis-calibrated* → e.g. demanding 3 KPIs from data supporting 2. It can
  **never** pass. Tune the thresholds to the real data.
- *Task too big* → split it; give each half its own check.

**Grow the harness from friction, not speculation.** When something goes wrong
repeatedly, promote it:

| Repeated problem | Promote to |
|---|---|
| A defect got past the gate | a **gate check** with a broken fixture that proves it |
| Agents keep skipping a check | a **hook** |
| Agents keep needing the same explanation | a **skill** |
| Context keeps filling with side-quest output | a **subagent** (the `scout` is the pattern) |
| Agents keep needing an external system | an **MCP server** |

Don't build these in advance. You'll provision things you never use and miss the
ones you need.

**Git stays yours.** Agents are denied git outright. The driver only *reads*
git state, to check the baseline is committed.

---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Python was not found; run without arguments to install from the Microsoft Store` | Store alias stub | Disable aliases (1.1), use absolute paths |
| Hook never fires | Wrong interpreter in `settings.json`, or session opened before the kit was installed | Re-run `install_kit.py` with `<py>`, restart the session |
| Gate fails every iteration with `playwright not installed` | Hooks pinned to a different interpreter than the one with Playwright | Re-run `install_kit.py` with the right `<py>` |
| `doctor --live`: "could not run a command" | Auto permission mode unavailable on your account or disabled by your org | `MODEL-ROUTING.md`, "Permission mode" |
| Unattended run ends at once with a sign-in or consent message | Not signed in, or Fable consent not given | `claude` interactively once; `/model fable` (1.3) |
| Driver says `HARNESS ERROR` and names a flag | Claude Code older than the kit expects | `claude update` |
| `STOPPED ... uncommitted changes` | Gate, plan, spec or kit edited since the last commit | Commit, or `--allow-dirty` if you mean it |
| `doctor`: `NOT DETERMINISTIC` | The gate gave different results on two identical runs: an unpinned seed, parallel fitting, or a dependence on the clock | Pin seeds, run single-threaded in the gate, via `harness --open` |
| `doctor`: "the gate takes Ns on every edit" | The per-edit gate run is over budget | Mark heavy checks `slow=True`, shrink the fast profile, or raise `limits.hook_gate_budget_sec` if you accept the wait |
| A builder passes every edit, then fails when it tries to finish | A slow check, which only runs at that point, is failing | Expected. The failure message names the check |
| Build log: "there is no test suite" | The plan names no test files, so the gate is the only judge | Fine for a small project; otherwise add tests to the plan |
| `TAMPER detected and undone` once | An agent tried to edit the judge; the driver restored it | Nothing — that is the system working. Note which task |
| "running the checks changed locked files" on every run | A test or the app writes into `tests\` or `verify\` at run time | Tests write to `tmp_path`; the gate to `verify\artifacts\`; the app nowhere near its inputs |
| Guard blocks a harmless command | The shell guard is a heuristic and erred on the safe side | Rephrase (e.g. use the Read tool); if it recurs, note the command |
| API returns 403 | Often a missing `User-Agent` header, not a firewall | Add a UA header before blaming the network |
| Gate passes locally, fails in project dir | Mapped network drive / UNC path | Move project to a local disk |
| Agent thrashes on the same failure | Gate demands something the data can't supply | Tune gate thresholds to the real data |
| Chart canvas "drew no pixels" intermittently | Chart animation still running when gate reads | `animation: false` in Chart.js |
| Startup warning about a `PowerShell(git *)` rule | The PowerShell tool is not enabled on this install | Harmless; the `Bash(git *)` rule and the guard still apply |

---

# The rules worth remembering

1. **A gate you have not watched fail is not a gate.**
2. **Verify, don't assert** — every claim about the environment should come from
   a command someone actually ran.
3. **An agent stopping proves nothing.** Only the driver's own re-run of the
   checks counts.
4. **Fix the judge, not the output.**
