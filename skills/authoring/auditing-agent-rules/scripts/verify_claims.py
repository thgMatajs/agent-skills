#!/usr/bin/env python3
"""Phase 1 — extract every checkable claim from the corpus and resolve the cheap ones.

Usage:
  python verify_claims.py --from-detect <detect_stack.json> [--repo <root>]
  python verify_claims.py --repo <root> <file.md> [<file2.md> ...]

Emits JSON on stdout with three claim classes:
  paths_missing   — CANDIDATES: a path-shaped token that does not resolve; the auditor
                    must confirm by ls/Read before it becomes a finding
  commands        — candidates the executability auditor must RUN (this script never runs them)
  symbols         — code identifiers the executability auditor must GREP for

This script never executes anything it extracts. Extraction is deterministic;
verification is the auditor's job, under the evidence rule.
"""
import json
import os
import re
import sys

RUNNERS = (r"\./gradlew", r"gradlew", r"npm", r"pnpm", r"yarn", r"bun", r"npx", r"make",
           r"just", r"task", r"python3?", r"pytest", r"tox", r"uv", r"poetry", r"pip",
           r"go", r"cargo", r"swift", r"xcodebuild", r"fastlane", r"pod", r"bundle",
           r"rake", r"dotnet", r"flutter", r"dart", r"mvn", r"docker", r"kubectl",
           r"terraform", r"ruff", r"eslint", r"biome", r"prettier", r"swiftlint",
           r"ktlint", r"detekt", r"golangci-lint", r"rubocop", r"tsc", r"deno", r"gh",
           r"pre-commit", r"lefthook", r"composer", r"php", r"cmake", r"bazel",
           # `curl … | bash` is the anchor pattern of the rubric's worst security band. It was
           # missing here, so an audit run with this skill could never REPORT one sitting in
           # the corpus. Extraction only — this script still executes nothing.
           r"curl", r"wget")
COMMAND_RE = re.compile(r"^\s*(?:\$\s*)?((?:%s)\b[^\n#]*)" % "|".join(RUNNERS))
INLINE_RE = re.compile(r"`([^`\n]{2,160})`")
PATH_EXTS = (".md", ".kt", ".kts", ".swift", ".py", ".ts", ".tsx", ".js", ".jsx", ".go",
             ".rs", ".rb", ".java", ".json", ".yml", ".yaml", ".toml", ".xml", ".gradle",
             ".sh", ".plist", ".txt", ".sql", ".env", ".cfg", ".ini", ".dart", ".php")
SYMBOL_RE = re.compile(r"^[A-Z][A-Za-z0-9_]{2,}(?:\(\)?)?$|^[a-z][A-Za-z0-9_]{2,}\(\)?$")
# Prose surfaces to extract claims from. `.mdc` (Cursor rules, detect_stack.py:66) is prose
# too: filtering on `.md` alone yielded zero commands/paths/symbols for a Cursor corpus.
PROSE_EXTS = (".md", ".mdc", ".txt")
PLACEHOLDER = ("<", ">", "{", "}", "*", "XXXXX", "…", "$", "..")


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def looks_like_path(token):
    """Conservative: needs a directory separator AND a file extension (or trailing /).

    Bare filenames and org/repo slugs are excluded on purpose — they produce false
    'missing path' findings, and a false finding costs more than a missed one.

    Single-segment directory tokens (`/api/`, `/v1/`, `docs/`) are excluded for the same
    reason: they are indistinguishable from URL path fragments quoted in prose, which is
    how `/api/` in "fixes duplicate `/api/` in URL paths" became a false hard finding.
    A directory a corpus genuinely points at almost always has depth >= 2 or an extension.
    """
    if any(ch in token for ch in PLACEHOLDER) or " " in token or '"' in token:
        return False
    if token.startswith(("http", "mailto", "git@")):
        return False
    if "/" not in token:
        return False
    if token.endswith(PATH_EXTS):
        return True
    if token.endswith("/"):
        return len([seg for seg in token.split("/") if seg]) >= 2
    return False


