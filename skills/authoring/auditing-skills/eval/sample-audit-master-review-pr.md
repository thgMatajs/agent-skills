> ⚠️ **Amostra PRÉ-MUDANÇA (2026-07-23).** Foi gerada quando o template pedia "top-3 fixes
> ranqueados por alavancagem". O formato atual exige inventário COMPLETO e SEM ordem de
> prioridade — ver `references/report-template.md`. Mantida como registro histórico.

# Sample audit — master-review-pr (real skill, 2026-07-23)

Ran `auditing-skills` (lite mode, advisor forbidden) against the user's global skill
`~/.claude/skills/master-review-pr` (381-line SKILL.md + 3 references + docs, ~7.2k tok).

## Result: Verdict C, 9/14 (64%), no cap

| Dimension | Score | Headline |
|---|---|---|
| Directness | 1 | hype padding + SOLID/DRY restated + rules duplicated SKILL.md↔deep-analysis |
| Clarity | 1 | **dead persona reference** (SKILL.md:31 → `senior-mobile-engineer.md`, `code-quality-checklist.md` don't exist); empty "apply church config" stubs; hardcoded personal path |
| Routing | 1 | description opens with capability dump, not "Use when…" (concrete trigger list saves it from 0) |
| Contracts & subagent-prompt | 1 | no `allowed-tools` in frontmatter; subagent tool scope unspecified. Return contract (mandatory table) is strong |
| Scope & refactorability | 1 | auto-detect (§1) + module map (§7) = deterministic prose → should be a script; build/visual + reviewer-etiquette lean separable |
| Efficiency | 2 | exemplary progressive disclosure + explicit context-budget rules |
| Security | 2 | writes gated behind AskUserQuestion; `--force` scoped to /tmp worktree; no injection/exfil |

Top-3 fixes (~35 min → A/12): (1) fix dead persona reference; (2) add scoped
`allowed-tools`; (3) rewrite description as "Use when…".

## Independent verification (by the orchestrator, against source)

**Confirmed TRUE:**
- Dead persona reference — `senior-mobile-engineer.md` + `code-quality-checklist.md` MISSING. ✓
- No `allowed-tools` in frontmatter. ✓
- Description opens "The most thorough…" (capability dump), not "Use when…". ✓
- Hardcoded path `/Users/thg.inchurch/StudioProjects/inchurch-app-main` (SKILL.md:349). ✓
- Strong progressive disclosure + gated writes. ✓

**INACCURATE (confabulation caught):**
- The audit said the Tier 1 placeholder ERROR was "TODOs at lines 158 & 384". FALSE —
  the actual match is `#XXX` at **line 96** ("PR #XXX para sua branch", a PR-number
  placeholder in an example). The auditor cited a location it did not read, violating
  the skill's own "confirm each mechanical lead by reading" rule. Conclusion (benign)
  right; evidence wrong.

## Lessons for the skill

1. **Residual limitation:** even under the structured process, an auditor can confabulate
   the *specifics* of a mechanical lead. The "confirm by reading" instruction isn't
   self-enforcing — a verify step (quote the actual matched line) would harden it.
2. **Minor script FP mode:** `#XXX` used as an illustrative placeholder in an example
   trips the `\bXXX\b` placeholder check. Candidate refinement: ignore XXX inside an
   obvious example string, or downgrade XXX-only matches to WARN.
