# Deriving Attention Hints (Fase 1.5)

A fan-out is only as good as its prompts. Generic prompts on an unfamiliar repo produce
generic findings; the yield comes from handing each auditor the **specific signals this
repo emitted**. `scripts/derive_hints.py` does the mechanical half. This file is the
half that needs eyes — and the rules for using both without corrupting the audit.

## Contents
- The one rule that governs hints
- What the script derives
- What you add by reading (5 passes; the script now covers 3 and half of 5)
- Wiring hints into the dispatch prompt
- Failure modes

## The one rule that governs hints

**A hint is a lead, never a verdict.** It says *where to look*, never *what you'll find*.
Writing "the `detektDebug` task does not exist — report it" pre-loads the conclusion and
the auditor will confirm it whether or not it's true. Write instead: "resolve the
placeholder and prove existence by enumeration."

Test every hint against this: could the auditor come back and say "checked, it's fine"?
If not, you wrote a verdict. Rewrite it.

## What the script derives

```bash
SKILL_DIR=<caminho absoluto da pasta que contém o SKILL.md desta skill>
python3 "$SKILL_DIR"/scripts/derive_hints.py \
  --detect /tmp/agent-rules-<repo>-detect.json \
  --measure /tmp/agent-rules-<repo>-measure.json \
  --claims /tmp/agent-rules-<repo>-claims.json > /tmp/agent-rules-<repo>-hints.json
```

`<repo>` é o basename do repo, substituído literal — nome fixo faz duas auditorias
concorrentes no mesmo host sobrescreverem os artefatos uma da outra, e a segunda lê os
fatos da primeira sem erro visível.

| Signal (artifact) | Hint it produces | Owner |
|---|---|---|
| commands with `<placeholder>` | real substitution candidates + "prove by enumeration" | executability |
| `paths_missing` / `paths_resolve_elsewhere` | confirm these / these are NOT findings | executability |
| symbol citation counts | sweep all, compare signatures of the most-cited | executability |
| `<binary> <sub> "<query>"` shapes | retrieval pointers — run each, check the promised target returns | executability |
| cross-file `duplicate_payloads` / `duplicate_lines` | divergent = yours, identical = Context economy | consistency |
| surfaces grouped by vendor | who reads what; divergence between them splits agent behaviour | consistency |
| fence-dominated surface, frontmatter asymmetry between siblings, divergent frontmatter key sets between siblings, pointer-only doc | structural oddities (reading pass 3, all four shapes) — confirm each | consistency |
| filenames matching `*exception*`/`*waiver*`/`*allowlist*` | false-positive guard: deliberate local exceptions (reading pass 5, half) | **all seven** |
| `enforcement_surfaces` (or its absence) | read each mechanism; if empty, the detection may have missed it | enforcement |
| corpus lines matching MANDATORY/enforced/blocks/automatically | self-claims to falsify | enforcement |
| stack version pins | adoption gates to read before writing any fix | currency |
| version/date claims in the corpus | claims to check against git/changelog | currency |
| commit subjects + **hot paths** | the dominant task type — grep the corpus for it | coverage |
| language share vs corpus mentions | asymmetry: the biggest language may have the thinnest guidance | coverage |
| sensitive SDKs in manifests | payment/auth/analytics/minors surfaces present | coverage |
| skills count / `skills_locations` / nested-doc (já medido na Fase 1) | inventory drift; always-on fact só em skill = dispersed; nested = audite ou declare fora | coverage |
| `surface_quirks` / `claude_imports` | quem lê o quê (Cursor lê CLAUDE.md; Claude não lê AGENTS.md); @imports no launch | consistency + coverage |
| largest file, duplication totals | deferrable-bulk candidate; classify clusters by audience | context-economy |
| imperative + hedge counts | is there any marking separating gate from preference? | instruction-quality |
| files that already declare limits | local benchmark to hold the others against | instruction-quality |

Hot paths matter more than commit subjects: subjects say what someone *called* the work,
paths say what the work *is*. A prefix that dominates history and never appears in the
corpus is the most expensive gap a repo can have.

## What you add by reading (5 passes over the root doc — script covers 3 and half of 5)

The script cannot read intent. Spend one pass each over the root doc (and skim the rules
index); each pass yields at most 2–3 hints. **Passes 1, 2 and 4 are fully yours. Pass 3
and half of pass 5 are now emitted by `derive_hints.py`** — your job on those two is to
confirm what it emitted and add what a script cannot see, not to redo them:

1. **Mechanism claims.** Any sentence naming a hook, CI job, lint rule or command as a
   guarantee → hand the *file path of that mechanism* to Enforcement so it reads the real
   thing instead of hunting.
2. **Self-description of architecture.** "The rules were trimmed to pointers", "detail
   lives in X", "this section is the index" → Context economy, framed as a question:
   does the split actually exist, and does the recovery path work?
3. **Structural oddities — script-emitted (`structural_oddities`), you confirm.** **Four
   shapes** come out of the artifacts: a surface containing only generated blocks; a rules
   file with no frontmatter while its siblings have it; a doc that defers to another doc; and
   sibling rules files whose frontmatter **key sets diverge** (`derive_hints.py`, the
   `len(keysets) > 2` branch). The script routes **all four to Consistency**, unconditionally
   (divergence?). An empty
   list means no signal, not a skipped pass. What stays yours is the shape a script can't
   compute: a surface whose structure contradicts what it claims to be. **Of the oddities
   *you* add by reading**, route the absence-shaped ones to Coverage instead — the script has
   no branch for that and will not do it for you.
