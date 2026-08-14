# Call-Chain Tracing

Before judging a skill's semantics, **draw what it actually does**. For orchestrator
skills the defects live in the *junctions* — dispatch points, handoffs to chained
skills, unbounded fan-outs — and a linear read of SKILL.md hides them. The tree makes
position visible, which is what turns "this line is wrong" into "this seam is wrong".

## When to trace

**Trace** when the target has any of: `Skill(...)` invocations, `Agent` dispatch, a
multi-phase/numbered workflow, or a fan-out over N inputs.

**Skip** when the target is a single-step or pure-reference skill with no chaining —
a tree with four nodes costs tokens and teaches nothing. Note the skip in the report
rather than drawing a trivial tree.

**Cost rule.** Trace **only the primary target**. Never trace per-skill inside an
inventory fan-out (`inventory-fanout.md`) — that multiplies cost with no proportional
gain. In `lite` mode you draw it inline; in `deep` mode you draw it *before* dispatching
the auditors, because they consume it.

## Format

One line per action. Indentation = depth in the recursion. Past tense, as a trace of
one execution. Wrap in `<pre>` (not a fenced block) so the links render.

- Box-drawing: `├──`, `└──`, `│`, and a bare `│` line to separate blocks.
- Skill / script / template names are `<a href="...">` links to their definitions. Use
  **absolute** URLs pinned to the branch under audit when the report will be posted as
  a PR comment — relative links don't resolve there.
- Branches as `[se X → …]` / `[if X → …]`, on their own line at the depth they apply.
- Name the artifact each phase writes, at the node that writes it.

## Audit annotations (what makes this an audit artifact, not documentation)

Two markers, placed on the **exact node** where the thing lives:

- `🔴n` — a defect. Numbered in flow order, not severity order.
- `✅` — something you positively **validated** (ran, measured, or confirmed against
  real data). Without these the tree reads as a pure catalogue of failure and loses
  credibility.

Follow the tree with a legend table: `| # | Node | Defect | Dimension |`. The Dimension
column is what ties the tree back to the scores — every `🔴` must map to a dimension
that took a hit, and any dimension scored 0 or 1 should be findable in the tree. **A
mismatch between the tree and the scores is a signal you mis-scored**, so reconcile
them before writing the verdict.

Close with one sentence on **what the topology shows that the prose didn't** — where
the defects cluster, and therefore whether the problem is the skill's core or its
boundaries. That sentence is usually the most valuable line in the report.

## Feeding the auditors (deep mode)

Pass the finished tree into each Tier 2 / Tier 4 subagent prompt. Each auditor reads
it through its own lens:

| Auditor | What the tree hands it |
|---|---|
| `contracts-subagent` | Every dispatch node and every seam with a chained skill, located |
| `scope-refactorability` | Which phases don't consume the previous phase's output (the tell for a multi-headed skill) |
| `security` | Exactly where external/untrusted text enters the flow |
| `writing-quality` | Which branches are declared vs. left unresolved |

Reference implementation of the format: `skynet/docs/call-chains.md`
(<https://bitbucket.org/inradar/skynet/src/main/docs/call-chains.md>).
