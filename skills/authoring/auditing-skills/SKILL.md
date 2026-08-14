---
name: auditing-skills
description: Use when reviewing, triaging, or deciding whether to promote/retire an agent skill (a SKILL.md and its bundled files) — including grading skill quality, checking a skill before merging it, comparing candidate skills, or auditing an inherited skill inventory.
argument-hint: "<skill-dir> [--mode lite|deep]"
---

# Auditing Skills

## Overview

Audit an agent skill the way you'd review code: cheap mechanical checks first,
expensive judgment last, and **stop at the first tier that disqualifies it**. Don't
run a behavioral eval on a skill that shouldn't exist.

You are the **orchestrator**. You run the cheap tiers inline, then dispatch
**specialized auditor subagents** for the expensive judgment — each owns one
responsibility and returns a structured finding-block. You synthesize their blocks
into one verdict. This keeps this file thin and makes the skill dogfood the subagent
contracts it audits.

**Vertical depth beats horizontal breadth.** Grade the skill against *what it claims
to do*, not a fixed suite. Most skills fail on directness, clarity, and scope — not on
structure — so a passing linter proves almost nothing.

## Input

```
auditing-skills <skill-dir> [--mode lite|deep]
```

`<skill-dir>` — path (absolute preferred) of the skill to audit. `--mode` picks the
cost knob defined in "Lite vs deep" below; omitted → `lite`. Callers that need
isolation (e.g. a generator grading its own output) must pass `--mode deep` explicitly.

## Dimensions (score 0–2 each — see `references/rubric.md`)

| Dimension | The question | Owner |
|---|---|---|
| **Directness** | Is every token earning its place? | writing-quality |
| **Novelty** | Does it carry knowledge the model can't infer? (structure ≠ quality) | writing-quality |
| **Clarity & interpretation-safety** | Ambiguity, gaps, wording that leads the agent wrong? | writing-quality |
| **Routing** | Does `description` say *when* to fire (not *what*)? | writing-quality |
| **Contracts & subagent-prompt** | Inputs/outputs/scoped tools/verifiable success; sound subagent prompts? | contracts-subagent |
| **Scope & refactorability** | One coherent job? What prose should be a script/template/contract? | scope-refactorability |
| **Efficiency** | Does loading it pay for itself vs. baseline? | behavioral eval (Tier 3) |
| **Security** | Any *reachable* injection/exfiltration/destructive surface? | security |

## Audit Workflow (cheap → expensive, early-exit)

Copy this checklist; stop at the first tier that disqualifies:

```
Skill Audit: <skill-name>   mode: lite | deep
- [ ] Tier 0: Should this be a skill at all?      (inline)
- [ ] Tier 1: Mechanical scripts                  (inline)
- [ ] Tier 1.5: Trace the call chain              (inline; skip if no chaining)
- [ ] Tier 2: Semantic judgment — 3 auditors      (inline in lite / dispatched in deep)
- [ ] Tier 4: Security                            (inline in lite / dispatched in deep)
- [ ] Tier 3: Behavioral paired eval              (only if survives AND claims behavior change)
- [ ] Synthesize: verdict + scores + complete unranked improvement inventory
```

**Read only what the current tier needs.** Load a brief when you reach its tier, not
up front. For a single-skill audit, do NOT read `inventory-fanout.md` (inventory mode
only), `behavioral-eval.md` (only if Tier 3 actually runs), or `call-chain.md` (only if
Tier 1.5 applies). Reading everything eagerly is the main avoidable token cost.

**Tier 0 — Should this exist? (inline)**
Duplicate of an existing skill → recommend merge, stop. Enforceable by regex/a hook →
recommend automating, stop. One-off/project-specific narrative → not a reusable skill.

**Tier 1 — Mechanical (inline, run both scripts):**
```
python scripts/audit_structure.py <skill-dir>   # frontmatter, naming, <500 lines, dead links, paths
python scripts/audit_writing.py   <skill-dir>   # token counts, hedge/ambiguity, fork-without-join, TODOs
```
An ERROR from either (e.g. broken frontmatter, placeholders in prose) can stop the
audit. Warnings are leads for Tier 2, not verdicts.

**Tier 1.5 — Trace the call chain (inline).** Draw what the skill actually does before
judging what it says. Follow `references/call-chain.md`. Required when the target
dispatches (`Skill`/`Agent`), has a multi-phase workflow, or fans out over N inputs —
that's where orchestrator defects hide, and a linear read misses them. Skip for
single-step/reference skills and say so in the report. **Only ever trace the primary
target**, never per-skill inside an inventory fan-out.

**Tier 2 — Semantic judgment (the differentiator).** Three auditors, each a brief in
`references/auditors/`. Feed each the target dir + the Tier 1 script output + **the
Tier 1.5 call chain** (it tells each auditor *where* its concern sits — dispatch nodes
for contracts, non-consuming phases for scope, external-input nodes for security):
- `writing-quality.md` → Directness, Clarity, Routing
- `contracts-subagent.md` → Contracts & subagent-prompt
- `scope-refactorability.md` → Scope & refactorability

