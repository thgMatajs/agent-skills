#!/usr/bin/env python3
"""Detect the primary stack of a repo and persist a power-review profile.

Core review rules stay the same. This script only picks the stack overlay
(persona, official docs, project linter) for the repo under review.

Usage:
    python3 detect_stack.py --root <repo>
    python3 detect_stack.py --root <repo> --write
    python3 detect_stack.py --root <repo> --write --force
    python3 detect_stack.py --root <repo> --stack ios-swift --write
    python3 detect_stack.py --root <repo> --skill-dir "$SKILL_DIR" --write

Prints JSON on stdout. Exit 0 on success, 2 on bad args.
The profile lives in <repo>/.power-review/stack.json (project-local).
If --skill-dir is inside the repo, also writes references/active-stack.md.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROFILE_REL = Path(".power-review") / "stack.json"
ACTIVE_REL = Path("references") / "active-stack.md"

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".gradle",
    ".build",
    ".next",
    ".nuxt",
    ".output",
    ".turbo",
    ".venv",
    ".tox",
    "venv",
    "node_modules",
    "build",
    "dist",
    "coverage",
    "DerivedData",
    "Pods",
    "Carthage",
    "vendor",
    "__pycache__",
    ".dart_tool",
    "ios/Pods",
}

STACKS: dict[str, dict[str, Any]] = {
    "android-kotlin": {
        "label": "Android / Kotlin",
        "snippet_lang": "kotlin",
        "persona_ref": "references/stacks/android-kotlin.md",
        "docs": [
            {"title": "Android Developers", "url": "https://developer.android.com/docs"},
            {"title": "Kotlin", "url": "https://kotlinlang.org/docs/home.html"},
        ],
        "linter": {
            "name": "Detekt",
            "config_names": ["detekt.yml", "detekt-baseline.xml"],
            "command": "./gradlew :<module>:detekt --quiet",
        },
    },
    "ios-swift": {
        "label": "iOS / Swift / SwiftUI",
        "snippet_lang": "swift",
        "persona_ref": "references/stacks/ios-swift.md",
        "docs": [
            {"title": "Apple Developer", "url": "https://developer.apple.com/documentation/"},
            {"title": "Swift", "url": "https://www.swift.org/documentation/"},
            {"title": "SwiftUI", "url": "https://developer.apple.com/documentation/swiftui/"},
        ],
        "linter": {
            "name": "SwiftLint",
            "config_names": [".swiftlint.yml", ".swiftlint.yaml"],
            "command": "swiftlint lint --quiet",
        },
    },
    "flutter-dart": {
        "label": "Flutter / Dart",
        "snippet_lang": "dart",
        "persona_ref": "references/stacks/flutter-dart.md",
        "docs": [
            {"title": "Flutter", "url": "https://docs.flutter.dev/"},
            {"title": "Dart", "url": "https://dart.dev/guides"},
        ],
        "linter": {
            "name": "Dart analyzer",
            "config_names": ["analysis_options.yaml"],
            "command": "dart analyze",
        },
    },
    "web-typescript": {
        "label": "Web / TypeScript",
        "snippet_lang": "ts",
        "persona_ref": "references/stacks/web-typescript.md",
        "docs": [
            {"title": "TypeScript", "url": "https://www.typescriptlang.org/docs/"},
        ],
        "linter": {
            "name": "ESLint",
            "config_names": [
                "eslint.config.js",
                "eslint.config.mjs",
                "eslint.config.ts",
                ".eslintrc",
                ".eslintrc.js",
                ".eslintrc.cjs",
                ".eslintrc.json",
            ],
            "command": "npx eslint .",
        },
    },
    "python": {
        "label": "Python",
        "snippet_lang": "python",
        "persona_ref": "references/stacks/python.md",
        "docs": [
            {"title": "Python", "url": "https://docs.python.org/3/"},
        ],
        "linter": {
            "name": "Ruff",
            "config_names": ["ruff.toml", ".ruff.toml", "pyproject.toml"],
            "command": "ruff check",
        },
    },
    "ruby": {
        "label": "Ruby",
        "snippet_lang": "ruby",
        "persona_ref": "references/stacks/ruby.md",
        "docs": [
            {"title": "Ruby", "url": "https://docs.ruby-lang.org/en/master/"},
        ],
        "linter": {
            "name": "RuboCop",
            "config_names": [".rubocop.yml", ".rubocop.yaml"],
            "command": "bundle exec rubocop",
        },
    },
    "go": {
        "label": "Go",
        "snippet_lang": "go",
        "persona_ref": "references/stacks/go.md",
        "docs": [
            {"title": "Go", "url": "https://go.dev/doc/"},
            {"title": "Effective Go", "url": "https://go.dev/doc/effective_go"},
        ],
        "linter": {
            "name": "golangci-lint",
            "config_names": [".golangci.yml", ".golangci.yaml", ".golangci.toml"],
            "command": "golangci-lint run",
        },
    },
    "rust": {
        "label": "Rust",
        "snippet_lang": "rust",
        "persona_ref": "references/stacks/rust.md",
        "docs": [
            {"title": "Rust", "url": "https://doc.rust-lang.org/book/"},
            {"title": "std", "url": "https://doc.rust-lang.org/std/"},
        ],
        "linter": {
            "name": "Clippy",
            "config_names": ["clippy.toml", "rustfmt.toml", ".rustfmt.toml"],
            "command": "cargo clippy --all-targets -- -D warnings",
        },
    },
    "lua": {
        "label": "Lua",
        "snippet_lang": "lua",
        "persona_ref": "references/stacks/lua.md",
        "docs": [
            {"title": "Lua", "url": "https://www.lua.org/manual/5.4/"},
        ],
        "linter": {
            "name": "Luacheck",
            "config_names": [".luacheckrc"],
            "command": "luacheck .",
        },
    },
    "generic": {
        "label": "Generic",
        "snippet_lang": "",
        "persona_ref": "references/stacks/generic.md",
        "docs": [],
        "linter": {
            "name": None,
            "config_names": [],
            "command": None,
        },
    },
}

EXT_WEIGHT = {
    ".kt": ("android-kotlin", 1),
    ".kts": ("android-kotlin", 1),
    ".swift": ("ios-swift", 1),
    ".dart": ("flutter-dart", 1),
    ".ts": ("web-typescript", 1),
    ".tsx": ("web-typescript", 1),
    ".py": ("python", 1),
    ".rb": ("ruby", 1),
    ".go": ("go", 1),
    ".rs": ("rust", 1),
    ".lua": ("lua", 1),
}

# Official docs for languages that may not win a named stack (generic fallback).
LANG_BY_EXT: dict[str, dict[str, str]] = {
    ".kt": {"id": "kotlin", "title": "Kotlin", "url": "https://kotlinlang.org/docs/home.html", "snippet": "kotlin"},
    ".swift": {"id": "swift", "title": "Swift", "url": "https://www.swift.org/documentation/", "snippet": "swift"},
    ".dart": {"id": "dart", "title": "Dart", "url": "https://dart.dev/guides", "snippet": "dart"},
    ".ts": {"id": "typescript", "title": "TypeScript", "url": "https://www.typescriptlang.org/docs/", "snippet": "ts"},
    ".tsx": {"id": "typescript", "title": "TypeScript", "url": "https://www.typescriptlang.org/docs/", "snippet": "tsx"},
    ".py": {"id": "python", "title": "Python", "url": "https://docs.python.org/3/", "snippet": "python"},
    ".rb": {"id": "ruby", "title": "Ruby", "url": "https://docs.ruby-lang.org/en/master/", "snippet": "ruby"},
    ".go": {"id": "go", "title": "Go", "url": "https://go.dev/doc/", "snippet": "go"},
    ".rs": {"id": "rust", "title": "Rust", "url": "https://doc.rust-lang.org/book/", "snippet": "rust"},
    ".lua": {"id": "lua", "title": "Lua", "url": "https://www.lua.org/manual/5.4/", "snippet": "lua"},
    ".php": {"id": "php", "title": "PHP", "url": "https://www.php.net/docs.php", "snippet": "php"},
    ".java": {"id": "java", "title": "Java", "url": "https://docs.oracle.com/en/java/", "snippet": "java"},
    ".cs": {"id": "csharp", "title": "C#", "url": "https://learn.microsoft.com/dotnet/csharp/", "snippet": "csharp"},
    ".ex": {"id": "elixir", "title": "Elixir", "url": "https://hexdocs.pm/elixir/", "snippet": "elixir"},
    ".exs": {"id": "elixir", "title": "Elixir", "url": "https://hexdocs.pm/elixir/", "snippet": "elixir"},
    ".zig": {"id": "zig", "title": "Zig", "url": "https://ziglang.org/documentation/master/", "snippet": "zig"},
    ".cr": {"id": "crystal", "title": "Crystal", "url": "https://crystal-lang.org/reference/", "snippet": "crystal"},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def walk_files(root: Path, limit: int = 8000) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            out.append(Path(dirpath) / name)
            if len(out) >= limit:
                return out
    return out


def read_text(path: Path, max_bytes: int = 8000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_bytes]
    except OSError:
        return ""


def find_named(files: list[Path], names: set[str]) -> list[Path]:
    lower = {n.lower() for n in names}
    return [p for p in files if p.name.lower() in lower]


def find_suffix(files: list[Path], suffixes: tuple[str, ...]) -> list[Path]:
    return [p for p in files if p.name.endswith(suffixes)]


def web_extra_docs(root: Path, files: list[Path]) -> list[dict[str, str]]:
    packages = [p for p in files if p.name == "package.json"]
    blob = ""
    for p in packages[:4]:
        blob += read_text(p, 20_000)
    extras: list[dict[str, str]] = []
    mapping = (
        ("next", "Next.js", "https://nextjs.org/docs"),
        ("nuxt", "Nuxt", "https://nuxt.com/docs"),
        ("@angular/core", "Angular", "https://angular.dev"),
        ("vue", "Vue", "https://vuejs.org/guide/"),
        ("svelte", "Svelte", "https://svelte.dev/docs"),
        ("react-native", "React Native", "https://reactnative.dev/docs/getting-started"),
        ("react", "React", "https://react.dev"),
    )
    seen = set()
    for key, title, url in mapping:
        if key in blob and title not in seen:
            extras.append({"title": title, "url": url})
            seen.add(title)
            if key == "react" and "react-native" in blob:
                continue
    return extras


def ruby_extra_docs(files: list[Path]) -> list[dict[str, str]]:
    gemfiles = [p for p in files if p.name == "Gemfile"]
    blob = ""
    for p in gemfiles[:2]:
        blob += read_text(p, 12_000)
    if "rails" in blob.lower():
        return [{"title": "Rails", "url": "https://guides.rubyonrails.org/"}]
    return []


TOOLING_PARTS = {"scripts", "skills", "eval", ".cursor", "docs", "references"}


def is_tooling(path: Path, root: Path) -> bool:
    try:
        parts = set(path.relative_to(root).parts)
    except ValueError:
        return False
    return bool(parts & TOOLING_PARTS)


def score_repo(root: Path) -> tuple[dict[str, int], list[str], dict[str, Any], set[str]]:
    files = walk_files(root)
    scores = {k: 0 for k in STACKS}
    signals: list[str] = []
    extras: dict[str, Any] = {"docs": [], "linter_configs": [], "languages": []}
    strong: set[str] = set()

    names = {p.name for p in files}

    def hit(stack: str, points: int, signal: str) -> None:
        scores[stack] += points
        signals.append(signal)

    if "settings.gradle" in names or "settings.gradle.kts" in names:
        hit("android-kotlin", 5, "settings.gradle*")
        strong.add("android-kotlin")
    if any(p.name == "AndroidManifest.xml" for p in files):
        hit("android-kotlin", 5, "AndroidManifest.xml")
        strong.add("android-kotlin")
    gradle = [p for p in files if p.name in {"build.gradle", "build.gradle.kts"}]
    for p in gradle[:8]:
        text = read_text(p)
        if "com.android" in text or "android {" in text:
            hit("android-kotlin", 3, f"android plugin in {p.name}")
            break

    if "Package.swift" in names:
        hit("ios-swift", 5, "Package.swift")
        strong.add("ios-swift")
    if find_suffix(files, (".xcodeproj",)):
        hit("ios-swift", 5, "*.xcodeproj")
        strong.add("ios-swift")
    if find_suffix(files, (".xcworkspace",)):
        hit("ios-swift", 4, "*.xcworkspace")
    if "Podfile" in names:
        hit("ios-swift", 3, "Podfile")

    pubspecs = [p for p in files if p.name == "pubspec.yaml"]
    for p in pubspecs[:3]:
        if "flutter:" in read_text(p, 12_000):
            hit("flutter-dart", 8, "pubspec.yaml (flutter)")
            strong.add("flutter-dart")
            break

    if "package.json" in names:
        hit("web-typescript", 5, "package.json")
    if "tsconfig.json" in names:
        hit("web-typescript", 4, "tsconfig.json")
    if "package.json" in names and "tsconfig.json" in names:
        strong.add("web-typescript")
    extras["docs"].extend(web_extra_docs(root, files))

    if any(n in names for n in {"pyproject.toml", "requirements.txt", "setup.py", "Pipfile"}):
        hit("python", 5, "python project file")
        strong.add("python")
    if "Gemfile" in names:
        hit("ruby", 5, "Gemfile")
        strong.add("ruby")
    if any(p.name.endswith(".gemspec") for p in files):
        hit("ruby", 3, "*.gemspec")
        strong.add("ruby")
    if "go.mod" in names:
        hit("go", 5, "go.mod")
        strong.add("go")
    if "Cargo.toml" in names:
        hit("rust", 5, "Cargo.toml")
        strong.add("rust")
    if ".luacheckrc" in names:
        hit("lua", 4, ".luacheckrc")
        strong.add("lua")

    ext_counts: dict[str, int] = {}
    lang_counts: dict[str, int] = {}
    for p in files:
        if is_tooling(p, root):
            continue
        ext = p.suffix.lower()
        pair = EXT_WEIGHT.get(ext)
        if pair:
            stack, w = pair
            ext_counts[stack] = ext_counts.get(stack, 0) + w
        info = LANG_BY_EXT.get(ext)
        if info:
            lang_counts[info["id"]] = lang_counts.get(info["id"], 0) + 1
    for stack, count in ext_counts.items():
        add = min(count, 15)
        if add:
            scores[stack] += add
            signals.append(f"{count} {stack} source files")

    extras["languages"] = collect_languages(lang_counts)
    extras["docs"].extend(ruby_extra_docs(files))

    if scores.get("android-kotlin", 0) >= 8 and scores.get("python", 0) < 8:
        scores["python"] = min(scores.get("python", 0), 2)

    return scores, signals, extras, strong


def collect_languages(lang_counts: dict[str, int]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for meta in LANG_BY_EXT.values():
        by_id[meta["id"]] = meta
    out: list[dict[str, Any]] = []
    for lang_id, count in sorted(lang_counts.items(), key=lambda kv: -kv[1]):
        meta = by_id[lang_id]
        out.append(
            {
                "id": lang_id,
                "title": meta["title"],
                "url": meta["url"],
                "snippet": meta["snippet"],
                "count": count,
            }
        )
    return out


def pick_stack(
    scores: dict[str, int], strong: set[str]
) -> tuple[str, str, list[str]]:
    ranked = sorted(
        ((k, v) for k, v in scores.items() if k != "generic"),
        key=lambda kv: kv[1],
        reverse=True,
    )
    if not ranked or ranked[0][1] < 5:
        return "generic", "low", []
    winner, top = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0
    candidates = [k for k, v in ranked if v >= 8 or k in strong]
    if winner in strong and second < 5:
        return winner, "high", candidates
    if top >= 8 and top >= max(second * 2, second + 4):
        return winner, "high", candidates
    if len([k for k in candidates if k in strong or scores[k] >= 8]) > 1:
        return winner, "medium", candidates
    if top >= 5:
        return winner, "medium", candidates or [winner]
    return "generic", "low", []


def find_linter_configs(root: Path, names: list[str]) -> list[str]:
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if name in names:
                rel = str((Path(dirpath) / name).relative_to(root))
                found.append(rel)
                if len(found) >= 8:
                    return found
    return found


def build_profile(
    stack_id: str,
    confidence: str,
    signals: list[str],
    extras: dict[str, Any],
    root: Path,
    forced: bool,
) -> dict[str, Any]:
    meta = STACKS[stack_id]
    docs = list(meta["docs"])
    for item in extras.get("docs") or []:
        if item not in docs:
            docs.append(item)
    linter = dict(meta["linter"])
    configs = find_linter_configs(root, linter.get("config_names") or [])
    if stack_id == "generic":
        for other in STACKS.values():
            configs.extend(find_linter_configs(root, other["linter"].get("config_names") or []))
        configs = list(dict.fromkeys(configs))
        if configs:
            linter["name"] = "project linter"
    linter["configs"] = configs
    languages = list(extras.get("languages") or [])
    snippet = meta["snippet_lang"]
    if stack_id == "generic" and languages:
        top = languages[0]
        snippet = top.get("snippet") or snippet
        lang_doc = {"title": top.get("title"), "url": top.get("url")}
        if lang_doc not in docs and lang_doc.get("url"):
            docs.append(lang_doc)
    return {
        "stack_id": stack_id,
        "label": meta["label"],
        "confidence": "high" if forced else confidence,
        "forced": forced,
        "detected_at": now_iso(),
        "signals": signals,
        "docs": docs,
        "languages": languages,
        "linter": {
            "name": linter.get("name"),
            "configs": linter.get("configs") or [],
            "command": linter.get("command"),
        },
        "snippet_lang": snippet,
        "persona_ref": meta["persona_ref"],
    }


def load_profile(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_profile(path: Path, profile: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def active_overlay_link(persona_ref: str) -> str:
    # references/active-stack.md → references/stacks/foo.md
    if persona_ref.startswith("references/"):
        return persona_ref[len("references/") :]
    return persona_ref


def write_active_stack(skill_dir: Path, profile: dict[str, Any]) -> Path:
    dest = skill_dir / ACTIVE_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    docs = "\n".join(
        f"- {d.get('title')}: {d.get('url')}" for d in profile.get("docs") or []
    ) or "- (use the language/framework docs of the files in the diff)"
    linter = profile.get("linter") or {}
    configs = ", ".join(linter.get("configs") or []) or "(none found — skip style findings)"
    overlay = active_overlay_link(profile["persona_ref"])
    dest.write_text(
        "\n".join(
            [
                "<!-- generated by detect_stack.py — do not edit by hand -->",
                f"# Active stack: {profile['stack_id']}",
                "",
                f"**{profile['label']}** · confidence `{profile['confidence']}`",
                "",
                "Load in this order:",
                "",
                "1. `persona.md` — core rules (same on every stack)",
                f"2. `{overlay}` — stack overlay",
                "3. `linters.md` — style findings follow the project linter",
                "",
                "## Official docs (search only these)",
                "",
                docs,
                "",
                "## Linter",
                "",
                f"- Name: `{linter.get('name') or 'none'}`",
                f"- Configs: `{configs}`",
                f"- Command: `{linter.get('command') or 'n/a'}`",
                "",
                f"Snippet language: `{profile.get('snippet_lang') or 'source language'}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect and persist the power-review stack profile.")
    ap.add_argument("--root", default=".", help="Repo root under review")
    ap.add_argument("--write", action="store_true", help="Write .power-review/stack.json")
    ap.add_argument("--force", action="store_true", help="Overwrite a different saved stack")
    ap.add_argument("--stack", default=None, help="Force a stack id")
    ap.add_argument("--skill-dir", default=None, help="This skill's directory (optional)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"root is not a directory: {root}"}, ensure_ascii=False))
        return 2
    if args.stack and args.stack not in STACKS:
        print(json.dumps({"error": f"unknown stack: {args.stack}", "known": list(STACKS)}, ensure_ascii=False))
        return 2

    scores, signals, extras, strong = score_repo(root)
    detected_id, confidence, candidates = pick_stack(scores, strong)
    forced = bool(args.stack)
    stack_id = args.stack or detected_id
    profile = build_profile(stack_id, confidence, signals, extras, root, forced)
    profile["detected_stack_id"] = detected_id
    profile["scores"] = {k: v for k, v in sorted(scores.items(), key=lambda kv: -kv[1]) if v}
    profile["candidates"] = candidates

    dest = root / PROFILE_REL
    existing = load_profile(dest)
    action = "detected"
    needs_ask = (
        not forced
        and confidence == "medium"
        and len(candidates) > 1
        and not (existing and existing.get("stack_id") == profile["stack_id"])
    )
    if needs_ask:
        action = "ask"
        profile["action"] = action
        profile["profile_path"] = str(dest)
        profile["profile_exists"] = dest.is_file()
        profile["skill_active_path"] = None
        print(json.dumps(profile, ensure_ascii=False, indent=2))
        return 0
    if args.write:
        if existing and existing.get("stack_id") == profile["stack_id"] and not args.force:
            existing["signals"] = profile["signals"]
            existing["scores"] = profile["scores"]
            existing["linter"] = profile["linter"]
            existing["docs"] = profile["docs"]
            existing["confidence"] = profile["confidence"]
            write_profile(dest, existing)
            profile = existing
            action = "unchanged"
        elif existing and existing.get("stack_id") != profile["stack_id"] and not args.force:
            action = "mismatch"
            profile["saved_stack_id"] = existing.get("stack_id")
            profile["saved_label"] = existing.get("label")
        else:
            write_profile(dest, profile)
            action = "updated" if existing else "created"

    profile["action"] = action
    profile["profile_path"] = str(dest)
    profile["profile_exists"] = dest.is_file()

    skill_active = None
    if args.skill_dir and args.write and action in {"created", "updated", "unchanged"}:
        skill_dir = Path(args.skill_dir).resolve()
        if skill_dir.is_dir() and is_relative_to(skill_dir, root):
            skill_active = str(write_active_stack(skill_dir, profile))
    profile["skill_active_path"] = skill_active

    print(json.dumps(profile, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
