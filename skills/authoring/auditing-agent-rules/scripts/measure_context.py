#!/usr/bin/env python3
"""Phase 1 — measure what the instruction corpus costs and where it repeats itself.

Usage:
  python measure_context.py --from-detect <detect_stack.json> [--repo <root>]
  python measure_context.py <file.md> [<file2.md> ...]

Emits JSON on stdout: per-file size/token estimate, imperative density, and
cross-file duplicated blocks. Deterministic — no judgment, no network.
Token counts are estimates (chars/4); label them as estimates in the report.
"""
import json
import os
import re
import sys
from collections import defaultdict

HEDGE = [r"\busually\b", r"\bprobably\b", r"\bmight\b", r"\bmaybe\b", r"\bas needed\b",
         r"\bif appropriate\b", r"\betc\.", r"\bsomewhat\b", r"\bgenerally\b",
         r"\bshould be fine\b", r"\btry to\b", r"\bwhen possible\b", r"\bwhere sensible\b",
         r"\bnormalmente\b", r"\btalvez\b", r"\bse poss[íi]vel\b", r"\bem geral\b"]
IMPERATIVE = {
    "NEVER": r"\b(never|nunca|jamais)\b",
    "ALWAYS": r"\b(always|sempre)\b",
    "MUST": r"\b(MUST|DEVE|OBRIGAT[ÓO]RI[OA])\b",
    "DONT": r"\b(don't|do not|não\s+(?:use|faça|crie))\b",
}
WINDOW = 3          # lines per shingle
MIN_DUP_LINES = 4   # report clusters at least this long
# Prose surfaces that count as injected context. `.mdc` is Cursor's rules extension, which
# detect_stack.py:66 detects on purpose and which IS injected as prose — measuring only
# `.md` sent those files to `excluded` under a reason that is false for them.
PROSE_EXTS = (".md", ".mdc", ".txt")


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def strip_code(text):
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def normalize(line):
    line = line.strip().lower()
    line = re.sub(r"[`*_>#|\-–—:.,;()\[\]]", " ", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


SPAN_RE = re.compile(r"`([^`\n]{8,200})`")
QUOTED_RE = re.compile(r"\"([^\"\n]{12,200})\"")
MIN_LINE_ECHO = 40      # chars of normalized text before a single line counts as an echo
MIN_PAYLOAD_CHARS = 20  # below this, a payload must look like a command to count
STRUCTURAL = re.compile(r"^(#{1,6}\s|\||\s*[-*+]\s*$|\s*\d+\.\s*$)")
# Same tool invoked with and without its path prefix must collapse to one key.
PATH_PREFIX_RE = re.compile(r"^(?:\./|~/|/)?(?:[\w.-]+/)*")


def payload_key(text):
    """Canonical form of a payload: case-, whitespace- and path-prefix-insensitive.

    `.claude/bin/mem find "x"` and `mem find "x"` are the same instruction written
    twice; keying on the raw span would file them as two distinct payloads.
    """
    text = re.sub(r"\s+", " ", text.strip().lower())
    head, sep, tail = text.partition(" ")
    return (PATH_PREFIX_RE.sub("", head) + sep + tail).strip()


def duplicate_payloads(files):
    """Commands, queries and quoted strings repeated across the corpus.

    Catches what the block detector cannot: the SAME `cmd "query"` carried by rows
    whose surrounding label differs (two index tables with different first columns),
    or the same command restated in a different sentence.
    """
    # Pass 1 — learn this corpus's binaries: any payload written with a path
    # (`.claude/bin/mem find …`) teaches that its last component is a command,
    # so the bare `mem rebuild` elsewhere is kept while `[weak self]` is dropped.
    binaries = set()
    raw = []
    for rel, path in files:
        for line_no, line in enumerate(read(path).splitlines(), 1):
            spans = SPAN_RE.findall(line)
            candidates = list(spans)
            for span in spans:                     # argument survives even when the
                candidates += QUOTED_RE.findall(span)   # command around it is rewritten
            candidates += QUOTED_RE.findall(SPAN_RE.sub(" ", line))
            for text in candidates:
                raw.append((rel, line_no, text))
                head = text.strip().split(" ")[0]
                if "/" in head and len(head.rsplit("/", 1)[-1]) > 1:
                    binaries.add(head.rsplit("/", 1)[-1].lower())

    def is_instruction(text):
        """Command or quoted phrase — not a bare language idiom repeated in prose."""
        key = payload_key(text)
        if '"' in text or len(key) >= MIN_PAYLOAD_CHARS:
            return True
        return key.split(" ")[0] in binaries

    index = defaultdict(list)
    for rel, line_no, text in raw:
        if " " not in text and '"' not in text:
            continue                               # bare identifier — not a payload
        if not is_instruction(text):
            continue                               # code idiom (`.task {}`, `suspend fun`)
        index[payload_key(text)].append(f"{rel}:{line_no}")

    out = []
    for key, hits in index.items():
        if len(set(hits)) < 2:
            continue
        files_hit = sorted({h.rsplit(":", 1)[0] for h in hits})
        out.append({"payload": key[:120], "occurrences": len(hits),
                    "files": files_hit, "cross_file": len(files_hit) > 1,
                    "locations": sorted(set(hits))[:8]})
    return sorted(out, key=lambda p: (-p["cross_file"], -p["occurrences"]))


def duplicate_lines(files, covered):
    """Substantial single lines repeated verbatim, that no 3-line block covers.

    A whole sentence restated in another file is duplication even when the lines
    around it differ — the block detector needs three consecutive matches and
    misses it every time.
    """
    index = defaultdict(list)
    for rel, path in files:
        for line_no, line in enumerate(strip_code(read(path)).splitlines(), 1):
            if STRUCTURAL.match(line):
                continue
            norm = normalize(line)
            if len(norm) < MIN_LINE_ECHO:
                continue
            index[norm].append(f"{rel}:{line_no}")

    out = []
    for norm, hits in index.items():
        hits = sorted(set(hits))
        if len(hits) < 2 or all(h in covered for h in hits):
            continue
        files_hit = sorted({h.rsplit(":", 1)[0] for h in hits})
        out.append({"line": norm[:120], "locations": hits[:8],
                    "files": files_hit, "cross_file": len(files_hit) > 1,
                    "approx_tokens_wasted": round(len(norm) / 4) * (len(hits) - 1)})
    return sorted(out, key=lambda d: -d["approx_tokens_wasted"])


def always_on(meta):
    """Three-valued load classification per surface, plus the basis for it.

    Deliberately NOT a boolean. Whether the harness honours the scoping metadata a
    rules file declares is a runtime verdict the Context-economy auditor must state and
    justify (`context-economy.md` §1); a bare `true/false` here would assert it silently
    and turn a judgment into a fact the report can't defend.
    """
    if not meta:
        return "desconhecido", "arquivo medido direto por caminho — sem metadado de superfície"
    notes = meta.get("notes") or []
    if "cursor-ignores-plain-md" in notes:
        return "não", "cursor-ignores-plain-md — Cursor ignora .md em .cursor/rules/; não entra no contexto"
    kind = meta.get("kind")
    if kind == "root-doc":
        return "sim", "root-doc — injetado em toda sessão do agente que o lê"
    if kind == "nested-doc":
        return "condicional", ("nested-doc — Claude/Codex/Cursor carregam sob demanda "
                               "ao trabalhar na subárvore, não em toda sessão na raiz")
    if kind == "imported-doc":
        return "sim", "imported-doc — @import no CLAUDE.md entra no contexto no launch"
    if kind == "rules-dir":
        if meta.get("declares_scope"):
            keys = ", ".join(meta.get("frontmatter_keys") or []) or "?"
            return "condicional", (f"rules-dir declara metadado de escopo ({keys}); se o "
                                   "runtime não honra, é always-on — veredito do auditor")
        return "sim", "rules-dir sem metadado de escopo — não há o que o runtime escope"
    if kind in ("agents-dir", "hooks-dir", "commands-dir"):
        return "não", f"{kind} — carregado no despacho/evento, não injetado como prosa"
    return "desconhecido", f"{kind} — determine com o vendor e declare como determinou"


def measure_file(path, rel, meta=None):
    text = read(path)
    prose = strip_code(text)
    lines = text.splitlines()
    counts = {label: len(re.findall(pat, prose, re.IGNORECASE))
              for label, pat in IMPERATIVE.items()}
    verdict, basis = always_on(meta)
    return {
        "path": rel,
        "lines": len(lines),
        "always_on": verdict,
        "always_on_basis": basis,
        "chars": len(text),
        "est_tokens": round(len(text) / 4),
        "code_blocks": text.count("\n```") // 2,
        "headings": len([ln for ln in lines if ln.startswith("#")]),
        "tables": len([ln for ln in lines if ln.strip().startswith("|")]),
        "hedges": sum(len(re.findall(p, prose, re.IGNORECASE)) for p in HEDGE),
        "imperatives": counts,
    }


def duplicate_blocks(files):
    """Shingle non-empty normalized prose lines; report runs repeated across locations."""
    index = defaultdict(list)          # shingle -> [(rel, line_no)]
    per_file_lines = {}
    for rel, path in files:
        raw = strip_code(read(path)).splitlines()
        kept = [(i + 1, normalize(ln)) for i, ln in enumerate(raw)]
        kept = [(n, s) for n, s in kept if len(s) > 25]
        per_file_lines[rel] = kept
        for i in range(len(kept) - WINDOW + 1):
            key = " || ".join(s for _, s in kept[i:i + WINDOW])
            index[key].append((rel, kept[i][0]))

    seeds = {k: v for k, v in index.items() if len(v) > 1}
    used = set()
    clusters = []
    for key, hits in seeds.items():
        signature = tuple(sorted(hits))
        if signature in used:
            continue
        used.add(signature)
        clusters.append({"locations": [f"{rel}:{ln}" for rel, ln in sorted(hits)],
                         "sample": key.split(" || ")[0][:110],
                         "seed_lines": WINDOW})

    # merge clusters that share a location prefix (contiguous duplicated regions)
    merged = defaultdict(lambda: {"locations": set(), "samples": [], "seeds": 0})
    for cluster in clusters:
        bucket = tuple(sorted({loc.split(":")[0] for loc in cluster["locations"]}))
        entry = merged[bucket]
        entry["locations"].update(cluster["locations"])
        entry["seeds"] += 1
        if len(entry["samples"]) < 3:
            entry["samples"].append(cluster["sample"])

    out = []
    for bucket, entry in merged.items():
        approx = entry["seeds"] + WINDOW - 1
        if approx < MIN_DUP_LINES:
            continue
        out.append({
            "files": list(bucket),
            "cross_file": len(bucket) > 1,
            "approx_duplicated_lines": approx,
            "approx_wasted_tokens": approx * 12 * (len(bucket) - 1 if len(bucket) > 1 else 1),
            "samples": entry["samples"],
            "locations": sorted(entry["locations"])[:12],
        })
    return sorted(out, key=lambda c: -c["approx_duplicated_lines"])


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2

    repo = os.getcwd()
    targets = []
    excluded = []
    if args[0] == "--from-detect":
        detect = json.load(open(args[1], encoding="utf-8"))
        repo = detect.get("repo", repo)
        if "--repo" in args:
            repo = args[args.index("--repo") + 1]
        for surface in detect.get("agentic_surfaces", []):
            if surface["path"].endswith(PROSE_EXTS):
                targets.append((surface["path"], os.path.join(repo, surface["path"]),
                                surface))
            else:
                excluded.append({"path": surface["path"],
                                 "lines": surface.get("lines", 0),
                                 "reason": "not a prose surface (.md/.mdc/.txt) — config, hook or "
                                           "script, not injected as prose context; still "
                                           "audited via enforcement_surfaces"})
    else:
        for arg in args:
            targets.append((os.path.relpath(arg, repo), arg, None))

    targets = [t for t in targets if os.path.isfile(t[1])]
    if not targets:
        print("ERROR no readable markdown target", file=sys.stderr)
        return 1

    pairs = [(rel, path) for rel, path, _ in targets]
    per_file = [measure_file(path, rel, meta) for rel, path, meta in targets]
    by_load = defaultdict(int)
    for entry in per_file:
        by_load[entry["always_on"]] += entry["est_tokens"]
    totals = {
        "files": len(per_file),
        "lines": sum(f["lines"] for f in per_file),
        "chars": sum(f["chars"] for f in per_file),
        "est_tokens": sum(f["est_tokens"] for f in per_file),
        "est_tokens_by_load": dict(sorted(by_load.items())),
        "hedges": sum(f["hedges"] for f in per_file),
        "imperatives": {k: sum(f["imperatives"][k] for f in per_file) for k in IMPERATIVE},
    }
    if excluded:
        totals["lines_excluded"] = sum(e["lines"] for e in excluded)
        totals["lines_detected"] = totals["lines"] + totals["lines_excluded"]
    blocks = duplicate_blocks(pairs)
    covered = {loc for b in blocks for loc in b["locations"]}
    result = {"repo": repo, "totals": totals, "per_file": per_file,
              "excluded": excluded,
              "duplicate_blocks": blocks,
              "duplicate_lines": duplicate_lines(pairs, covered),
              "duplicate_payloads": duplicate_payloads(pairs),
              "note": ("est_tokens = chars/4 (estimate). `excluded` lists detected surfaces "
                       "left out of the token accounting — reconcile totals.lines against "
                       "totals.lines_detected before reporting any cost number. "
                       "`always_on` is sim|condicional|não|desconhecido with its basis, and "
                       "totals.est_tokens_by_load sums tokens per class: `condicional` is "
                       "not a runtime verdict — scoped rules (`declares_scope`) and nested-doc "
                       "load on demand. Whether the harness honours that is the "
                       "Context-economy auditor's call, not the script's. "
                       "Three duplication views: "
                       "blocks = contiguous regions; lines = substantial single lines "
                       "repeated verbatim; payloads = same command/query/quoted string "
                       "reused under different surrounding text (tables, restatements).")}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
