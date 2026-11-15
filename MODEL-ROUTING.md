# Model routing

Which model does which work, why, and the one file to edit when that changes.

**The whole policy lives in `loop/loop.json`.** Nothing else names a model,
except the `scout` subagent (pinned to `haiku` in its own file). Every entry
uses an **alias** (`fable`, `opus`, `sonnet`, `haiku`), never a version
number, so the routing follows new releases without edits.

---

## The policy

| Work | Model | Effort | Attempts | Why this model |
|---|---|---|---|---|
| Brief (claude.ai Project) | Fable | — | — | The interview decides what the gate will look for |
| **Harness**: discovery, gate, spec, test plan, task plan | `fable` | xhigh | interactive | Every later stage inherits its mistakes. Highest leverage per token |
| **Tests**: the pytest suite, from the spec | `opus` | high | 2 | Strong coding model, deliberately *not* the one that builds, so the tests are an independent reading of the spec |
| **Build, `complex` tier** | `opus` | high | 3 | Tasks that carry a named failure mode or a reconciliation rule |
| **Build, `routine` tier** | `sonnet` | medium | 2, then escalates | One concern, clear contract |
| **Build, `support` tier** | `haiku` | medium | 2, then escalates | One obvious right answer: scaffolding, config, fixtures, docs |
| `scout` subagent, inside any build run | `haiku` | — | — | Searches and digests long gate or test output, so the builder's context stays on the work |
| **Diagnosis** after three strikes | `fable` | high | 1, read-only | Decides whether spec, gate, tests or plan is at fault |
| **Review** | `fable` | high | 1, read-only | Looks for what the gate and tests cannot judge |

Fable sits at the two ends, where judgment matters most and volume is low.
The volume in the middle goes to the cheapest model that can pass the checks.

## Why not one strong model for everything

- **Independence.** The agent that writes the tests never sees the code. The
  agent that builds cannot edit the tests. The reviewer has no stake in
  either. One long session doing all three marks its own homework.
- **Fresh context per task.** Each task starts clean with only its brief and
  its checks. Nothing from task 2 leaks into task 7.
- **Cost follows difficulty.** Most of a build is routine. The tier on each
  task is a claim about difficulty that the build then tests, and the build
  report shows where the claim was wrong.

## The tiers

The harness stage assigns a tier to every task. The rule it follows:
**tier by the cost of being subtly wrong, not by size.**

| Tier | Starts on | Use for |
|---|---|---|
| `complex` | `opus` | A named failure mode (F1, F2, ...) or a reconciliation rule. Wiring across layers. Process lifecycle. Parsing messy real data. Anything where a plausible wrong answer would survive a casual look. |
| `routine` | `sonnet` | One concern, a clear contract in the spec, an obvious pattern to follow. |
| `support` | `haiku` | One obvious right answer. |

For a modelling tool, "subtly wrong" has a precise meaning: anything that
decides **which rows a number is computed on** is `complex`. That covers
splitting, validation, fitting any preprocessing, metric and baseline
computation, model selection, leakage detection and joins. Adding another
model family or report section behind an interface that already exists is
`routine`.

When torn between two tiers the planner picks the lower, because escalation
is automatic and cheap. The exception is a task that carries a named failure:
it starts at `complex`.

## Escalation

```
support ──2 fails──▶ routine ──2 fails──▶ complex ──3 fails──▶ STOP
 haiku                sonnet               opus               fable diagnoses,
                                                              you decide
```

- A retry on the **same** tier resumes the same session, with the failure
  output as its next instruction.
- Moving **up** a tier starts a fresh session on the stronger model, with the
  failure history in its brief. It does not inherit the weaker model's
  wrong turns.
- At the top, the loop stops. It does not let any agent rewrite the spec, the
  plan, the gate or the tests unattended. Fable reads everything, classifies
  the cause, and proposes the smallest fix. You apply it.

The ladder and the attempt counts are `ladder` and `tiers.*.attempts` in
`loop/loop.json`.

## Effort

Effort is set explicitly on every run, because the default now differs by
model and a default you didn't choose is a setting you don't know you have.

