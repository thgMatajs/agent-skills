# Skeleton for a generated SKILL.md

Fill from the decision record. Include a branch section only when its branch opened;
omit closed branches entirely — no empty headings.

```markdown
---
name: <name>                    # [a-z0-9-]{1,64}, equal to the directory name
description: <what it does, one clause>. Use when <concrete triggers, symptoms, phrases the user would type>.
argument-hint: <invocation forms, if the skill takes arguments>
allowed-tools: <only what the body calls, scoped by prefix — this pre-approves, it does not restrict>
disallowed-tools: <what must never run — the only field that restricts>
---

# <name>

<one-paragraph job statement: what it reads, writes or decides>

| Not this skill | Use instead |
|---|---|
| <adjacent job the description could misfire on> | <owning skill> |

## Input

<invocation forms and what each receives; behavior on empty input>

## <core workflow — one section per phase, tables over prose>

## Output

<artifacts and destinations; the exact shape of any structured output>

## Dispatch contracts        <!-- orchestration branch only -->

<per dispatch: literal prompt, tool scope, return shape; fan-out ceiling; failure branch per chained skill>

## Guardrails                <!-- guardrails branch only -->

<injection guard for every ingested third-party text; declared prerequisites; confirmation before irreversible actions>

## Scripts                   <!-- script branch only -->

<per script: argv contract, output shape, error and exit behavior; functional from the first write, never a stub>
```

| Rule | Detail |
|---|---|
| Budget and form | the §"Writing rules" table in the generator's `SKILL.md` is the single source — do not restate its numbers here |
| Mode-scoped sections | a generated skill with more than one mode or phase names, on every section, the mode it belongs to |
| Slots | every `<slot>` above is replaced — none survives into the emitted file |
