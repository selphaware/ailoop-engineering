# Loop Engineering — Setup Guide

How to set up an autonomous build loop for any Python + HTML/JS project, on Windows.

**The idea:** you don't ask an agent to build something and hope. You define
"done" as a program that returns pass/fail, then let the agent iterate against it
until it passes. The program that judges is called the **gate**. The gate plus its
supporting files is called the **harness**.

You build the harness once per project. After that, every task is just a spec.

**Convention:** anything in `<angle brackets>` in this guide — `<project>`,
`<deliverable>`, `<you>` — is a placeholder. Replace it with your real value
before pasting; never paste the brackets themselves. In prompts especially,
name the exact file (e.g. `dashboard.html`) — a diagnostic that makes the agent
guess its own target proves nothing.

Worked examples, stratified across three project shapes. **Each column is one
coherent project — read downwards:**

| Placeholder | ① Static dashboard | ② API + frontend | ③ Data pipeline |
|---|---|---|---|
| `<you>` (GitHub owner) | `usman-dev` | `acuity-analytics` | `usman-dev` |
| `<project>` (repo + venv name) | `fx-monitor` | `sales-pipeline` | `etl-refresh` |
| Interpreter path | `A:\envs\fx-monitor\Scripts\python.exe` | `A:\envs\sales-pipeline\Scripts\python.exe` | `A:\envs\etl-refresh\Scripts\python.exe` |
| `<deliverable>` (gate argument) | `dashboard.html` | `app` | `output\monthly_report.csv` |
| File to break in step 3.4 | `dashboard.html` | `app\static\index.html` | `etl\transform.py` |

Note the last two rows **diverge** once the deliverable is more than one file:

- **② API + frontend:** the gate's argument is the app folder (it starts the
  server and verifies API + UI together), but the live-fire test breaks one
  concrete file inside it.
- **③ Data pipeline:** the gate *runs the pipeline, then checks the output* —
  so breaking `output\monthly_report.csv` directly would prove nothing (the gate
  regenerates it). You must break the **code that produces it**. Break the thing
  the gate reads; for pipelines, the gate effectively reads what your code does.

---

## Files in this set

| File | What it's for |
|---|---|
| `SETUP-GUIDE.md` | This file. The steps. |
| `BOOTSTRAP-TEMPLATE.md` | Copy into a new project, fill in the top, hand to Claude Code. |
| `BOOTSTRAP-EXAMPLE.md` | The template filled in for a real project, so you can see what "good" looks like. |

---

# Part 1 — One-time machine setup

Do this once. Skip if already done.

### 1.1 Kill the Microsoft Store Python stubs

Windows ships fake `python.exe` shims that break everything silently.

**Settings → Apps → Advanced app settings → App execution aliases →
turn OFF `python.exe` and `python3.exe`.**

### 1.2 Install Claude Code

```powershell
irm https://claude.ai/install.ps1 | iex
```
Restart PowerShell, run `claude` once, authenticate in the browser.

### 1.3 Check you have Python 3.10+

