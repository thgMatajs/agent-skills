# Inventory Fan-Out

Auditing many skills sequentially wastes the parent's context and is slow. Dispatch
one subagent per skill, in parallel, then rank the returned reports.

This section is itself a subagent contract — it must pass the checklist in
`auditors/contracts-subagent.md` (dogfooding).

## Pre-pass: cross-skill dedup (before fan-out)

A per-skill subagent sees only its own skill, so it **cannot** answer Tier 0's
"duplicate of an existing skill?" — that check is structurally impossible in the
fan-out and must happen here, once, over the whole set.

Before dispatching: collect every skill's `name` + `description` (cheap — frontmatter
only, no bodies). Cluster by overlap:
- **Near-duplicate** — two descriptions fire on the same triggers/inputs → candidates
  to merge; audit both but flag the pair.
- **Overlap/conflict** — one skill's scope is a subset of another's, or two would both
  trigger on the same request (ambiguous routing) → flag for consolidation or sharper
  descriptions.

Feed the dedup flags into each flagged skill's Tier 0 (the subagent can't find them,
so you inject them). Skills with no overlap proceed normally.

## Dispatch prompt (one per skill)

Each subagent gets a **self-contained** prompt. It must not depend on the parent's
conversation — a fresh agent succeeds from the prompt alone:

```
Audit the agent skill at <ABS_PATH_TO_SKILL_DIR> in LITE mode.
1. Read and follow /…/auditing-skills/SKILL.md and the reference files it points to.
2. Apply the audit to the target skill only, running every tier INLINE (lite mode —
   do NOT dispatch further subagents). Do not audit other skills.
3. Return ONLY the report in references/report-template.md format:
   verdict, per-dimension scores (/14 with denominator noted), tiers run,
   responsibilities note, and the complete unranked inventory of suggested
   improvements. No transcript.
```

- **Tool scope:** Read/Grep/Glob + Bash (for the Tier 1 script) is enough. Do not
  grant Edit/Write — an auditor reads, it doesn't modify the skill under audit.
- **Return contract:** the report is the only output the parent sees. If a subagent
  returns prose instead of the template, that's a fan-out failure — re-dispatch.
- **Isolation rationale:** parallelism + context savings. Each audit is independent;
  no shared state, so they run concurrently with no ordering.

## Aggregation

Collect the reports and produce an inventory table:

| Skill | Grade | Blocking (0 on Contracts/Security?) | Improvements found |
|---|---|---|---|

Order by grade so the table is scannable — that is presenting a measurement, not
recommending a work order. Do NOT append a suggested sequence, a "start here", or a
promote/retire routing: report each skill's grade and its improvement count, and let the
team decide. Flag Security 0 explicitly (it is a fact about exposure, not a priority call).

## Cost discipline

Tier 0→2 is cheap per skill; run it across the whole inventory in one fan-out wave.
Tier 3 (behavioral paired eval) is expensive — only dispatch it for skills that
survived Tier 0→2 **and** claim to change agent behavior. Don't fan out Tier 3
across an inventory blindly.

**Never nest the two fan-outs.** The per-skill subagents run in **lite** mode (every
tier inline). Do NOT let them spawn the per-dimension `deep` auditors — 20 skills ×
5 auditors = 100 subagents to sweep a small inventory. Per-dimension deep fan-out is
for a single deliberate deep audit, not inventory sweeps.
