#!/usr/bin/env python3
"""Tier 1 structural audit for an agent skill.

Mechanical checks only — the stuff that's regex-enforceable and doesn't need
judgment. Semantic quality (routing, directness, contracts) is NOT checked here;
that's Tier 2, done by a reviewer reading references/rubric.md.

Usage: python audit_structure.py <skill-dir>
Exit codes: 0 = no errors, 1 = errors found (warnings never fail the build).
"""
import re
import sys
from pathlib import Path

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

RESERVED = ("anthropic", "claude")
MAX_NAME = 64          # official spec
MAX_DESC = 1024        # official spec
MAX_BODY_LINES = 500   # official ceiling ("keep SKILL.md body under 500 lines")
TARGET_BODY_LINES = 300  # empirical target (Carey 2026, 673 skills: 100–300 lines)
REF_TOC_LINES = 100    # official: reference files >100 lines need a table of contents


def parse_frontmatter(text):
    """Split off the frontmatter block and parse it as real YAML.

    A naive `key: value` line-splitter (the previous implementation) accepts
    unquoted scalars containing an internal ": " (e.g. a `description` whose
    prose has a "Triggers: ..." clause) — text a real YAML loader rejects with
    "mapping values are not allowed here". A harness that parses frontmatter
    strictly then silently fails to index the skill, while this script reported
    zero errors. Parse with PyYAML so that class of defect is an ERROR here too.
    """
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return None, text, None
    block = m.group(1)
    if not _HAS_YAML:
        # Degraded fallback only — flagged by the caller as a coverage gap.
        fm = {}
        for line in block.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip()
        return fm, m.group(2), "no-yaml-fallback"
    try:
        fm = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        return None, m.group(2), str(exc)
    if not isinstance(fm, dict):
        return None, m.group(2), "frontmatter did not parse to a mapping"
    return fm, m.group(2), None


def audit(skill_dir):
    errors, warnings = [], []
    d = Path(skill_dir)
    skill_md = d / "SKILL.md"
    if not skill_md.is_file():
        return [f"No SKILL.md in {skill_dir}"], []

    text = skill_md.read_text(encoding="utf-8")
    fm, body, yaml_err = parse_frontmatter(text)

    # Frontmatter
    if fm is None:
        detail = f": {yaml_err}" if yaml_err else ""
        errors.append(f"Missing or malformed YAML frontmatter{detail}")
        fm = {}
    elif yaml_err == "no-yaml-fallback":
        warnings.append("PyYAML not installed; frontmatter checked with a naive line-splitter "
                         "that cannot catch invalid YAML (e.g. an unquoted scalar containing ': ')")
    name = str(fm.get("name") or "")
    desc = str(fm.get("description") or "")

    if not name:
        errors.append("Frontmatter missing `name`")
    else:
        if len(name) > MAX_NAME:
            errors.append(f"name >{MAX_NAME} chars")
        if not re.fullmatch(r"[a-z0-9-]+", name):
            errors.append("name must be lowercase letters/numbers/hyphens only")
        if any(w in name.lower() for w in RESERVED):
            errors.append(f"name contains reserved word {RESERVED}")
        # name should match the skill's directory (discoverability/consistency).
        dirname = d.resolve().name
        if dirname and name != dirname:
            warnings.append(f"frontmatter name '{name}' != directory '{dirname}'")

    if not desc:
        errors.append("Frontmatter missing `description`")
    else:
        if len(desc) > MAX_DESC:
            errors.append(f"description >{MAX_DESC} chars")
        # Authority: the official spec requires BOTH what it does AND when to use it
        # ("should include both what the Skill does and when to use it"). All three
        # official examples open with the *what*, then append a "Use when …" clause —
        # so requiring the description to START with "Use when" contradicts the spec
        # and flagged 28/28 skills in this repo. We check for the trigger clause
        # ANYWHERE, and separately flag workflow narration (the real routing defect).
        if not re.search(r"use (this )?when|use for|trigger", desc, re.IGNORECASE):
            warnings.append("description has no trigger clause; add 'Use when …' (what it does AND when)")
        if re.search(r"pipeline:|steps?:|\s→\s|\bthen\b.*\bthen\b", desc, re.IGNORECASE):
            warnings.append("description narrates the workflow; agents shortcut to it instead of reading the body")
        if re.search(r"\b(I |I'll|I can|you can use this)\b", desc):
            warnings.append("description not in third person")

    # Body size — 500 is the official ceiling; 300 is the empirical target
    # (Carey 2026 on 673 skills recommends 100–300 lines; SkillsBench found
    # "comprehensive documentation" yields +0.7pp vs +21.5pp for standard-length).
    n_lines = len(body.splitlines())
    if n_lines > MAX_BODY_LINES:
        warnings.append(f"SKILL.md body {n_lines} lines (>{MAX_BODY_LINES} official ceiling); use progressive disclosure")
    elif n_lines > TARGET_BODY_LINES:
        warnings.append(f"SKILL.md body {n_lines} lines (>{TARGET_BODY_LINES} target); check every section earns its tokens")

    # Structured vs prose — top-quartile skills are ~4:1 structured:prose and 90% use
    # tables (vs 40% of bottom); every bottom-decile skill measured was prose-heavy.
    if n_lines > 150 and not re.search(r"^\s*\|.*\|", body, re.MULTILINE):
        warnings.append("no tables in a long SKILL.md; prefer tables over prose for rules/mappings")

    # Windows paths
    if re.search(r"[A-Za-z0-9_]+\\[A-Za-z0-9_]+\.(md|py|js|sh)", text):
        warnings.append("Windows-style backslash paths found; use forward slashes")

    # Reference links: exist, and are one level deep
    for target in re.findall(r"\]\(([^)]+\.md)\)", body):
        if target.startswith(("http://", "https://")):
            continue
        ref = (d / target).resolve()
        if not ref.is_file():
            errors.append(f"Dead reference link: {target}")
        else:
            ref_text = ref.read_text(encoding="utf-8")
            ref_body = parse_frontmatter(ref_text)[1]
            for nested in re.findall(r"\]\(([^)]+\.md)\)", ref_body):
                if not nested.startswith(("http", "#")):
                    warnings.append(f"Reference {target} links deeper to {nested}; keep refs one level from SKILL.md")
            # Official: "For reference files longer than 100 lines, include a table
            # of contents at the top." Cheap proxy: a Contents/TOC heading or a list
            # of intra-doc anchors in the first 30 lines.
            ref_lines = ref_body.splitlines()
            if len(ref_lines) > REF_TOC_LINES:
                head = "\n".join(ref_lines[:30])
                if not re.search(r"^#{1,3}\s*(contents|table of contents|índice|sumário)\b|\]\(#",
                                 head, re.IGNORECASE | re.MULTILINE):
                    warnings.append(f"Reference {target} is {len(ref_lines)} lines (>{REF_TOC_LINES}) with no table of contents")

    return errors, warnings


def main():
    if len(sys.argv) != 2:
        print("Usage: python audit_structure.py <skill-dir>")
        sys.exit(2)
    errors, warnings = audit(sys.argv[1])
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    if not errors and not warnings:
        print("OK — structural checks passed")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s). "
          f"Structure is Tier 1 only — run Tier 2 semantic review next.")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
