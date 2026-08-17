#!/usr/bin/env python3
"""Print a safe git worktree path (and optional quoted git argv).

Usage:
    python3 worktree_path.py --branch feat/foo
    python3 worktree_path.py --branch feat/foo --print-cmd add
    python3 worktree_path.py --branch feat/foo --target develop --print-cmd fetch
    python3 worktree_path.py --branch feat/foo --mode local --print-cmd add
    python3 worktree_path.py --path /tmp/pr-feat-foo-deadbeef --print-cmd remove

Stdout: absolute path, or one git command with shlex-quoted argv.
Never interpolates the branch into an unquoted shell string.
Invalid refs (check-ref-format) → exit 2.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shlex
import subprocess
import sys
import tempfile

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_REF_OK = re.compile(r"^[A-Za-z0-9._/-]+$")


def slug_branch(branch: str) -> str:
    raw = (branch or "head").strip().replace("\\", "/")
    raw = raw.replace("..", "")
    slug = _UNSAFE.sub("-", raw).strip("-.")
    return (slug[:80] if slug else "branch")


def worktree_path(branch: str) -> str:
    digest = hashlib.sha1(branch.encode("utf-8")).hexdigest()[:8]
    return os.path.join(tempfile.gettempdir(), f"pr-{slug_branch(branch)}-{digest}")


def valid_git_ref(name: str) -> bool:
    """True if name is a safe branch-ish ref (no .., no shell metacharacters)."""
    name = (name or "").strip()
    if not name or name.startswith("-") or ".." in name or "\\" in name:
        return False
    if not _REF_OK.match(name):
        return False
    try:
        r = subprocess.run(
            ["git", "check-ref-format", f"refs/heads/{name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return bool(_REF_OK.match(name) and ".." not in name)


def require_ref(name: str, label: str) -> str:
    name = (name or "").strip()
    if not valid_git_ref(name):
        print(f"ERRO: {label} não é um git ref válido: {name!r}", file=sys.stderr)
        raise SystemExit(2)
    return name


def main() -> int:
    ap = argparse.ArgumentParser(description="Safe worktree path for power-review")
    ap.add_argument("--branch", help="source branch name")
    ap.add_argument("--target", help="target branch (for --print-cmd fetch)")
    ap.add_argument("--path", help="existing path (for remove)")
    ap.add_argument(
        "--mode",
        choices=("remote", "local"),
        default="remote",
        help="remote → origin/<branch>; local → HEAD",
    )
    ap.add_argument(
        "--print-cmd",
        choices=("add", "remove", "fetch"),
        help="print a quoted git command instead of the path",
    )
    ap.add_argument(
        "--git-ref",
        default=None,
        help="ref to check out on add (default: origin/<branch> or HEAD)",
    )
    a = ap.parse_args()

    path = (a.path or "").strip()
    if not path:
        if not a.branch:
            ap.error("informe --branch (ou --path para remove)")
        path = worktree_path(a.branch)

    if a.print_cmd == "remove":
        print("git worktree remove --force " + shlex.quote(path))
        return 0

    if a.print_cmd == "fetch":
        src = require_ref(a.branch or "", "source")
        tgt = require_ref(a.target or "", "target")
        print(
            "git fetch origin "
            + shlex.quote(src)
            + " "
            + shlex.quote(tgt)
        )
        return 0

    if a.print_cmd == "add":
        if a.git_ref:
            if a.git_ref in {"HEAD", "FETCH_HEAD"}:
                checkout = a.git_ref
            elif a.git_ref.startswith("origin/"):
                require_ref(a.git_ref[len("origin/") :], "git-ref")
                checkout = a.git_ref
            else:
                checkout = require_ref(a.git_ref, "git-ref")
        elif a.mode == "local":
            checkout = "HEAD"
        else:
            src = require_ref(a.branch or "", "source")
            checkout = f"origin/{src}"
        print("git worktree add -f " + shlex.quote(path) + " " + shlex.quote(checkout))
        return 0

    if a.branch:
        require_ref(a.branch, "source")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