```powershell
A:\envs\py312\python.exe --version
```
Use your own path. Note it down — you'll need it constantly.

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
A:\envs\<project>\Scripts\python.exe -m pip install playwright
A:\envs\<project>\Scripts\python.exe -m playwright install chromium
```

Write down the absolute path: `A:\envs\<project>\Scripts\python.exe`
(Put the venv on a local disk too — a venv on a network share adds latency to
every single gate run.)

**Install only the gate's dependencies now** (Playwright + Chromium). Leave the
app's runtime packages — `fastapi`, `pandas`, whatever — for the agent to install
into this same venv as it discovers it needs them.

> Why you and not the agent: the harness pins this interpreter, and the gate
> self-tests using it. An agent that creates its own verification environment has
> nothing trustworthy to verify with — and when it goes wrong, it goes wrong at
> the exact moment you have least ability to diagnose it.

### 2.3 Copy in the bootstrap

Copy `BOOTSTRAP-TEMPLATE.md` into the project folder as `BOOTSTRAP.md`.

### 2.4 Fill in the project section

Open `BOOTSTRAP.md` and complete the project block at the top (six fields).

**Spend real time on this — 15 minutes, not 2.** Especially this line:

> *What "broken but passes tests" looks like*

That sentence becomes your gate. It's the single highest-leverage thing you write.
See `BOOTSTRAP-EXAMPLE.md` for how specific to be.

---

# Part 3 — Build the harness

### 3.1 Run Claude Code to generate the harness

```powershell
cd D:\sandbox\<project>
claude
```

Set the model: `/model` → **Fable 5**, effort **xhigh**.

> Why Fable here: harness generation is long-horizon, multi-file work where the
> agent must discover an unfamiliar environment before it can build — where
> Fable's lead is largest. The app build afterwards is usually better on Opus.
> This is a guideline, not a rule: judge by task shape, not stage.

Then paste:

```
python is A:\envs\<project>\Scripts\python.exe
Read BOOTSTRAP.md and follow it.
```

It will report its environment findings, build the harness, self-test the gate,
and stop. **It should not build your application.**

### 3.2 Restart Claude Code ⚠️

```
/exit
```
```powershell
claude
```

**This step is not optional.** Hooks are registered when a session starts. The
harness didn't exist when the last session began, so its hook is not live. Skip
this and you have no automatic verification — and it fails silently.

### 3.3 Confirm the hook loaded

```
/hooks
```

You should see a `PostToolUse` hook whose command uses the **absolute
interpreter path** (`A:\envs\...\python.exe`), not bare `python`. Approve it if
prompted.

If it's missing or shows bare `python`, stop and fix it. Everything downstream
depends on this.

### 3.4 Prove the hook actually fires ⚠️

Never trust a harness you haven't watched reject something.

At this point no real deliverable exists yet, so give the gate something to fail:

```
Write a deliberately broken placeholder <deliverable> — one the gate must
fail. Make only that one write, then stop. Do not fix it.
```

**Expected:** immediately after the write, the gate's complaint appears **on its
own** — you didn't ask for verification and the agent didn't choose to run it.

(Note what a `PostToolUse` hook actually does: it runs *after* the write, so the
file does get written — nothing is rolled back. Exit 2 feeds the failure straight
back into the model. The thing you're looking for is that **automatic feedback**,
not a prevented edit.)

**If the file is written and nothing appears:** the hook is dead. The usual
suspects are bare `python` in `settings.json` or a session started before the
harness existed. Fix before continuing.

Then clean up:
```
Delete the placeholder.
```

### 3.5 Commit the harness

```powershell
git add -A
git commit -m "Add build-loop harness"
```

Clean baseline. Now you can diff exactly what the app build touched.

---

# Part 4 — Build the application

### 4.1 Write the task spec

The harness includes a `spec.md`. Make it concrete: real endpoints, real field
names, the actual metrics and views you want, and any known traps in the data.

### 4.2 Run the build

Fresh session, `/model` → **Opus 4.8**, effort **xhigh**:

```
python is A:\envs\<project>\Scripts\python.exe
Read spec.md and build it. Don't stop until
`A:\envs\<project>\Scripts\python.exe verify\smoke_test.py <deliverable>` exits 0.
```

> The bootstrap standardises the gate at `verify\smoke_test.py`, and the
> harness's `CLAUDE.md` states the literal gate command. If the harness's final
> report gave a different command, use that one.

Watch for the moment the gate fires on its own after a write and the agent fixes
itself without you saying anything. **That's the loop working.**

### 4.3 Review what the machine can't judge

The gate proved it runs and the data landed. Your job is whether it's the *right*
chart, the right story, the sensible axis.

**If it's wrong, sharpen `spec.md` and re-run.** Don't hand-patch the output —
that breaks the loop's premise.

### 4.4 Commit, then find your cheapest model

```powershell
git add -A && git commit -m "Build <deliverable> via loop"
```

Now re-run the *same spec* on **Sonnet 5** at default effort. If it still goes
green in ≤3 iterations, that's your production model — and you've learned your
spec is robust. That number decides whether this scales.

---

# Part 5 — Operating it day to day

**You touch `spec.md`. That's it.** New task = new spec, same harness. The harness
is capital; the spec is the per-task cost.

**The three-strikes rule.** If it fails the gate three times *for the same
reason*, the problem is your spec or your gate — **not the model**. A fourth
iteration won't help.

- *Spec too vague* → agent guesses wrong. Paste the real data shape into `spec.md`.
- *Gate mis-calibrated* → e.g. demanding 3 KPIs from data supporting 2. It can
  **never** pass and the agent will thrash inventing filler. Tune the thresholds.

**Grow the harness from friction, not speculation.** When something goes wrong
repeatedly, promote it:

| Repeated problem | Promote to |
|---|---|
| Agent keeps skipping a check | a **hook** |
| Agent keeps needing the same explanation | a **skill** |
| Context keeps filling with side-quest output | a **subagent** |
| Agent keeps needing an external system | an **MCP server** |

Don't build these in advance. You'll provision things you never use and miss the
ones you need.

---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Python was not found; run without arguments to install from the Microsoft Store` | Store alias stub | Disable aliases (1.1), use absolute paths |
| Hook never fires | Registered as bare `python`, or session started before harness existed | Absolute path in `settings.json`, then restart session |
| Gate fails every iteration with `playwright not installed` | Hook spawning the wrong interpreter | Pin absolute venv path in the hook command |
| API returns 403 | Often a missing `User-Agent` header, not a firewall | Add a UA header before blaming the network |
| Gate passes locally, fails in project dir | Mapped network drive / UNC path | Move project to a local disk |
| Agent thrashes on the same failure | Gate demands something the data can't supply | Tune gate thresholds to the real data |
| Chart canvas "drew no pixels" intermittently | Chart animation still running when gate reads | `animation: false` in Chart.js |

---

# The two rules worth remembering

1. **A gate you have not watched fail is not a gate.**
2. **Verify, don't assert** — every claim about the environment should come from
   a command someone actually ran.
