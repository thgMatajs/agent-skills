#!/usr/bin/env python3
"""Phase 0 — inventory the repo: timestamp, stack, agentic surfaces, enforcement surfaces.

Usage: python detect_stack.py <repo-root> [--json-only]

Emits JSON on stdout. Everything here is deterministic; no judgment, no network.
The orchestrator uses `stack` to pick research axes and `agentic_surfaces` as the
audit target set. An empty `agentic_surfaces` means there is nothing to audit.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

# (glob-ish relative path, stack label, optional version-extraction regex)
STACK_MARKERS = [
    ("package.json", "node/js", r'"version"\s*:\s*"([^"]+)"'),
    ("pnpm-lock.yaml", "node/pnpm", None),
    ("yarn.lock", "node/yarn", None),
    ("tsconfig.json", "typescript", None),
    ("pyproject.toml", "python", r'requires-python\s*=\s*"([^"]+)"'),
    ("requirements.txt", "python", None),
    ("setup.py", "python", None),
    ("go.mod", "go", r"^go\s+([0-9.]+)"),
    ("Cargo.toml", "rust", r'edition\s*=\s*"([^"]+)"'),
    ("pom.xml", "java/maven", None),
    ("build.gradle", "jvm/gradle", None),
    ("build.gradle.kts", "jvm/gradle-kts", None),
    ("settings.gradle.kts", "jvm/gradle-kts", None),
    ("gradle/libs.versions.toml", "gradle-version-catalog", r'kotlin\s*=\s*"([^"]+)"'),
    ("Gemfile", "ruby", None),
    ("composer.json", "php", None),
    ("Package.swift", "swift/spm", None),
    ("pubspec.yaml", "dart/flutter", r"sdk:\s*(.+)"),
    ("Dockerfile", "docker", None),
    ("docker-compose.yml", "docker-compose", None),
    ("requirements-dev.txt", "python", None),
    ("mix.exs", "elixir", None),
    ("deno.json", "deno", None),
    ("bun.lockb", "bun", None),
]

# Agentic instruction surfaces. kind: root-doc | nested-doc | rules-dir | vendor-config | skills
# Inventory as of 2026-08-14 — see references/instruction-surfaces.md
AGENTIC_FILES = [
    ("CLAUDE.md", "root-doc", "claude"),
    (".claude/CLAUDE.md", "root-doc", "claude"),
    ("CLAUDE.local.md", "root-doc", "claude"),
    ("AGENTS.md", "root-doc", "generic/agents.md"),
    ("AGENTS.override.md", "root-doc", "codex"),
    ("AGENT.md", "root-doc", "generic"),
    ("GEMINI.md", "root-doc", "gemini"),
    ("QWEN.md", "root-doc", "qwen"),
    (".cursor/BUGBOT.md", "root-doc", "cursor-bugbot"),
    (".cursorrules", "vendor-config", "cursor"),
    (".windsurfrules", "vendor-config", "windsurf"),
    (".clinerules", "vendor-config", "cline"),
    (".aider.conf.yml", "vendor-config", "aider"),
    (".github/copilot-instructions.md", "vendor-config", "copilot"),
    (".gemini/config.yaml", "vendor-config", "gemini-code-assist"),
    (".gemini/styleguide.md", "vendor-config", "gemini-code-assist"),
    (".codex/config.toml", "vendor-config", "codex"),
    (".claude/settings.json", "vendor-config", "claude"),
    (".claude/settings.local.json", "vendor-config", "claude"),
]
AGENTIC_DIRS = [
    (".claude/rules", "rules-dir", "claude", (".md",)),
    (".cursor/rules", "rules-dir", "cursor", (".md", ".mdc")),
    (".cursor/commands", "commands-dir", "cursor", (".md", ".mdc")),
    (".github/instructions", "rules-dir", "copilot", (".md",)),
    (".github/agents", "agents-dir", "copilot", (".md",)),
    (".devin/rules", "rules-dir", "windsurf/devin", (".md",)),
    (".windsurf/rules", "rules-dir", "windsurf", (".md",)),
    (".clinerules", "rules-dir", "cline", (".md", ".txt")),
    (".cline/rules", "rules-dir", "cline", (".md", ".txt")),
    (".agents/rules", "rules-dir", "antigravity", (".md",)),
    (".continue/rules", "rules-dir", "continue", (".md",)),
    (".codex/rules", "rules-dir", "codex", (".md",)),
    (".junie", "rules-dir", "junie", (".md",)),
    (".claude/agents", "agents-dir", "claude", (".md",)),
    (".claude/hooks", "hooks-dir", "claude", (".sh", ".py", ".js")),
]
# Nested copies of these dirs in packages/ (root copies are AGENTIC_DIRS).
NESTED_RULE_DIR_PARTS = [
    ((".cursor", "rules"), "rules-dir", "cursor", (".md", ".mdc")),
    ((".claude", "rules"), "rules-dir", "claude", (".md",)),
    ((".devin", "rules"), "rules-dir", "windsurf/devin", (".md",)),
    ((".windsurf", "rules"), "rules-dir", "windsurf", (".md",)),
    ((".cline", "rules"), "rules-dir", "cline", (".md", ".txt")),
    ((".continue", "rules"), "rules-dir", "continue", (".md",)),
    ((".agents", "rules"), "rules-dir", "antigravity", (".md",)),
    ((".codex", "rules"), "rules-dir", "codex", (".md",)),
    ((".clinerules",), "rules-dir", "cline", (".md", ".txt")),
    ((".cursor", "commands"), "commands-dir", "cursor", (".md", ".mdc")),
]
NESTED_DOC_NAMES = {
    "CLAUDE.md": "claude",
    "CLAUDE.local.md": "claude",
    "AGENTS.md": "generic/agents.md",
    "AGENTS.override.md": "codex",
    "GEMINI.md": "gemini",
}
SKILL_ROOTS = [
    ".claude/skills",
    ".agents/skills",
    ".cursor/skills",
    ".codex/skills",
    ".gemini/skills",
]

ENFORCEMENT_MARKERS = [
    (".editorconfig", "editorconfig"),
    (".eslintrc.json", "eslint"), (".eslintrc.js", "eslint"), ("eslint.config.js", "eslint"),
    ("biome.json", "biome"), (".prettierrc", "prettier"),
    ("ruff.toml", "ruff"), (".ruff.toml", "ruff"), (".flake8", "flake8"),
    ("mypy.ini", "mypy"), (".pylintrc", "pylint"),
    (".golangci.yml", "golangci-lint"), ("clippy.toml", "clippy"),
    (".rubocop.yml", "rubocop"), ("phpstan.neon", "phpstan"),
    ("config/detekt/detekt.yml", "detekt"), ("detekt.yml", "detekt"),
    (".swiftlint.yml", "swiftlint"), ("iosApp/.swiftlint.yml", "swiftlint"),
    (".pre-commit-config.yaml", "pre-commit"), ("lefthook.yml", "lefthook"),
    ("Makefile", "make"), ("justfile", "just"), ("Taskfile.yml", "task"),
    ("analysis_options.yaml", "dart-analyzer"),
]

SKIP_DIRS = {".git", "node_modules", "build", "dist", ".gradle", "Pods", "vendor",
             ".venv", "venv", "target", ".next", "__pycache__", ".idea", "DerivedData"}


def read(path, limit=200_000):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def count_lines(path):
    try:
        with open(path, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


# Frontmatter keys that ask the runtime to LIMIT when a file is loaded. `description`
# and `name` are metadata, not scoping — counting them would inflate `declares_scope`.
SCOPE_KEYS = {"globs", "applyto", "alwaysapply", "paths", "include", "exclude"}
# Prose surfaces whose frontmatter is worth parsing. `.mdc` (Cursor rules, AGENTIC_DIRS
# above) is where `globs:` is MOST common, so excluding it reported a scoped Cursor rule as
# unscoped always-on — a false basis printed into the report as if it were detection.
PROSE_EXTS = (".md", ".mdc", ".txt")


def frontmatter(path):
    """(top-level YAML keys, declares_scope) for a prose surface; (None, None) else.

    Deliberately shallow: the audit needs to know WHICH keys a rules file declares —
    scoping metadata above all — never their values. Indented keys are nested and are
    not top level, so the column-0 anchor is the whole filter.
    Whether the runtime *honours* the scoping it finds is judgment, not detection:
    that verdict belongs to the Context-economy auditor.
    """
    if not path.endswith(PROSE_EXTS):
        return None, None
    lines = read(path, 8_000).splitlines()
    if not lines or lines[0].strip() != "---":
        return [], False
    keys = []
    for line in lines[1:]:
        if line.strip() in ("---", "..."):
            break
        match = re.match(r"([A-Za-z_][\w.-]*)\s*:", line)
        if match:
            keys.append(match.group(1))
    keys = sorted(set(keys))
    return keys, any(k.lower() in SCOPE_KEYS for k in keys)


def git_info(root):
    out = {}
    for key, cmd in (("branch", ["rev-parse", "--abbrev-ref", "HEAD"]),
                     ("head", ["rev-parse", "--short", "HEAD"])):
        try:
            res = subprocess.run(["git", "-C", root] + cmd, capture_output=True,
                                 text=True, timeout=10)
            out[key] = res.stdout.strip() if res.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            out[key] = None
    return out


def find_nested(root, filename, max_hits=40):
    """Nested instruction files (e.g. per-package AGENTS.md) beyond the root one."""
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")]
        if filename in filenames:
            rel = os.path.relpath(os.path.join(dirpath, filename), root)
            if rel != filename:
                hits.append(rel)
        if len(hits) >= max_hits:
            break
    return sorted(hits)


def append_surface(surfaces, seen, rel, kind, vendor, root):
    if rel in seen:
        return
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        return
    keys, scoped = frontmatter(path)
    notes = []
    if vendor == "cursor" and kind == "rules-dir" and rel.endswith(".md") and not rel.endswith(".mdc"):
        notes.append("cursor-ignores-plain-md")
    if rel in (".cursorrules", ".windsurfrules") or rel.endswith("/.cursorrules"):
        notes.append("legacy")
    if os.path.basename(rel) == "AGENTS.override.md":
        notes.append("codex-hides-agents-md-same-dir")
    surfaces.append({"path": rel, "kind": kind, "vendor": vendor,
                     "lines": count_lines(path),
                     "frontmatter_keys": keys, "declares_scope": scoped,
                     "notes": notes})
    seen.add(rel)


def collect_dir_tree(root, rel, kind, vendor, exts, surfaces, seen):
    base = os.path.join(root, rel)
    if not os.path.isdir(base):
        return
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            if name.endswith(exts):
                full = os.path.join(dirpath, name)
                append_surface(surfaces, seen, os.path.relpath(full, root),
                               kind, vendor, root)


def find_nested_vendor_dirs(root, parts):
    """packages/foo/.cursor/rules — skip the repo-root copy already in AGENTIC_DIRS."""
    hits = []
    plen = len(parts)
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")]
        rel = os.path.relpath(dirpath, root)
        rel_parts = () if rel == "." else tuple(rel.split(os.sep))
        if len(rel_parts) >= plen and rel_parts[-plen:] == parts and rel_parts != parts:
            hits.append(rel)
    return hits


AT_IMPORT_RE = re.compile(r"(?<!`)@([A-Za-z0-9_./~-][A-Za-z0-9_./~-]*)")


def claude_imports(root, surfaces):
    """@path imports in CLAUDE.md (not code spans / fences). Claude expands these at launch."""
    found = []
    for s in surfaces:
        base = os.path.basename(s["path"])
        if base not in ("CLAUDE.md", "CLAUDE.local.md"):
            continue
        text = read(os.path.join(root, s["path"]))
        stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        stripped = re.sub(r"`[^`]+`", "", stripped)
        for match in AT_IMPORT_RE.finditer(stripped):
            found.append({"from": s["path"], "import": match.group(1)})
    return found


def collect_skills(root):
    found = []
    seen = set()
    for rel in SKILL_ROOTS:
        base = os.path.join(root, rel)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if os.path.isfile(os.path.join(base, name, "SKILL.md")):
                key = (rel, name)
                if key not in seen:
                    found.append({"name": name, "path": f"{rel}/{name}"})
                    seen.add(key)
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")]
        if os.path.basename(dirpath) != "skills":
            continue
        parent = os.path.basename(os.path.dirname(dirpath))
        if parent not in (".claude", ".agents", ".cursor", ".codex", ".gemini"):
            continue
        rel_base = os.path.relpath(dirpath, root)
        if rel_base in SKILL_ROOTS:
            continue
        for name in sorted(os.listdir(dirpath)):
            if os.path.isfile(os.path.join(dirpath, name, "SKILL.md")):
                key = (rel_base, name)
                if key not in seen:
                    found.append({"name": name, "path": f"{rel_base}/{name}"})
                    seen.add(key)
    return found


def surface_quirks(surfaces):
    """Dated runtime facts for auditors — not verdicts."""
    as_of = "2026-08-14"
    paths = {s["path"] for s in surfaces}
    quirks = []
    if any(p == "AGENTS.md" or p.endswith("/AGENTS.md") for p in paths):
        quirks.append({
            "id": "claude-skips-agents-md",
            "as_of": as_of,
            "fact": "Claude Code does not natively read AGENTS.md; needs @AGENTS.md in CLAUDE.md or a symlink.",
        })
    if "CLAUDE.md" in paths or ".claude/CLAUDE.md" in paths:
        quirks.append({
            "id": "cursor-reads-claude-md",
            "as_of": as_of,
            "fact": "Cursor CLI/Help also injects CLAUDE.md (always-on), alongside AGENTS.md and .cursor/rules.",
        })
    if any("cursor-ignores-plain-md" in s.get("notes", []) for s in surfaces):
        quirks.append({
            "id": "cursor-mdc-only",
            "as_of": as_of,
            "fact": "Cursor project rules require .mdc; a plain .md in .cursor/rules/ is ignored.",
        })
    if ".cursorrules" in paths:
        quirks.append({
            "id": "cursorrules-legacy",
            "as_of": as_of,
            "fact": "Cursor Help: .cursorrules is legacy and will be deprecated; migrate to alwaysApply .mdc.",
        })
    if any(s["path"] == "GEMINI.md" or s["path"].endswith("/GEMINI.md") for s in surfaces):
        quirks.append({
            "id": "gemini-cli-default-filename",
            "as_of": as_of,
            "fact": "Gemini CLI defaults to GEMINI.md only; AGENTS.md loads only if context.fileName includes it.",
        })
    if any(s["vendor"] == "copilot" for s in surfaces) and any(
            p == "AGENTS.md" or p.endswith("/AGENTS.md") for p in paths):
        quirks.append({
            "id": "copilot-chat-vs-cloud-agent",
            "as_of": as_of,
            "fact": "Copilot cloud agent/review read AGENTS.md; Copilot Chat on github.com does not.",
        })
    if any(s["kind"] == "nested-doc" and s["path"].endswith("AGENTS.md") for s in surfaces):
        quirks.append({
            "id": "agents-md-nested-semantics-differ",
            "as_of": as_of,
            "fact": "Nested AGENTS.md is not one spec: site=closest to edited file; Codex=concatenate root→CWD (32KiB); VS Code nested is experimental.",
        })
    return quirks


CODE_EXTS = {".kt": "kotlin", ".swift": "swift", ".java": "java", ".ts": "typescript",
             ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript",
             ".py": "python", ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php",
             ".cs": "c#", ".dart": "dart", ".ex": "elixir", ".scala": "scala",
             ".m": "objective-c", ".mm": "objective-c++", ".c": "c", ".cpp": "c++",
             ".vue": "vue", ".svelte": "svelte", ".sql": "sql", ".sh": "shell"}


def language_histogram(root, cap=60_000):
    """Source-file counts per language — the agnostic fallback when build markers lie."""
    counts = {}
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            ext = os.path.splitext(name)[1]
            lang = CODE_EXTS.get(ext)
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
            seen += 1
        if seen > cap:
            break
    return dict(sorted(counts.items(), key=lambda kv: -kv[1])[:8])


# Enforcement configured INSIDE a manifest instead of its own file.
EMBEDDED_SECTIONS = [
    ("pyproject.toml", r"^\[tool\.(ruff|mypy|pytest[.\w]*|black|isort|coverage|pyright)\]", "python"),
    ("package.json", r'"(eslintConfig|prettier|husky|lint-staged)"\s*:', "node"),
    ("Cargo.toml", r"^\[lints", "rust"),
    ("setup.cfg", r"^\[(flake8|mypy|tool:pytest)\]", "python"),
    ("tox.ini", r"^\[(flake8|testenv[.\w:]*)\]", "python"),
]


def embedded_tool_sections(root):
    """Lint/test config living inside a manifest — invisible to a filename-only scan."""
    found = []
    for rel, pattern, family in EMBEDDED_SECTIONS:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        for match in sorted(set(re.findall(pattern, read(path), re.MULTILINE))):
            found.append({"tool": match, "config": f"{rel} (embedded, {family})"})
    return found


def hook_surfaces(root, surfaces):
    """Agent hooks and git hooks ARE enforcement — report them on both lists."""
    found = [{"tool": f"agent-hook:{os.path.basename(s['path'])}", "config": s["path"]}
             for s in surfaces if s["kind"] == "hooks-dir"]
    hooks_path = None
    try:
        res = subprocess.run(["git", "-C", root, "config", "core.hooksPath"],
                             capture_output=True, text=True, timeout=10)
        hooks_path = res.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        pass
    if hooks_path:
        found.append({"tool": "git-hooks", "config": f"core.hooksPath={hooks_path}"})
    else:
        git_hooks = os.path.join(root, ".git", "hooks")
        if os.path.isdir(git_hooks):
            live = [h for h in os.listdir(git_hooks) if not h.endswith(".sample")]
            if live:
                found.append({"tool": "git-hooks",
                              "config": f".git/hooks ({', '.join(sorted(live)[:6])})"})
    return found


def main():
    if len(sys.argv) < 2:
        print("usage: detect_stack.py <repo-root>", file=sys.stderr)
        return 2
    root = os.path.abspath(sys.argv[1])
    now = datetime.now().astimezone()

    stack = []
    for rel, label, version_re in STACK_MARKERS:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        version = None
        if version_re:
            match = re.search(version_re, read(path), re.MULTILINE)
            version = match.group(1) if match else None
        stack.append({"label": label, "evidence": rel, "version_hint": version})

    surfaces = []
    seen = set()
    for rel, kind, vendor in AGENTIC_FILES:
        append_surface(surfaces, seen, rel, kind, vendor, root)
    for rel, kind, vendor, exts in AGENTIC_DIRS:
        collect_dir_tree(root, rel, kind, vendor, exts, surfaces, seen)
    for parts, kind, vendor, exts in NESTED_RULE_DIR_PARTS:
        for rel in find_nested_vendor_dirs(root, parts):
            collect_dir_tree(root, rel, kind, vendor, exts, surfaces, seen)

    nested = {}
    for name, vendor in NESTED_DOC_NAMES.items():
        hits = find_nested(root, name)
        if hits:
            nested[name] = hits
        for rel in hits:
            append_surface(surfaces, seen, rel, "nested-doc", vendor, root)

    imports = claude_imports(root, surfaces)
    for item in imports:
        target = item["import"]
        if target.startswith("~") or target.startswith("/"):
            continue
        rel = os.path.normpath(os.path.join(os.path.dirname(item["from"]), target))
        if os.path.isfile(os.path.join(root, rel)):
            append_surface(surfaces, seen, rel, "imported-doc", "claude", root)

    skills_locations = collect_skills(root)
    skills = sorted({s["name"] for s in skills_locations})

    enforcement = [{"tool": tool, "config": rel}
                   for rel, tool in ENFORCEMENT_MARKERS
                   if os.path.isfile(os.path.join(root, rel))]
    enforcement += embedded_tool_sections(root)
    enforcement += hook_surfaces(root, surfaces)
    workflows = os.path.join(root, ".github", "workflows")
    if os.path.isdir(workflows):
        enforcement.append({"tool": "github-actions",
                            "config": f".github/workflows ({len(os.listdir(workflows))} files)"})

    result = {
        "generated_at_local": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": root,
        "git": git_info(root),
        "stack": stack,
        "languages_by_file_count": language_histogram(root),
        "agentic_surfaces": surfaces,
        "agentic_surface_lines_total": sum(s["lines"] for s in surfaces),
        "nested_instruction_files": nested,
        "claude_imports": imports,
        "skills": skills,
        "skills_locations": skills_locations,
        "surface_quirks": surface_quirks(surfaces),
        "enforcement_surfaces": enforcement,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not surfaces:
        print("WARN  no agentic instruction surface found — nothing to audit",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
