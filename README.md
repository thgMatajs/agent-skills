# agent-skills

Skills for AI coding agents — authoring, then (next) review, QA, Android, and Firebase.

Install with the [Vercel skills CLI](https://skills.sh/):

```bash
npx skills add thgMatajs/agent-skills
```

Pick the skills you want, and which coding agents to install them on.

[![skills.sh](https://skills.sh/b/thgMatajs/agent-skills)](https://skills.sh/thgMatajs/agent-skills)

## Authoring

### auditing-skills

Grades a `SKILL.md` (structure → writing → contracts → security) and stops at the first tier that disqualifies it.

**Use when:** reviewing, triaging, or deciding whether to promote or retire an agent skill.

```bash
npx skills add thgMatajs/agent-skills --skill auditing-skills
```

### skill-builder

Creates a skill from an idea, or brings an existing one up to standard (`--rework`). Emission is gated on `auditing-skills`.

**Use when:** "create a skill for X", "fix this skill", `/skill-builder`.

Install **both** (hard dependency):

```bash
npx skills add thgMatajs/agent-skills --skill auditing-skills --skill skill-builder
```

### auditing-agent-rules

Audits a repository's **agent instruction corpus** the way you'd audit code: run it, don't just read it. Finds broken commands, contradictions, unenforced claims, stale ecosystem guidance, coverage gaps, and per-session context cost. Ranks findings by impact — it does not sequence the fix.

**Use when:**

- "Audit our rules" / "are CLAUDE.md and AGENTS.md still accurate"
- Inheriting an unfamiliar repo's agent config
- "Why do our agent rules cost so much"

**Looks at:** `CLAUDE.md` (including `.claude/CLAUDE.md`), nested docs, Claude `@imports`, `AGENTS.md` / `AGENTS.override.md`, `GEMINI.md`, Cursor `.mdc` rules and commands, Copilot / Devin / Windsurf / Cline / Antigravity rule dirs, and skills under `.claude`, `.agents`, `.cursor`, `.codex`, `.gemini`.

**Seven dimensions:** executability, consistency, enforcement, currency, coverage, context economy, instruction quality.

```bash
npx skills add thgMatajs/agent-skills --skill auditing-agent-rules
```

Add `-g` to install for every local agent, not only the current one.

## Review

### power-review

Critical MR/PR or local-branch review. Detects the repo stack and applies matching persona, official docs, and linter. Context pack is token-first (Jira, Linear, Asana, Shortcut, GitHub Issues, Figma) and does not require `jira-figma-context`.

**Use when:** power review, re-review, review this branch, or an MR/PR URL.

```bash
npx skills add thgMatajs/agent-skills --skill power-review
```

## Coming next

| Category | Path |
| --- | --- |
| QA | [`skills/qa`](./skills/qa) |
| Android | [`skills/android`](./skills/android) |
| Firebase | [`skills/firebase`](./skills/firebase) |

## Layout

Each skill is `skills/<category>/<skill>/SKILL.md`. The CLI discovers that layout automatically.

## Rules

[`rules/`](./rules) is reference material for Claude Code, Codex, Cursor, and other agents. The skills CLI does **not** install this folder. Copy what you need into your agent's rules directory.

## License

[MIT](./LICENSE)
