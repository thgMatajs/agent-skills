#!/usr/bin/env python3
"""Resolve an optional jira-figma-context skill directory.

Prints one absolute path to stdout. Read-only, offline, stdlib-only.

Looks for SKILL.md + scripts/fetch_jira_context.py in:
  1. sibling of this skill (catalog / npx install)
  2. ~/.agents/skills/jira-figma-context
  3. <cwd>/.agents/skills/jira-figma-context
  4. ~/.claude/skills/jira-figma-context
  5. <cwd>/.claude/skills/jira-figma-context
  6. ~/.cursor/skills/jira-figma-context
  7. <cwd>/.cursor/skills/jira-figma-context

Usage: python3 scripts/resolve_context_pack.py
Exit:  0 printed a path | 1 skill not found (caller must degrade, not abort)
"""
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
NAME = "jira-figma-context"


def is_pack(path: Path) -> bool:
    return (
        (path / "SKILL.md").is_file()
        and (path / "scripts" / "fetch_jira_context.py").is_file()
    )


def candidates():
    home = Path.home()
    cwd = Path.cwd()
    yield SKILL_DIR.parent / NAME
    yield home / ".agents" / "skills" / NAME
    yield cwd / ".agents" / "skills" / NAME
    yield home / ".claude" / "skills" / NAME
    yield cwd / ".claude" / "skills" / NAME
    yield home / ".cursor" / "skills" / NAME
    yield cwd / ".cursor" / "skills" / NAME


def main():
    seen = set()
    for raw in candidates():
        path = raw.resolve()
        if path in seen:
            continue
        seen.add(path)
        if is_pack(path):
            print(path)
            return 0
    print(
        "jira-figma-context not found. Skip the Context Pack and continue the review.\n"
        "Install it next to power-review when you want ticket/Figma context.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
