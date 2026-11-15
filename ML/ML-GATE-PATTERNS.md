# ML gate patterns

How to build a gate for a tool whose output is a model, a score or a
statistical conclusion. Read with `ML/BOOTSTRAP-TEMPLATE.md`. A complete
runnable example is `kit/examples/smoke_test.ml.example.py` (copied into each
project as `loop/examples/smoke_test.ml.example.py`).

## The idea

On real data nobody knows the right score, so a gate cannot check one. What
it can do is build data where the right **conclusion** is known because you
constructed it, then check the tool reaches it.

Each pattern below is a small synthetic dataset, the conclusion a correct
tool must reach on it, and the silent failures that make a tool reach the
wrong one. Pick the patterns that match the failure modes in your brief. Two
are needed by every project: planted signal and pure noise.

## Rules that apply to every pattern

| Rule | Why |
|---|---|
| The gate generates each dataset in code, from a fixed seed, into `verify/artifacts/` | Reproducible, small, and reviewable as a few lines rather than an opaque file |
| Small: hundreds to low thousands of rows | The gate runs on every edit |
| Scores are asserted as bands with `ctx.require_between` | A fitted model's score is not an exact value |
| Bands are measured, not guessed: run the good fixture over five or more data seeds, take the range, add a margin, and check every broken fixture lands outside it on every seed | A guessed band either never passes or never fails |
| Single-threaded and seeded inside the gate | Parallel fits are a common source of scores that move between runs |
| Every measured value goes through `ctx.record` or a band helper | `--selftest` runs the good fixture twice and fails if any of them moves |
| Heavy checks are `slow=True`; setup reads `ctx.fast` | Skipped per edit, run when a builder finishes and whenever the driver judges |
| The gate drives the tool's public interface and reads its output | Internals stay the builder's to change |
| No score is ever asserted on real data | There is no known right answer there. Real data gets structural checks only |
| Each failure mode has a broken reference implementation in `--selftest` | A gate you have not watched fail is not a gate |

## The patterns

### 1. Planted signal
**Build:** the target is a known function of one or two features, plus noise.
**Right conclusion:** clear lift over the baseline, inside a measured band.
**Catches:** a model that is never fitted; a target column misread or
inverted; features dropped on the way in; a headline that is just the baseline.
**Note:** this pattern gives the others their meaning. "No lift on noise"
proves nothing about a tool that never finds lift anywhere.

### 2. Pure noise
**Build:** features and target drawn independently; or take the planted-signal
set and shuffle the target.
**Right conclusion:** lift about zero, inside a band around zero.
**Catches:** scoring on training rows; preprocessing fitted before the split;
feature selection done on all rows; picking the best of many models on the
rows used to report it. Every one of these finds "signal" in a coin flip.
**Note:** the single most valuable dataset in the gate. Use a memorising
model in the fast profile (a deep tree, nearest neighbour) so leakage shows
up as a large effect rather than a marginal one.

### 3. Leaked column
**Build:** planted signal plus a column that copies the target, a noisy copy
of it, or a field only filled in after the outcome (a cancellation date, a
default flag, a settlement amount).
**Right conclusion:** the column is flagged in the output and excluded.
**Catches:** a near-perfect score reported as predictability.
**Note:** add a control: a column that is merely strongly predictive and must
NOT be flagged, so the leak rule cannot pass by flagging everything.

### 4. Join fan-out
**Build:** a parent table and a child table with many rows per parent key,
the child's values unrelated to the target.
**Right conclusion:** rows after the join equal the number of parents, counted
by the gate; no lift.
**Catches:** joining without aggregating, which multiplies rows and puts the
same entity on both sides of a split.

### 5. Join key mismatch
**Build:** the same keys as text with leading zeros in one table and as
integers in the other; or trailing spaces; or mixed case.
**Right conclusion:** every key matches after normalisation, or the tool
stops with a named error. The count of unmatched keys is reported.
**Catches:** a join that silently matches almost nothing and fills the
features with zeros or missing values.

### 6. Repeated entities
**Build:** each entity appears many times with near-identical features, and
the label is random per entity.
**Right conclusion:** with the grouped scheme, no lift. Assert the tool uses
it: the gate also checks no entity id appears on both sides of the split the
tool reports.
**Catches:** a random split that lets the model recognise entities rather
than learn anything.

### 7. Imbalanced target
**Build:** pure noise with a 95/5 target.
**Right conclusion:** lift about zero, and the headline metric is the one the
methodology names, with its baseline.
**Catches:** accuracy reported as the headline, where predicting the majority
class scores 95%.

### 8. Time order
**Build:** a series where the target drifts with time and features carry
information about the future (a rolling mean computed over the whole series).
**Right conclusion:** with the time-ordered scheme, modest or no lift. The
gate checks every training timestamp precedes every test timestamp.
**Catches:** a shuffled split on time-dependent data; features built with
look-ahead.
**Use when:** the data has a time column that matters.

### 9. Missing and malformed values
**Build:** planted signal with blank cells, an unparseable date, a text value
in a numeric column.
**Right conclusion:** every row is accounted for: the output's row counts
add up to the source's, with dropped or imputed rows reported by reason.
**Catches:** rows dropped on load; a parse failure that turns a column into
all-missing; a silent coercion.

### 10. Selection inflation
**Build:** pure noise, run with many model configurations.
**Right conclusion:** the headline equals the score on the untouched holdout
(read both from the output and compare), and is not the maximum of the
cross-validation scores.
**Catches:** reporting the best cross-validation score of many tries as the
result.
**Note:** needs the full profile, so usually a slow check.

### 11. Planted clusters (unsupervised)
**Build:** well-separated groups with known membership; and a second dataset
with no structure at all.
**Right conclusion:** on the first, the recovered grouping agrees with the
planted one (adjusted Rand index inside a measured band). On the second, the
tool reports that it found no meaningful structure.
**Catches:** a clustering step that always returns k groups and presents them
as findings; unscaled features letting one column decide everything.

### 12. Output reconciliation
**Build:** any run above.
**Right conclusion:** every number in the report equals the number in the
machine-readable output; no `NaN` or infinity; every required section is
populated.
**Catches:** a report rendered from stale or rounded-twice values; a section
that is blank and reads as "nothing to report".

## Choosing bands

1. Write the good reference implementation and each broken one.
2. For each score check, run all of them over at least five data seeds.
3. Good range: say 0.38 to 0.47. Broken range for the failure it should
   catch: say 0.00 to 0.02. Set the band between them, nearer the good range:
   0.25 to 0.55.
4. If the ranges overlap or nearly touch, the dataset is too small or the
   effect too weak. Fix the dataset, not the band.
5. Fix one seed for the gate, and write the measured ranges in a comment
   beside the band.

A band is changed only when it was measured wrong. Never because a build
missed it.

## What a gate of this kind cannot tell you

- Whether the methodology is the right one for the question.
- Whether the features make sense for the business.
- Whether a real-data score is good.

Those are in the brief, in the review, and with you.