**Tier 4 — Security.** `references/auditors/security.md` → Security (two-stage:
exists vs reachable).

**Tier 3 — Behavioral paired eval.** Only if the skill survived AND *claims to change
behavior*. `references/behavioral-eval.md` + `scripts/paired_eval.py`. Reference skills
are judged on retrieval, not pass-rate gain — skip Tier 3 for them.

## Lite vs deep (cost knob)

- **lite (default):** you run every auditor brief **inline**, in this context. Same
  briefs, no dispatch cost. Right for a single small/medium skill.
- **deep:** dispatch each Tier 2 + Tier 4 auditor as its own subagent (parallel,
  context-isolated). Use for large/complex skills or when you want isolation. Each
  subagent gets a **self-contained** prompt: target path + "read and follow
  `references/auditors/<brief>.md`" + the Tier 1.5 call chain + its return contract.
  Tools: Read/Grep/Glob (+Bash for the script runners). **Never** grant Edit/Write — an
  auditor reads, it doesn't fix.

Draw the call chain **before** dispatching in deep mode — the auditors consume it.

## Auditing a whole inventory (fan-out)

For many skills, dispatch **one subagent per skill** (see `references/inventory-fanout.md`)
and rank by grade. Run those per-skill audits in **lite** mode — do NOT nest the
per-dimension deep fan-out inside the per-skill fan-out; that multiplies subagents and
explodes cost. **Skip Tier 1.5 inside the fan-out** for the same reason: trace the
primary target only. Run Tier 0→2 across the inventory first; reserve Tier 3 for
survivors that claim behavior change.

## Synthesis → the audit report

Merge the auditors' finding-blocks: collect per-dimension scores, apply the grade bands
and the Contracts/Security cap (`references/rubric.md`), and produce the report in
`references/report-template.md` — executive summary, verdict, per-dimension scores, the
**call chain** with its defect markers, the findings, the **dependencies & seams** table
(graded 🔴 Rompido / 🟡 Instável when the skill chains others), what the skill gets right,
a **responsibilities** note, and the **complete inventory of suggested improvements**.

**Never prioritize and never prescribe.** List every improvement you found, unranked — no
"top 3", no ordering by leverage/effort, no "do this first", no verdict on whether the work
is worth doing. The report makes the state legible; the author and the team decide what
happens next. Each item still needs concrete content (what, and where) — an improvement
with nothing actionable in it is noise. Severity on *findings* stays (it describes the
defect's impact); what is forbidden is sequencing the *work*.

**State consequences, not risks.** "Trava em toda invocação" beats "pode causar problemas".
A consequence the reader can picture is what makes a finding actionable without a ranking —
it is the mechanism that replaces prioritization, so it is not optional.

**Reconcile the tree against the scores before writing the verdict.** Every `🔴` in the
call chain must map to a dimension that took a hit, and every dimension scored 0–1
should be locatable in the tree. A mismatch means you mis-scored or mis-traced — fix it
then, not after.

**Report language: always pt-BR (with proper accents).** The delivered report — verdict,
notes, findings, fixes, all prose — is written in Brazilian Portuguese, regardless of the
language of this skill or the skill under audit. The internal machinery (these
instructions, the briefs, the rubric) stays in English; only the final report is
localized. Keep code identifiers, file paths, `file:line` refs, and dimension labels
as-is; translate the surrounding prose.

**Evidence rule (anti-confabulation).** Every finding that cites a `file:line` MUST
quote the actual line verbatim. If you can't quote it, you didn't read it — don't
report it. This applies to mechanical leads too: a script WARN is a *lead*; confirm it
by quoting the line it fired on before you keep or discard it. Citing a location you
didn't read is the failure this rule exists to stop.

## Common Mistakes

- **Treating a green linter as "good."** Structure is Tier 1; skills fail at Tier 2.
- **Running the behavioral eval on every skill.** Only behavior-changing skills earn Tier 3.
- **Nesting deep fan-out inside inventory fan-out.** Inventory audits run lite.
- **Scoring against a generic benchmark.** Grade against the skill's own claim.
- **Auditors straying out of their lane.** Each owns its dimensions only; the orchestrator synthesizes.
- **Judging an orchestrator from a linear read.** Trace it (Tier 1.5) — the defects are in the junctions.
- **Tracing every skill in an inventory.** Primary target only; a fan-out of trees is pure cost.
- **A call chain with only 🔴 and no ✅.** If you validated nothing, you traced but didn't verify.
- **Ranking the fixes or naming a "top 3".** List all of them, unranked; the team sequences the work.
- **Writing "pode causar problemas" instead of the actual consequence.** Without a ranking, the stated consequence is what makes a finding actionable — vagueness there guts the report.
- **Reporting an ungraded seam list on an orchestrator.** Without 🔴 Rompido / 🟡 Instável the reader cannot tell "blocks a run" from "degrades output".
- **Letting pre-existing debt read as the author's.** Attribute it explicitly, or a fair report lands as an unfair one.
