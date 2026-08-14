# agent-skills

Agent skills and agents rules.

Install with the [Vercel skills CLI](https://skills.sh/):

```bash
npx skills add thgMatajs/agent-skills
```

Pick the skills you want, and which coding agents to install them on.

## Authoring

| Skill | What it does |
| --- | --- |
| [`auditing-skills`](./skills/authoring/auditing-skills) | Grades a `SKILL.md` (structure → writing → contracts → security). |
| [`skill-builder`](./skills/authoring/skill-builder) | Creates or reworks a skill and gates emission on `auditing-skills`. |

`skill-builder` needs `auditing-skills` installed next to it. Install both:

```bash
npx skills add thgMatajs/agent-skills --skill auditing-skills --skill skill-builder
```

## Coming next

| Category | Path |
| --- | --- |
| Review | [`skills/review`](./skills/review) |
| QA | [`skills/qa`](./skills/qa) |
| Android | [`skills/android`](./skills/android) |
| Firebase | [`skills/firebase`](./skills/firebase) |

## Layout

Each skill is `skills/<category>/<skill>/SKILL.md`. The CLI discovers that layout automatically.

## Rules

[`rules/`](./rules) is reference material for Claude Code, Codex, Cursor, and other agents. The skills CLI does **not** install this folder. Copy what you need into your agent's rules directory.

## License

[MIT](./LICENSE)
