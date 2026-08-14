> ⚠️ **Amostra PRÉ-MUDANÇA (2026-07-23).** Foi gerada quando o template pedia "top-3 fixes
> ranqueados por alavancagem". O formato atual exige inventário COMPLETO e SEM ordem de
> prioridade — ver `references/report-template.md`. Mantida como registro histórico.

# Sample audit — ultra-review (5-agent system, 2026-07-23)

Ran `auditing-skills` (lite, no advisor) on the `ultra-review` multi-subagent PR-review
system. Also validates the v3 improvements (evidence rule + XXX-WARN).

## Discovery: the live install is BROKEN
- `~/.claude/agents/ultra-review-*.md` are **dangling symlinks** → `~/.ultra-review/…` (gone).
- `~/.claude/skills/ultra-review` is empty / a dangling symlink.
- Only readable copy: a **May-21 backup** of the 5 agent defs in `gsd-user-files-backup/agents/`.
- No orchestrator/SKILL.md survives.

Audited the backup's 5 agents (triage, gates, deep, build, conformity) as a multi-subagent system.

## Result: A- definition quality (9/10 applicable) BUT system non-functional → fix-then-keep

| Dimension | Score | Note |
|---|---|---|
| Directness | 2 | tight, imperative, tables |
| Clarity | 2 | crisp taxonomies; inter-agent boundaries policed in-prose |
| Routing | N/A | orchestrator missing — can't judge |
| Contracts & subagent-prompt | 2 | **the star** — all 5: declared inputs, named output schema, validation step, return contract, scoped tools, model tier matched to task (haiku=mechanical, sonnet=reasoning) |
| Scope & refactorability | 2 | textbook separation across 5 single-responsibility agents |
| Efficiency | N/A | no behavioral eval |
| Security | 1 | reachable-but-bounded injection: `triage` reasons over attacker-influenceable PR comments with no data/instruction boundary; bounded by no-write/no-gh scope |
| **Total** | **9/10 applicable = 90% (A)** | but see robustness |

## The killer finding (system robustness)
Every agent hardcodes `~/.ultra-review/engine/...` (validate_schema.py at triage:44,
deep:42, build:39, conformity:57; `02_gates.sh` at gates:11) — **verified absent**. So
`gates` can't run at all and every agent's validation loop errors out. An A-grade
definition set is currently an inert system. Root defect: absolute per-user path as the
sole locator, no env-var/config indirection, no fail-fast.

## Top-3 fixes
1. De-hardcode the engine path (config/env indirection + fail-fast) — turns inert → runnable.
2. Add an injection guard to `triage` (treat comment text as data, never instructions) — Security 1→2.
3. Ship the `agent-output/*` schemas with the agents; fix `build`'s two nits (missing
   "ONLY invoke" guard at build:3; "for now" placeholder at build:48).

## Validation of the v3 improvements (meta)
- **Evidence rule WORKED.** Every finding in this audit quoted the actual line (triage.md:44,
  deep.md:9, conformity.md:54, build.md:48, …). Contrast: the earlier master-review-pr audit
  confabulated a line ("TODOs at 158/384" when the real match was `#XXX` at line 96). The
  added `evidence:` requirement measurably changed behavior on the very next run.
- The audit correctly adapted to a non-SKILL.md target: Tier 1 scripts N/A, Routing N/A,
  subagent-prompt promoted to the star dimension — no forcing, no invented coverage.

## Caveats
- Backup is 2 months stale (May 21); the current ultra-review may differ.
- No orchestrator to audit → routing/end-to-end unassessed.
