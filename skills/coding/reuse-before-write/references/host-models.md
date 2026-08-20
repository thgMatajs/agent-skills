# Host models

Read once per run. Substitute into dispatches. Roles stay split even when the parent model is already strong: the parent must not audit in place of the auditor.

| Role | Cursor (`Task` `model`) | Claude Code (`Agent` `model`) | Other hosts |
|---|---|---|---|
| Scout | `composer-2.5-fast` | `haiku` | cheapest isolated agent |
| Auditor | `cursor-grok-4.6-xhigh` | `opus` | strongest isolated agent |

| Host | Scout dispatch | Auditor dispatch |
|---|---|---|
| Cursor | `Task`, `subagent_type` `explore` | `Task`, `subagent_type` `generalPurpose` |
| Claude Code | `Agent` | `Agent` |
| Other | isolated agent, read-only tools | isolated agent, read-only tools |

Cursor `Task` has no per-dispatch tool allowlist. Scouts use `explore` (read-oriented). The auditor uses `generalPurpose` for judgment; the sent prompt is the gate: Read, Grep, Glob only — no Task, Agent, Edit, Write, or Bash. Claude Code: pass `Read, Grep, Glob` as the Agent tool list.

If the host rejects a model id, retry **that** dispatch once with `inherit` (Cursor) or omit `model` (Claude Code). Do not collapse scout and auditor into one dispatch.
