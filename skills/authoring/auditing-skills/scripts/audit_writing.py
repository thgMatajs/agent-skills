#!/usr/bin/env python3
"""Tier 2 mechanical signals for writing quality — feeds judgment, never replaces it.

Computes the *countable* part of Directness / Clarity so the reviewer (or the
writing-quality auditor subagent) spends judgment on what's actually ambiguous,
not on counting. Like audit_structure.py, this is Tier 1-mechanical: it flags,
it does not grade.

Scans SKILL.md + references/**.md of a skill dir (skips eval/ fixtures and scripts/).

Usage: python audit_writing.py <skill-dir>
Exit: 0 = no hard defects; 1 = placeholders/TODO found (a real defect in a shipped skill).
"""
import re
import sys
from pathlib import Path

# Hedge words that signal ambiguity — the reader can't tell what to actually do.
HEDGE = [
    r"\busually\b", r"\bmaybe\b", r"\bprobably\b", r"\bmight\b", r"\bsomewhat\b",
    r"\bin general\b", r"\byou can\b", r"\byou may\b", r"\bif needed\b", r"\bas needed\b",
    r"\betc\.?", r"\bor so\b", r"\bsome\b", r"\bvarious\b", r"\ba bit\b",
    r"\bgeralmente\b", r"\btalvez\b", r"\bprovavelmente\b", r"\bàs vezes\b",
    r"\bse necess[áa]rio\b", r"\bvoc[êe] pode\b", r"\bou algo assim\b", r"\bmais ou menos\b",
]
DECISION = [r"\bif\b", r"\bwhen\b", r"\bcase\b", r"\bse\b", r"\bquando\b", r"\bcaso\b"]
RESOLUTION = [r"\belse\b", r"\botherwise\b", r"\bsen[ãa]o\b", r"\bcaso contr[áa]rio\b",
              r"→", r"\bthen\b", r"\bent[ãa]o\b"]
# Hard = almost always unfinished content. Soft = often illustrative (a "#XXX" PR-number
# placeholder in an example is benign), so it warns instead of erroring.
PLACEHOLDER = [r"\bTODO\b", r"\bFIXME\b", r"\bTBD\b", r"\blorem ipsum\b",
               r"<[A-Z_]{3,}>", r"\[FILL[^\]]*\]", r"\[\.\.\.\]"]
SOFT_PLACEHOLDER = [r"\bXXX\b"]

IMPERATIVE_HINT = re.compile(r"^\s*(?:[-*]|\d+\.|#{1,6}\s|```|\|)")  # list/heading/code/table


def strip_code(text):
    """Drop fenced code blocks so prose metrics don't count code lines."""
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def strip_inline_code(text):
    """Drop `inline spans` — used ONLY for the placeholder scan.

    A skill documenting a placeholder convention writes the token inside
    backticks (`TODO`), which is a *reference to* the marker, not unfinished
    work; a real leftover marker is written bare. Inline spans stay in the
    prose used for word counts (they are part of the sentence) — removing them
    only here is what preserves the distinction.
    """
    return re.sub(r"`[^`\n]*`", "", text)


def count(patterns, text, flags=re.IGNORECASE):
    return sum(len(re.findall(p, text, flags)) for p in patterns)


def audit_file(path):
    raw = path.read_text(encoding="utf-8")
    prose = strip_code(raw)
    words = len(re.findall(r"\w+", prose))
    lines = [l for l in raw.splitlines() if l.strip()]
    structured = sum(1 for l in lines if IMPERATIVE_HINT.match(l))
    prose_lines = len(lines) - structured

    findings = []
    # Token proxy (~1.3 tokens/word).
    tok = int(words * 1.3)

    # Instruction-to-noise: prose lines that aren't lists/headings/code.
    if lines:
        noise_ratio = prose_lines / len(lines)
        if noise_ratio > 0.6 and words > 120:
            findings.append(("WARN", f"prose-heavy ({noise_ratio:.0%} non-structured lines); "
                                     f"may explain what the model already knows"))

    # Hedge density (ambiguity).
    hedges = count(HEDGE, prose)
    if words and hedges / words * 100 > 1.5:
        findings.append(("WARN", f"{hedges} hedge/ambiguity words ({hedges/words*100:.1f}/100w) — "
                                 f"vague guidance the agent can interpret several ways"))

    # Heading nesting depth.
    depths = [len(m.group(1)) for m in re.finditer(r"^(#{1,6})\s", raw, re.MULTILINE)]
    if depths and max(depths) >= 4:
        findings.append(("INFO", f"heading depth {max(depths)} (h4+) — deep nesting is hard to navigate"))

    # Long sections (between headings).
    for sec in re.split(r"^#{1,6}\s.*$", raw, flags=re.MULTILINE):
        n = len([l for l in sec.splitlines() if l.strip()])
        if n > 60:
            findings.append(("INFO", f"a section is {n} lines — consider splitting/progressive disclosure"))
            break

    # Fork-without-join: decision cues but no resolution cue nearby.
    dec, res = count(DECISION, prose), count(RESOLUTION, prose)
    if dec >= 3 and res == 0:
        findings.append(("WARN", f"{dec} decision cues (if/when/caso) but no resolution "
                                 f"(else/então/→) — branches may lack a clear join"))

    # Placeholders / TODO — a real defect. Scan prose only (code-fence placeholders are
    # legitimate template syntax) and case-SENSITIVE (markers are uppercase by
    # convention: TODO/FIXME/<ABS_PATH>), so lowercase meta-vars like <dir>/<brief> and
    # the word "todo" in prose don't false-positive.
    scannable = strip_inline_code(prose)
    ph = count(PLACEHOLDER, scannable, flags=0)
    if ph:
        findings.append(("ERROR", f"{ph} placeholder/TODO marker(s) in prose — "
                                  f"unfinished content in a shipped skill"))
    soft = count(SOFT_PLACEHOLDER, scannable, flags=0)
    if soft:
        findings.append(("WARN", f"{soft} 'XXX' marker(s) — unfinished, OR an illustrative "
                                 f"placeholder (e.g. 'PR #XXX'); read the line to tell which"))

    return tok, words, findings


def main():
    if len(sys.argv) != 2:
        print("Usage: python audit_writing.py <skill-dir>")
        sys.exit(2)
    root = Path(sys.argv[1])
    # Exclude eval/ and scripts/ *relative to the scanned root* — so auditing our own
    # skill skips its fixtures, but pointing the script AT a fixture still scans it.
    files = [p for p in sorted(root.rglob("*.md"))
             if not ({"eval", "scripts"} & set(p.relative_to(root).parts[:-1]))]
    if not files:
        print(f"No .md files under {root}")
        sys.exit(2)

    total_tok, errors = 0, 0
    for p in files:
        tok, words, findings = audit_file(p)
        total_tok += tok
        rel = p.relative_to(root)
        print(f"\n{rel}  (~{tok} tokens, {words} words)")
        if not findings:
            print("  ok")
        for level, msg in findings:
            print(f"  {level:5} {msg}")
            if level == "ERROR":
                errors += 1

    print(f"\nTOTAL ~{total_tok} tokens across {len(files)} file(s). "
          f"Mechanical only — feed these into the writing-quality auditor (Tier 2).")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
