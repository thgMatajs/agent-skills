# Branches — classifier and per-branch decisions

**Classifier (the five questions): create mode only**, asked one per turn at interview
start; each opens a branch, or doesn't. In `--rework`, skip the classifier and load the
table of any branch the improvement inventory touches. For every opened branch, its
table below lists the decisions that must exist in the decision record before anything
is written. The capability contract at the bottom binds **every emitted script, in both
modes**.

| # | Question | Opens |
|---|---|---|
| 1 | When must it fire? Name concrete symptoms, inputs, phrases a user would type. | — |
| 2 | What does it receive, and what does it hand back? | **template**, if the output has a fixed shape |
| 3 | Does it orchestrate? Invoke other skills, dispatch subagents, fan out over N items? | **orchestration** |
| 4 | Does it touch external state? Writes files, runs builds, hits network/MCP, ingests third-party text? | **guardrails** |
| 5 | Does it repeat deterministic logic? Arithmetic, parsing, path resolution, timestamp comparison? | **script** |

## Branch: template

A fixed output shape ships as a shape, not as prose about the shape: a fenced skeleton
in the generated `SKILL.md`, or a `references/` template the skill fills in. Decide
which of the two, and decide what every slot means.

## Branch: orchestration

| Must be decided | Why it matters |
|---|---|
| Declared fan-out ceiling, and behavior above it | An uncapped fan-out is the single largest cost risk in an orchestrator |
| Per-dispatch contract: literal prompt, tool scope, return shape | "Delegate it to a subagent" with no prompt returns free prose the caller can't validate |
| Failure branch per chained skill + existence check on the previous artifact | Otherwise one silent failure degrades the whole run with no diagnostic |
| Which side owns each seam | Two skills both assuming authority is how contradictions ship |
| Artifact path **per invocation**, if a chained skill is called more than once | A fixed output path means call N+1 overwrites call N |

Draw the call chain now, following the format in
`$GATE/references/call-chain.md` (same root `resolve_gate.py` printed in Step 0).
Junctions are cheap to fix before a line exists and expensive after.

## Branch: guardrails

| Must be decided | Why it matters |
|---|---|
| Injection guard, if it ingests third-party text | Jira/PR/wiki text is writable by anyone with board access |
| `allowed-tools` limited to what the body actually calls | It does **not** restrict anything — it *pre-approves*, removing the permission prompt |
| `disallowed-tools` for what must never be callable | This is the only field that actually restricts |
| Non-obvious prerequisites, declared | An MCP connector, a binary, a credential — absent, the skill fails with no explanation |

Prose is never a gate for an irreversible action. "Never commit" in the body plus
`Bash(git *)` in the frontmatter means committing runs *without asking*.

## Branch: script

Open it only when the logic is genuinely deterministic **and** repeated. In doubt, the
default answer is **no script**: skills shipping scripts are measurably more likely to
carry a vulnerability (2.12×, n=31,132), and the auditor reads the script too.

When it opens, settle input, output and error contract first, then write the file
**minimal and functional**. Never a stub — `audit_writing.py` treats `TODO`/placeholders
in prose as ERROR and `audit_structure.py` treats a dead link as ERROR, so a stub fails
the gate.

**Capability contract — every Python 3 script this skill writes or edits, in either mode
(not only when this create-mode branch opened), satisfies all six:**

| Constraint | Meaning |
|---|---|
| stdlib only | no third-party imports, nothing to install |
| offline | no sockets, no network modules (`urllib`, `http.client`, `socket`) |
| no process escape | no `subprocess`, no `os.system`, no `eval`/`exec` |
| scoped writes | reads and writes only under the target skill directory; never deletes |
| no secret reach | never reads env vars, keychains, or files outside the target directory |
| declared I/O | argv contract, output shape and non-zero exit on failure, stated in the docstring |
