# Severity Model, Evidence Contract & Ranking

Every auditor scores its own findings with this model. The orchestrator re-ranks the
merged set with the same formula, so scores must be comparable across dimensions.

## Contents
- Tiers
- Evidence contract
- Ranking formula
- Confidence
- What is NOT a finding

## Tiers

| Tier | Name | Definition | Weight |
|---|---|---|---|
| **T1** | Executa e falha | Following the instruction yields a command, path, symbol or snippet that fails (not found, doesn't compile, wrong type/arity) | **5** |
| **T2** | Contraditório | Two sources disagree (rule × rule, rule × config, rule × code, doc × doc) and the agent has no way to pick | **4** |
| **T3** | Falsamente garantido | Presented as enforced/measured/mandatory, but nothing enforces it | **3** |
| **T4** | Datado | Was true when written; the ecosystem moved. Split: *decision still holds* vs *decision is now wrong* | **3** |
| **T5** | Lacuna | Absent guidance the stack/domain demands (security, verification, i18n, offline…) | **2** |
| **T6** | Custo | Correct but expensive: duplicated, inert, or prose that duplicates existing enforcement | **2** |
| **T7** | Redigido para induzir erro | Wording an agent can resolve wrongly: load-bearing ambiguity, missing branch, prohibition without positive recipe, description that invites skipping the body | **2** |

A single finding gets exactly one tier — the *mechanism of harm*, not the topic. A
stale version number that makes a command fail is T1, not T4.

## Evidence contract (hard gate)

Every finding carries:

```
where:     <file:line>            # the instruction, not the code it talks about
evidence:  "<verbatim line>"      # copied, not paraphrased
proof:     <how you verified>     # command run + observed output | grep + result | config line read
```

- **No `evidence` quote → drop the finding** (exceto T5 de ausência, carve-out abaixo).
  Citing a location you didn't read is confabulation, and it is the failure mode this
  contract exists to stop.
- **No `proof` → `confidence: 0.4`, and it can never be T1/T2** — **except in the two cases
  declared immediately below (T7 wording, T5 absence), where the named fields *are* the
  proof.** Use the numeric scale below, never `high|medium|low` — those belong to Fase 2
  research only, and a non-numeric `confidence` makes `impact` uncomputable.
- **T7 (instruction quality): the cited line IS the proof.** `evidence` + `occurrences` +
  `samples` satisfy this contract; a T7 finding carrying those three is **not** downgraded to
  `confidence: 0.4`. There is nothing to run — the defect is the wording itself, visible in
  the quoted line. (T7 is capped at weight 2 regardless, so the T1/T2 clause is moot.)
- **T5 absence findings satisfy the contract with `need_evidence` + `absence_proof`**, plus a
  `where` naming the surface where the guidance **should** live, marked `(ausência)`. A gap
  has no line to quote, so `evidence`/`proof` are *replaced*, not waived — and the `where`
  keeps the Fase 4 dedup key (`file:line` + claim) available for absence findings too.
- For T1 on a command: `proof` must contain the command *as the corpus writes it* and
  the observed failure line (e.g. `Task 'detektDebug' not found in project ':shared'`).
- For a **negative claim** ("this task/symbol/file does not exist"), `proof` must be the
  enumeration that proves absence — `<runner> tasks --all`, `--help`, `ls`, or a
  repo-wide grep — not the absence of a positive result from a narrow search.

> **This file is also a machine input — three shapes below are load-bearing.**
> `scripts/summarize_run.py --check` parses them at runtime instead of keeping a copy, so a
> stale duplicate can never disagree with this file: the seven `| **Tn** | … | **weight** |`
> rows of §Tiers, the table whose header starts `| reach |`, and the paragraph starting
> `**confidence**` together with its backticked values (that paragraph wraps across two lines —
> both are read). Reword the prose freely; if you change one of those **shapes**, `--check`
> exits 2 naming what it could not read, rather than silently agreeing with an outdated model.

## Ranking formula

```
impact = tier_weight × reach × confidence
```

**reach** — how often the defective instruction is actually hit:

| reach | Scope | Example |
|---|---|---|
| 3 | every task in the stack | e.g. a post-change verification step, a commit rule, a core naming convention |
| 2 | every task in one area | e.g. one platform, one layer, one feature type |
| 1 | rare / narrow | e.g. one component's parameter list, an edge case |

**confidence** — `1.0` verified (proof present), `0.7` strong indirect evidence,
`0.4` single secondary source or unrun claim. Anything at `0.4` is reported as a
*suspicion*, labelled as such.

Report the three factors alongside the score. A reader who disagrees with a weight must
be able to recompute the row without rerunning the audit.

**Ties stay tied.** Show the tie, don't invent a differentiator.

**No sequencing.** The ranking measures impact only. Never emit an execution order,
wave plan, effort-based ordering or "start here" — that is the human's decision, and
inventing it is a rule violation, not a bonus.

## Confidence and the ecosystem-vs-repo distinction (T4)

Before filing a T4, answer: *can this repo even use the newer thing?* Check the pinned
version, the language/platform target, the support matrix.

- Repo **cannot** adopt it → the guidance is still correct; only its *justification* is
  stale. File as T4 with `sub: justification-only`, reach usually 1.
- Repo **can** adopt it and the rule forbids/ignores it → T4 `sub: decision-wrong`.
- Recommending something the repo cannot compile is itself a defect — don't create one
  while auditing.

## Calibration anchors (from a real audit — JVM/Gradle + Swift repo)

Use these to check your own scoring before writing the report. All seven were verified
findings; the ordering below is what the formula must reproduce.

| impacto | Tier | Finding | tier×reach×conf |
|---|---|---|---|
| 15 | T1 | `<module>:detektDebug` prescribed as MANDATORY post-change step; task doesn't exist (`task 'detektDebug' not found in project ':shared'`) | 5×3×1.0 |
| 15 | T1 | `<module>:testDebugUnitTest` prescribed for the KMP module; real task is `testAndroidHostTest` | 5×3×1.0 |
| 8 | T2 | Deployment target stated as 15.0+ in two root docs; project + lint config say 16.0 | 4×2×1.0 |
| 6 | T3 | Method-length/param-count limits listed under "enforced"; both rules are `active: false` in the lint config | 3×2×1.0 |
| 5 | T1 | Documented dialog parameter typed `UIImage?`; the real init takes a non-optional `String` asset name | 5×1×1.0 |
| 4 | T6 | Critical-rules block duplicated verbatim across two root docs with the same content | 2×2×1.0 |
| 3 | T4 | A library's stable-release month cited wrong; no behavioural consequence → trivia | 3×1×1.0 |

What the anchors teach: **reach separates T1s**. A broken command every task touches
outranks a broken API in one component by 3×, and a stale date sits below a duplication —
if your ranking inverts any of those, re-read the reach table.

## What is NOT a finding

- **Preference.** The rule picks one of two valid options (one of two overloads, one of
  two equivalent idioms). Convention, not defect — unless it contradicts code/config.
- **Style you'd write differently.** Not your corpus.
- **A script WARN you didn't confirm.** Leads are not findings.
- **`paths_resolve_elsewhere`** from `verify_claims.py` — subtree-relative paths resolve
  fine for a reader, and are never a finding. `paths_missing` is a **candidate**: confirm
  by `ls`/Read that the path truly doesn't exist *and* that the citing line means it as a
  path, before it becomes a finding. A URL fragment quoted in prose (`/api/`, `/v1/`) is
  not a path.
- **Absence of something the stack doesn't have.** No i18n gap in a CLI with no user
  strings.
- **Duplication across surfaces with different audiences**, unless the copies have
  *diverged* — then it's T2 (contradiction), not T6.

Discarded false positives are not deleted: they go to the report's own section, with
the reason. That section is what stops the next audit from re-filing them.