Raise `complex` to `xhigh` if tasks at that tier keep needing all three
attempts. Don't raise `routine` or `support`: if they need more thought, the
task is in the wrong tier.

## Optional: Fable as advisor during the build

Claude Code has an experimental advisor tool: the working model consults a
stronger one at decision points (before committing to an approach, when an
error keeps recurring, before declaring done). It is set per tier. To give
the Opus builder a Fable advisor, in `loop/loop.json`:

```json
"complex": { "model": "opus", "effort": "high", "attempts": 3, "advisor": "fable", ... }
```

The driver then passes `--advisor fable` on runs at that tier. Leave it `null`
until the plain loop is working for you:

- It is experimental, and available on the Anthropic API only (not Amazon
  Bedrock, Google Cloud or Microsoft Foundry).
- The advisor must rank at or above the working model. Claude Code refuses
  to start a run with a pairing it does not accept, and the driver reports
  that as a HARNESS ERROR. Run `claude --advisor fable --model <alias>` once
  by hand for each tier you set it on.
- Each consultation re-reads the whole conversation at the advisor's rates.
- Fable as advisor needs the same one-time consent as `/model fable`.

Try it on one project and compare build reports before making it your default.

## Permission mode

Unattended runs use `--permission-mode auto`: a classifier reviews each
action instead of prompting you. It is the mode built for this, and three
things hold whatever it decides: the deny rules in `.claude/settings.json`,
the guard hook, and the driver's tamper check.

If `doctor --live` reports that a command could not run, auto mode is not
available to you (an organisation can disable it). Then set
`"permission_mode": "acceptEdits"` in `loop/loop.json` and add allow rules for
your interpreter to `.claude/settings.json`:

```json
"permissions": { "allow": ["Bash(A:/envs/<project>/Scripts/python.exe *)",
                           "PowerShell(A:\\envs\\<project>\\Scripts\\python.exe *)"] }
```

Expect some friction: allow rules match the command as typed, so a command
spelled differently is denied and the agent has to try again. Run
`doctor --live` after the change.

Never use `bypassPermissions` for this outside a disposable VM or container.
Native Windows has no command sandbox, so that mode leaves only the guard
heuristics and the tamper check between an agent and your disk.

## Limits

In `loop/loop.json`:

| Setting | Meaning |
|---|---|
| `tiers.*.max_turns`, `roles.*.max_turns` | Turn cap for one run |
| `tiers.*.max_budget_usd`, `roles.*.max_budget_usd` | Spend cap for one run |
| `limits.total_budget_usd` | The driver stops (exit 2) once the running total reaches this |
| `limits.run_timeout_min` | Wall-clock cap for one run |

**The shipped numbers are starting values, not measurements.** Set them to
what you are willing to spend before your first unattended run, then adjust
from the build report. Spend figures are Claude Code's own client-side
estimates; on a subscription they are an estimate of usage, not a bill.
A run that hits a cap is still judged. If its checks do not pass, it counts
as a failed attempt and the task carries on up the ladder.

## When a new model ships

Usually nothing. Aliases move to the new version when you update Claude Code.

1. `claude update`, then `claude --version`.
2. `<py> loop\run_loop.py doctor --live`.
3. Run a project you have already built with `build --restart` and compare
   the build report with the last one: attempts per task, escalations, spend.

To hold a specific version (for a reproducible comparison, say), put the full
model id in `loop/loop.json` in place of the alias, for example
`"model": "claude-opus-5-5"`.

To change the policy itself, e.g. try Sonnet on the `complex` tier:
edit `tiers.complex.model`, run `build --dry-run` to see the new routing,
then `build --restart`. One file, one line.

## Reading the build report

`loop\state\build-report.md`, after every build:

| You see | It means | Do |
|---|---|---|
| Task passed first time on its planned tier | The tier was right, or generous | If it was `complex` and quick, try `routine` for that kind of task next time |
| Task escalated | The tier was too low | Plan that kind of task one tier up |
| Several `complex` tasks used all 3 attempts | The tasks are too big, or the spec is thin | Split tasks; tighten the interface contract |
| A task stopped the build | Not a model problem | Read the escalation file |
| Judge-awareness warnings | App code mentions tests or the gate | Each needs a reason; the reviewer is told to check them |
