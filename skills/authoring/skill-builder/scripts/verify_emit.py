#!/usr/bin/env python3
"""Emission and target verifier for skill-builder (project or personal skills).

Read-only, offline, stdlib-only: no subprocess, no network, no writes, no deletions.

`--personal` selects the personal skills root (~/.claude/skills); otherwise the
project root (<cwd>/.claude/skills, run from the repo root).

Modes:
  verify_emit.py [--personal] <name>              post-emission checks:
    project: .claude/skills/<name>/SKILL.md exists; .agents/skills/<name> is a
             symlink → ../../.claude/skills/<name> resolving to that dir; the
             `## Available Skills` table in AGENTS.md has exactly one `<name>` row.
    personal: ~/.claude/skills/<name>/SKILL.md exists (no symlink, no AGENTS row).
  verify_emit.py --preflight [--personal] <name>  pre-write checks:
    <name> matches [a-z0-9-]{1,64}; <root>/<name>/ does not exist yet.
  verify_emit.py --rework-target <path>           validates a --rework target:
    <path> resolves under .claude/skills/ OR ~/.claude/skills/, has a SKILL.md,
    and is not `skill-builder`/`auditing-skills` (reworking the gate with the
    gate is a conflict of interest → human review).
  verify_emit.py --containment [--personal] <name> <path> [<path>...]
    every <path> must resolve under $DEST/<name>/, or (project only) be exactly
    the symlink .agents/skills/<name> or the repo-root AGENTS.md.

Usage: python3 scripts/verify_emit.py
       [--preflight|--rework-target|--containment] [--personal] <name|path> [paths...]
Exit:  0 all checks pass | 1 a check failed | 2 usage or wrong cwd
"""
import os
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"[a-z0-9-]{1,64}")
GATE_SKILLS = ("skill-builder", "auditing-skills")


def available_skills_section(agents_text):
    m = re.search(r"^## Available Skills\s*$(.*?)(?=^## |\Z)", agents_text,
                  re.MULTILINE | re.DOTALL)
    return m.group(1) if m else None


def check_emitted_project(name, root):
    failures = []
    skill_md = root / ".claude" / "skills" / name / "SKILL.md"
    if not skill_md.is_file():
        failures.append(f"missing {skill_md.relative_to(root)}")
    link = root / ".agents" / "skills" / name
    expected = f"../../.claude/skills/{name}"
    if not link.is_symlink():
        failures.append(f".agents/skills/{name} is not a symlink "
                        f"(create it: ln -s {expected} .agents/skills/{name})")
    else:
        target = os.readlink(link)
        if target != expected:
            failures.append(f".agents/skills/{name} points to '{target}', expected '{expected}'")
        elif not link.resolve().is_dir():
            failures.append(f".agents/skills/{name} target does not resolve to a directory")
    section = available_skills_section((root / "AGENTS.md").read_text(encoding="utf-8"))
    if section is None:
        failures.append("AGENTS.md has no `## Available Skills` section")
    else:
        rows = re.findall(rf"^\|\s*`{re.escape(name)}`\s*\|", section, re.MULTILINE)
        if not rows:
            failures.append(f"no `## Available Skills` row for `{name}` in AGENTS.md")
        elif len(rows) > 1:
            failures.append(f"{len(rows)} rows for `{name}` in AGENTS.md; exactly one expected")
    return failures


def check_emitted_personal(name):
    skill_md = Path.home() / ".claude" / "skills" / name / "SKILL.md"
    if not skill_md.is_file():
        return [f"missing ~/.claude/skills/{name}/SKILL.md"]
    return []


def check_preflight(name, base):
    if (base / name).exists():
        return [f"{base}/{name}/ already exists — rework it, don't create over it"]
    return []


