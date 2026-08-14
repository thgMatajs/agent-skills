# agent-skills

Agent skills and agents rules.

Install with the [Vercel skills CLI](https://skills.sh/):

```bash
npx skills add thgMatajs/agent-skills
```

Pick the skills you want, and which coding agents to install them on.

## Catalog

Skills live at `skills/<category>/<skill>/SKILL.md`. The CLI discovers that layout automatically.

| Category | Path | Status |
| --- | --- | --- |
| Authoring | [`skills/authoring`](./skills/authoring) | empty |
| Review | [`skills/review`](./skills/review) | empty |
| QA | [`skills/qa`](./skills/qa) | empty |
| Android | [`skills/android`](./skills/android) | empty |
| Firebase | [`skills/firebase`](./skills/firebase) | empty |

## Rules

[`rules/`](./rules) is reference material for Claude Code, Codex, Cursor, and other agents. The skills CLI does **not** install this folder. Copy what you need into your agent's rules directory.

## License

[MIT](./LICENSE)
