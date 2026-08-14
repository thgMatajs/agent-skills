# Behavioral Paired Eval (Tier 3)

Run **only** when the skill claims to change agent behavior (a discipline,
technique, or workflow skill). Pure reference skills are judged on retrieval, not
pass-rate gain — skip this tier for them.

## Method (paired baseline)

For the same task set, run each scenario twice:
- **without_skill** — baseline: the agent, no skill loaded.
- **with_skill** — the skill loaded into context.

Have a judge (a fresh model instance) grade both outputs against fixed
`expected_behavior` bullets. Use **≥3 scenarios**, ideally including one that
*tempts the failure* the skill is meant to prevent.

```json
{
  "skill": "auditing-skills",
  "query": "Review this SKILL.md and tell me if it's good enough to promote.",
  "files": ["candidate/SKILL.md"],
  "expected_behavior": [
    "Runs cheap structural checks before semantic judgment",
    "Flags the description if it summarizes workflow instead of routing",
    "Produces a verdict with a complete, unranked inventory of suggested improvements"
  ]
}
```

## Executor/grader separation (avoid self-correction bias)

The agent that *executes* the task must not be the one that *grades* it. An executor
grading itself will rationalize its own output as passing — the skill then looks good
because the agent self-corrected, not because the skill worked. Use a **fresh judge
instance** with only the task, the `expected_behavior` bullets, and the output — not
the executor's reasoning. Judge **first-attempt** output; don't let the executor retry
into a pass. (Pair this with the paired-trajectory read: compare with/without traces
for where the skill actually changed the behavior, not just the final answer.)

## Runner

`scripts/paired_eval.py` orchestrates this. It has no model API of its own — it
emits the two dispatch prompts and does the math, so it can't fabricate a result.

```bash
python scripts/paired_eval.py prompts eval/dataset.json   # get with/without prompts
# dispatch both arms as subagents (>=3 reps), judge each vs expected_behavior,
# record pass fractions + tokens + duration_ms into results.json:
python scripts/paired_eval.py score results.json          # -> PRG + ECG
```

`results.json` shape:
```json
{"skill": "auditing-skills",
 "with_skill":    {"pass": [1.0, 0.83, 1.0], "tokens": [9000, 8600, 9200], "duration_ms": [120000, 110000, 130000]},
 "without_skill": {"pass": [0.67, 0.5, 0.67], "tokens": [4200, 4000, 4400], "duration_ms": [42000, 40000, 44000]}}
```

## Metrics

- **Pass-rate gain (PRG)** — `(pass_with − pass_without)`. Positive is the whole
  point. Zero or negative means the skill isn't earning its context — that's a
  finding, not a footnote.
- **Efficiency/cost delta** — token and wall-time difference, with vs. without.
  A skill that adds 3k tokens for a 0.05 pass-rate bump is a poor trade; say so.

## Discipline skills need pressure, not just tasks

If the skill enforces a rule under pressure (like "always audit Tier 2 before
concluding"), a happy-path task won't reveal whether it holds. Add scenarios that
combine pressures — time, sunk cost, authority — and check the rule survives.

## Cheap wording micro-test (before full scenarios)

Before running full paired scenarios, verify the wording binds: one fresh-context
sample per call, always with a no-guidance control, 5+ reps, read every flagged
match by hand. Converging reps = the wording is binding; five different readings =
tighten the form first. Micro-tests check wording; they don't replace the paired
eval for behavior.