def check_rework_target(path_arg):
    roots = [(Path.cwd() / ".claude" / "skills").resolve(),
             (Path.home() / ".claude" / "skills").resolve()]
    target = Path(path_arg).resolve()  # resolves ../ traversal before any check
    rel = None
    for skills_root in roots:
        try:
            rel = target.relative_to(skills_root)
            break
        except ValueError:
            continue
    if rel is None:
        return [f"{path_arg} resolves to {target}, outside .claude/skills/ and ~/.claude/skills/"]
    if rel == Path("."):
        return [f"{path_arg} is a skills root itself, not a skill directory"]
    if rel.parts[0] in GATE_SKILLS:
        return [f"'{rel.parts[0]}' is not a valid rework target — reworking the gate with "
                f"the gate is a conflict of interest; route to human review"]
    if not (target / "SKILL.md").is_file():
        return [f"{path_arg} has no SKILL.md — not a rework target"]
    return []


def check_containment(name, personal, paths):
    """Every path must sit under $DEST/<name>/ or a project install artifact."""
    failures = []
    if personal:
        dest_root = (Path.home() / ".claude" / "skills" / name).resolve()
        allowed_extra = set()
    else:
        root = Path.cwd().resolve()
        if not (root / "AGENTS.md").is_file() or not (root / ".claude" / "skills").is_dir():
            return ["project mode: run from the repo root (expects ./AGENTS.md and "
                    "./.claude/skills/), or pass --personal"]
        dest_root = (root / ".claude" / "skills" / name).resolve()
        allowed_extra = {
            (root / ".agents" / "skills" / name).resolve(),
            (root / "AGENTS.md").resolve(),
        }

    for raw in paths:
        path = Path(raw).resolve()
        try:
            path.relative_to(dest_root)
            continue
        except ValueError:
            pass
        if path in allowed_extra:
            continue
        failures.append(
            f"{raw} resolves to {path}, outside $DEST/{name}/"
            + (" and project install artifacts" if not personal else "")
        )
    return failures


def main():
    args = sys.argv[1:]
    usage = ("Usage: python3 scripts/verify_emit.py "
             "[--preflight|--rework-target|--containment] [--personal] "
             "<name|path> [paths...]")
    mode = "emit"
    for flag in ("--preflight", "--rework-target", "--containment"):
        if flag in args:
            mode = flag[2:]
            args = [a for a in args if a != flag]
    personal = "--personal" in args
    args = [a for a in args if a != "--personal"]

    if mode == "containment":
        if len(args) < 2:
            print(usage)
            return 2
        name, paths = args[0], args[1:]
        if not NAME_RE.fullmatch(name):
            print(f"FAIL  name '{name}' must match [a-z0-9-]{{1,64}}")
            return 1
        failures = check_containment(name, personal, paths)
        ok = (f"OK    {name}: {len(paths)} path(s) inside $DEST/{name}/"
              f"{'' if personal else ' (+ install artifacts)'} "
              f"({'personal' if personal else 'project'})")
    elif mode == "rework-target":
        if len(args) != 1:
            print(usage)
            return 2
        arg = args[0]
        failures = check_rework_target(arg)
        ok = f"OK    {arg}: resolves under a skills root, has SKILL.md, not a gate skill"
    else:
        if len(args) != 1:
            print(usage)
            return 2
        arg = args[0]
        if not NAME_RE.fullmatch(arg):
            print(f"FAIL  name '{arg}' must match [a-z0-9-]{{1,64}}")
            return 1
        if personal:
            base = Path.home() / ".claude" / "skills"
        else:
            root = Path.cwd()
            if not (root / "AGENTS.md").is_file() or not (root / ".claude" / "skills").is_dir():
                print("FAIL  project mode: run from the repo root (expects ./AGENTS.md and "
                      "./.claude/skills/), or pass --personal")
                return 2
            base = root / ".claude" / "skills"
        if mode == "preflight":
            failures = check_preflight(arg, base)
            ok = (f"OK    {arg}: valid name, directory free — clear to write "
                  f"({'personal' if personal else 'project'})")
        elif personal:
            failures = check_emitted_personal(arg)
            ok = f"OK    {arg}: ~/.claude/skills/{arg}/SKILL.md present (personal)"
        else:
            failures = check_emitted_project(arg, Path.cwd())
            ok = f"OK    {arg}: SKILL.md present, symlink exact, AGENTS.md row unique (project)"

    if failures:
        for f in failures:
            print(f"FAIL  {f}")
        return 1
    print(ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
