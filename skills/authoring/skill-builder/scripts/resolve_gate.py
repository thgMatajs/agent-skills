#!/usr/bin/env python3
"""Resolve the auditing-skills directory that skill-builder's gate needs.

Prints one absolute path to stdout. Read-only, offline, stdlib-only.

Looks for SKILL.md + scripts/audit_structure.py + scripts/audit_writing.py in:
  1. sibling of this skill (catalog, npx install, or ~/.claude/skills siblings)
  2. ~/.agents/skills/auditing-skills  (npx skills add -g)
  3. <cwd>/.agents/skills/auditing-skills
  4. ~/.claude/skills/auditing-skills  (legacy personal)
  5. <cwd>/.claude/skills/auditing-skills

Usage: python3 scripts/resolve_gate.py
Exit:  0 printed a path | 1 gate not found
"""
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
NAME = "auditing-skills"


def is_gate(path: Path) -> bool:
    return (
        (path / "SKILL.md").is_file()
        and (path / "scripts" / "audit_structure.py").is_file()
        and (path / "scripts" / "audit_writing.py").is_file()
    )


def candidates():
    home = Path.home()
    cwd = Path.cwd()
    yield SKILL_DIR.parent / NAME
    yield home / ".agents" / "skills" / NAME
    yield cwd / ".agents" / "skills" / NAME
    yield home / ".claude" / "skills" / NAME
    yield cwd / ".claude" / "skills" / NAME


def main():
    seen = set()
    for raw in candidates():
        path = raw.resolve()
        if path in seen:
            continue
        seen.add(path)
        if is_gate(path):
            print(path)
            return 0
    print(
        "auditing-skills not found. Install it next to skill-builder, e.g.\n"
        "  npx skills add thgMatajs/agent-skills --skill auditing-skills --skill skill-builder",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
