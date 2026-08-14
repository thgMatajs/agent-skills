# Instruction surfaces (as of 2026-08-14)

## Contents
- What is in the spec vs vendor
- Who reads what
- Detector mapping
- Auditor traps

Refresh this file when Fase 2 meta research contradicts it. Primary sources: [agents.md](https://agents.md/), [Claude memory](https://code.claude.com/docs/en/memory), [Cursor rules](https://cursor.com/docs/rules), [Copilot instructions](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions), [Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md).

## What is in the spec vs vendor

`AGENTS.md` is schema-free Markdown. **No required sections.** v1.1 frontmatter is an open proposal, not the live spec. Nested semantics are **not** standardized.

| System | Nested `AGENTS.md` |
|---|---|
| agents.md site | Closest file to the **edited** file wins |
| Codex | Concatenate git-root → **CWD**; later wins; default cap 32 KiB; `AGENTS.override.md` hides `AGENTS.md` in the same dir |
| VS Code Copilot | Nested is **experimental** (`chat.useNestedAgentsMdFiles`, default off) |

## Who reads what

| File | Native readers | Does not load unless |
|---|---|---|
| `CLAUDE.md` / `.claude/CLAUDE.md` | Claude Code; Cursor (always-on, Help/CLI) | — |
| `AGENTS.md` | Codex, Cursor, Copilot cloud agent/review, Antigravity, Cline, Windsurf | **Claude Code** — `@AGENTS.md` or symlink. **Gemini CLI** — `context.fileName`. **Copilot Chat on github.com** — never |
| `GEMINI.md` | Gemini CLI (default), Antigravity, Copilot cloud agent (root) | — |
| `.claude/rules/*.md` | Claude Code. Unscoped = always-on. Scoped via YAML `paths:` (not `globs`) | Skills are on-demand; do not put always-on facts only in a skill |
| `.cursor/rules/*.mdc` | Cursor. Four modes: `alwaysApply` / `globs` / `description` / manual `@` | Plain `.md` in that folder is **ignored** |
| `.github/copilot-instructions.md` + `.github/instructions/*.instructions.md` | Copilot (feature-dependent). Path files use `applyTo` | github.com Chat skips path-specific files and `AGENTS.md` |
| `.devin/rules/*.md` | Windsurf/Devin **preferred** | `.windsurf/rules/` is fallback; `.windsurfrules` still read |
| `.clinerules/` (dir) or `.cline/rules/` | Cline | File `.clinerules` is legacy-style; both layouts appear in Cline docs |
| `.agents/rules/` | Antigravity | Not `.gemini/rules/` (that path is unofficial) |
| `.continue/rules/*.md` | Continue.dev | Do not assume Continue injects `AGENTS.md` |
| `.cursor/BUGBOT.md` | Cursor Bugbot only | `.mdc` project rules **do not** apply to Bugbot |
| `.codex/config.toml` / `.codex/rules/` | Codex config, not the AGENTS.md walk | Team instructions live in `AGENTS.md` |

Claude `@path` imports expand at launch (max 4 hops) and **still cost tokens**. Nested `CLAUDE.md` loads on **Read**, not at launch from repo root, and is **not** re-injected after `/compact`. Explore/Plan subagents **skip** CLAUDE.md.

## Detector mapping

`detect_stack.py` puts root files, vendor rule dirs, **nested** `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`, nested `.cursor/rules` in packages, Claude `@imports` that resolve in-repo, and skills under `.claude/skills`, `.agents/skills`, `.cursor/skills`, `.codex/skills`, `.gemini/skills` into `agentic_surfaces`.

`surface_quirks` are dated facts for auditors, not findings.

## Auditor traps

- Do **not** file “AGENTS.md missing section X” — the spec forbids required sections.
- Do **not** treat `AGENTS.md` × `CLAUDE.md` identical copies as waste if they serve different agents — unless Cursor/VS Code will load **both** (then it is always-on duplication for that agent).
- Do **not** treat Gemini `AGENTS.md` as loaded without `context.fileName`.
- Do **not** treat a `.md` in `.cursor/rules/` as active Cursor guidance.
- Procedures belong in skills; always-on facts belong in CLAUDE.md / AGENTS.md / scoped rules.
- Codex 32 KiB combined (docs also say per-file — flag truncation, don't pick a wording).