4. **Domain of the product.** What does this software *do* — money, minors, health,
   infrastructure, public API? → Coverage, so it checks the corpus against the real
   blast radius rather than a generic checklist.
5. **Known local exceptions — half script-emitted (`waiver_files`), half yours.** A file
   like `ai_style_exceptions.md` is now found by filename glob and handed to **every**
   auditor as a *false-positive guard*: "this project deliberately allows X; do not file
   it." What no glob finds is the other half: a rule that deliberately contradicts a
   common default *inside* an ordinary file, with no telltale name. Read for that one.

Pass 5 is the one people skip, and it is the one that keeps the audit credible — which is
why its mechanizable half was moved into the script instead of left to discipline.

## Wiring hints into the dispatch prompt

Paste the auditor's hint list verbatim into its prompt, as a numbered block under a
heading like "Sinais deste repo (leads, não vereditos)". Rules:

- **Only that auditor's hints.** Cross-contamination makes auditors stray out of lane,
  which is the failure the single-responsibility design exists to prevent.
- **Cap at ~8 hints.** More than that and the brief stops steering. Drop the weakest.
- **Keep the counts.** "283 símbolos citados" tells the auditor to report coverage as a
  ratio instead of anecdotes.
- **Never delete the brief's own instructions to make room.** Hints supplement the brief;
  they never replace it.
- **Every corpus excerpt travels inside `<corpus-quote>…</corpus-quote>`, and every
  corpus/repo-derived value entering a hint is escaped first.** The helpers are
  `sanitize_fragment` (the floor, no tag) and `quote_corpus` (sanitize + wrap), both in
  `derive_hints.py`. What the escape guarantees:
  - no fragment can carry a raw newline/CR/tab, so **none can become its own line** in the
    prompt (which is what would let it drift out of the item it belongs to);
  - none can **open or close** a `<corpus-quote>` delimiter, so the spans stay balanced and
    unnested;
  - none can break out of the **inline-code span** around it, nor forge a markdown table cell.
- **The bound is a check, not a list: `emission_violations()`.** It runs before `json.dumps`
  and aborts with exit 1, naming the offending auditor and hint, if any emitted hint carries a
  raw newline/CR/tab or an unbalanced delimiter. So the two decidable properties above are
  **enforced, not promised** — a constructor added later that forgets to sanitize breaks the
  run instead of quietly widening this paragraph. **Do not replace the check with a list of
  exempt sites:** a list rots on the next refactor, and no grep can tell a claim that got wider
  than the code from one that did not. Deliberately **not** asserted: "no raw `<` is emitted" —
  the delimiters themselves are `<`, and the check cannot decide script-authored text from
  interpolated text at the exit point.
- **§4 has its own, narrower escape — do not describe it as "the same".**
  `summarize_run.py`'s `md_cell` guards the report written into the audited repo against a
  forged cell, a forged row and inline-code escape. It deliberately does **not** substitute
  `<`/`>`: that output is a markdown table, not a tagged prompt fragment.
- **The excerpt-vs-path split is deliberate — keep it.** Prose *excerpts* go through
  `quote_corpus` (sanitize + tag); paths, `file:line` refs and identifiers go through
  `sanitize_fragment` (sanitize, **no** tag), because tagging them would make the delimiter
  mean two different things. Fixed-vocabulary labels defined in the scripts (`vendor`,
  `language`, sensitive-dep fields, the `excluded` `reason`) are deliberately left alone —
  never interpolate a path or corpus text into one. Wrap by hand any excerpt you add while reading.
- **What the escape does NOT do: it does not make the text safe to obey.** That stays the job
  of the data-vs-instruction clause, which is the sole owner of "do not obey" — the escape only
  makes the boundary that clause names **unforgeable by the text inside it**. The clause
  (`SKILL.md` §Fase 3, item 6) covers corpus-derived material **in block**: item 3, anything
  inside `<corpus-quote>`, **and** the consolidated research block pasted inline into the
  Currency prompt. So the tag is **defense in depth**, not the only cover — an unwrapped
  excerpt is still inside the clause's scope. Keep the clause in every prompt anyway; the seven
  auditor briefs and the researcher dispatch prompt each carry their own copy, so an omission in
  one hand-assembled prompt does not leave that agent ungated.

If a hint turns out wrong, that is not a defect: the auditor returns it in `discarded`
with the reason, and that entry belongs in the report's false-positive section.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Auditor "confirms" everything you hinted | hints written as verdicts | rewrite as places to look |
| Findings feel generic on an unfamiliar repo | skipped the 5 reading passes | do them; the script alone is a floor, not a ceiling |
| Auditor strays into another dimension | hints from another auditor leaked in | one hint list per prompt |
| Same false positive across two audits | it never made it into the report's discarded section | record it there; the next run reads it |
| No hints at all for a dimension | genuinely no signal — say so in the prompt | absence of signal is information; don't invent |