def extract(rel, text):
    commands, paths, symbols = [], [], []
    in_fence = False
    for line_no, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:                                  # fenced block → commands only
            match = COMMAND_RE.match(line)
            if match:
                commands.append({"command": match.group(1).strip(),
                                 "where": f"{rel}:{line_no}"})
            continue
        for token in INLINE_RE.findall(line):         # inline code spans
            token = token.strip()
            if COMMAND_RE.match(token):
                commands.append({"command": token, "where": f"{rel}:{line_no}"})
            elif looks_like_path(token):
                paths.append({"path": token.rstrip(",.;:"), "where": f"{rel}:{line_no}"})
            elif SYMBOL_RE.match(token):
                symbols.append({"symbol": token.rstrip("()"), "where": f"{rel}:{line_no}"})
        bare = INLINE_RE.sub(" ", line)               # drop code spans, already handled
        for token in re.findall(r"(?<![\w/`])(\.?[\w.-]+(?:/[\w.-]+)+\.\w{2,5})", bare):
            if looks_like_path(token):                # bare path in prose
                paths.append({"path": token, "where": f"{rel}:{line_no}"})
    return commands, paths, symbols


SKIP_DIRS = {".git", "node_modules", "build", "dist", ".gradle", "Pods", "vendor",
             ".venv", "venv", "target", ".next", "__pycache__", "DerivedData"}


def build_suffix_index(repo, cap=120_000):
    """basename -> [repo-relative paths]. Lets a cited path resolve from a subtree."""
    index = {}
    seen = 0
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = os.path.relpath(dirpath, repo)
        for name in list(dirnames) + filenames:
            index.setdefault(name, []).append(
                name if rel_dir == "." else os.path.join(rel_dir, name))
            seen += 1
        if seen > cap:
            break
    return index


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2

    repo, targets = os.getcwd(), []
    if args[0] == "--from-detect":
        detect = json.load(open(args[1], encoding="utf-8"))
        repo = detect.get("repo", repo)
        targets = [(s["path"], os.path.join(repo, s["path"]))
                   for s in detect.get("agentic_surfaces", [])
                   if s["path"].endswith(PROSE_EXTS)]
    else:
        if args[0] == "--repo":
            repo, args = os.path.abspath(args[1]), args[2:]
        targets = [(os.path.relpath(a, repo), a) for a in args]
    targets = [(rel, path) for rel, path in targets if os.path.isfile(path)]
    if not targets:
        print("ERROR no readable markdown target", file=sys.stderr)
        return 1

    all_cmds, all_paths, all_syms = [], [], []
    for rel, path in targets:
        cmds, paths, syms = extract(rel, read(path))
        all_cmds += cmds
        all_paths += paths
        all_syms += syms

    subtree_index = build_suffix_index(repo)
    seen, missing, elsewhere, ok = set(), [], [], 0
    for entry in all_paths:
        key = (entry["path"], entry["where"])
        if key in seen:
            continue
        seen.add(key)
        rel_path = entry["path"].lstrip("./")
        if os.path.exists(os.path.join(repo, entry["path"])) or \
           os.path.exists(os.path.join(repo, rel_path)):
            ok += 1
            continue
        hits = subtree_index.get(os.path.basename(rel_path.rstrip("/")), [])
        matches = [h for h in hits if h.endswith(rel_path.rstrip("/"))]
        if matches:
            elsewhere.append({**entry, "resolves_at": matches[:3],
                              "note": "subtree-relative, not repo-root-relative"})
        else:
            missing.append(entry)

    cmd_index = {}
    for entry in all_cmds:
        cmd_index.setdefault(entry["command"], []).append(entry["where"])
    sym_index = {}
    for entry in all_syms:
        sym_index.setdefault(entry["symbol"], []).append(entry["where"])

    result = {
        "repo": repo,
        "files_scanned": [rel for rel, _ in targets],
        "paths_checked": ok + len(missing) + len(elsewhere),
        "paths_ok": ok,
        "paths_missing": missing,
        "paths_resolve_elsewhere": elsewhere,
        "commands": [{"command": c, "cited_at": w[:6], "citations": len(w)}
                     for c, w in sorted(cmd_index.items(), key=lambda kv: -len(kv[1]))],
        "symbols": [{"symbol": s, "cited_at": w[:4], "citations": len(w)}
                    for s, w in sorted(sym_index.items(), key=lambda kv: -len(kv[1]))],
        "next_step": ("paths_missing are CANDIDATES — confirm each by ls/Read, and check the "
                      "citing line means it as a path, before filing. commands MUST be run and symbols "
                      "MUST be grepped by the executability auditor — this script did neither."),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
