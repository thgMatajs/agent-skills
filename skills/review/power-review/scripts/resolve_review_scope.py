#!/usr/bin/env python3
"""Resolve power-review diff scope for a GitLab MR or GitHub PR.

Looks for the latest note/review/comment containing:
  <!-- power-review:head_sha=<sha> reviewed_at=<iso> -->

Prints JSON with mode, branches, SHAs and diff_range.

Usage:
    python3 resolve_review_scope.py --mr 2457
    python3 resolve_review_scope.py --mr 2457 --project 5
    python3 resolve_review_scope.py --pr 12 [--forge github]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys

MARKER_RE = re.compile(
    r"<!--\s*power-review:head_sha=([0-9a-fA-F]{7,40})"
    r"(?:\s+reviewed_at=([^\s>]+))?\s*-->"
)

GH_MISSING = (
    "ERRO: 'gh' não encontrado no PATH. Instale o GitHub CLI "
    "(https://cli.github.com/) e autentique com `gh auth login`."
)


def glab_json(args: list[str]):
    r = subprocess.run(["glab", "api", *args], capture_output=True, text=True)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip()
    try:
        return True, json.loads(r.stdout)
    except json.JSONDecodeError:
        return True, r.stdout.strip()


def require_gh() -> None:
    if shutil.which("gh") is None:
        print(GH_MISSING, file=sys.stderr)
        sys.exit(2)


def gh_json(args: list[str]):
    """GET via `gh api` (official placeholders :owner/:repo).

    https://cli.github.com/manual/gh_api
    """
    try:
        r = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
    except FileNotFoundError:
        print(GH_MISSING, file=sys.stderr)
        sys.exit(2)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip()
    try:
        return True, json.loads(r.stdout)
    except json.JSONDecodeError:
        return True, r.stdout.strip()


def resolve_project(explicit: str | None) -> str:
    if explicit:
        return str(explicit)
    ok, data = glab_json(["projects/:id"])
    if ok and isinstance(data, dict) and data.get("id"):
        return str(data["id"])
    print(f"ERRO: project id: {data}", file=sys.stderr)
    sys.exit(2)


def fetch_all_notes(project: str, mr: str) -> list[dict]:
    notes: list[dict] = []
    page = 1
    while True:
        ok, data = glab_json([
            f"projects/{project}/merge_requests/{mr}/notes"
            f"?per_page=100&page={page}&sort=desc&order_by=created_at"
        ])
        if not ok:
            print(f"ERRO: notes: {data}", file=sys.stderr)
            sys.exit(2)
        if not isinstance(data, list) or not data:
            break
        notes.extend(data)
        if len(data) < 100:
            break
        page += 1
    return notes


def fetch_github_pages(endpoint: str) -> list[dict]:
    """Paginate a GitHub list endpoint (per_page=100).

    Reviews: GET /repos/{owner}/{repo}/pulls/{n}/reviews
      https://docs.github.com/en/rest/pulls/reviews
    Issue comments: GET /repos/{owner}/{repo}/issues/{n}/comments
      https://docs.github.com/en/rest/issues/comments
    Pagination: per_page max 100, page
      https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api
    """
    items: list[dict] = []
    page = 1
    while True:
        ok, data = gh_json([f"{endpoint}?per_page=100&page={page}"])
        if not ok:
            print(f"ERRO: {endpoint}: {data}", file=sys.stderr)
            sys.exit(2)
        if not isinstance(data, list) or not data:
            break
        items.extend(data)
        if len(data) < 100:
            break
        page += 1
    return items


def github_item_as_note(item: dict, *timestamp_keys: str) -> dict:
    """Map a GitHub review or issue comment onto the GitLab-note shape.

    Reviews: body + submitted_at (optional; pending reviews omit it) + id
      https://docs.github.com/en/rest/pulls/reviews
    Issue comments: body + created_at + id
      https://docs.github.com/en/rest/issues/comments
    """
    created = ""
    for key in timestamp_keys:
        val = item.get(key) or ""
        if val:
            created = val
            break
    return {
        "body": item.get("body") or "",
        "created_at": created,
        "id": item.get("id"),
    }


def same_sha(a: str, b: str) -> bool:
    if not a or not b:
        return False
    a, b = a.lower(), b.lower()
    return a == b or a.startswith(b) or b.startswith(a)


def find_latest_marker(notes: list[dict]) -> tuple[str | None, int | None, str | None]:
    best = None  # (created_at, note_id, sha, reviewed_at)
    for n in notes:
        body = n.get("body") or ""
        m = MARKER_RE.search(body)
        if not m:
            continue
        created = n.get("created_at") or ""
        cand = (created, n.get("id"), m.group(1), m.group(2))
        if best is None or cand[0] > best[0]:
            best = cand
    if best is None:
        return None, None, None
    return best[2], best[1], best[3]


def decide_mode(
    last_head: str | None, head_sha: str, target: str, source: str,
) -> tuple[str, str]:
    if not last_head:
        return "full", f"origin/{target}...origin/{source}"
    if same_sha(last_head, head_sha):
        return "noop", f"{last_head}...{head_sha}"
    return "incremental", f"{last_head}...{head_sha}"


def resolve_iid_and_forge(args: argparse.Namespace) -> tuple[str, str]:
    """--mr only → gitlab; --pr or --forge github → github."""
    mr_s = str(args.mr).strip() if args.mr not in (None, "") else ""
    pr_s = str(args.pr).strip() if args.pr not in (None, "") else ""
    forge = args.forge

    if mr_s and pr_s and mr_s != pr_s:
        print(f"ERRO: --mr ({mr_s}) e --pr ({pr_s}) diferem", file=sys.stderr)
        sys.exit(2)

    iid = pr_s or mr_s
    if not iid:
        print("ERRO: informe --mr <IID> (GitLab) ou --pr <IID> (GitHub)", file=sys.stderr)
        sys.exit(2)

    if pr_s and forge == "gitlab":
        print("ERRO: --pr implica GitHub; não combine com --forge gitlab", file=sys.stderr)
        sys.exit(2)

    if forge == "github" or pr_s:
        return iid, "github"
    return iid, "gitlab"


def run_gitlab(mr: str, project_arg: str | None) -> dict:
    project = resolve_project(project_arg)

    ok, mr_data = glab_json([f"projects/{project}/merge_requests/{mr}"])
    if not ok or not isinstance(mr_data, dict):
        print(f"ERRO: mr view: {mr_data}", file=sys.stderr)
        sys.exit(2)

    source = mr_data.get("source_branch") or ""
    target = mr_data.get("target_branch") or ""
    diff_refs = mr_data.get("diff_refs") or {}
    base_sha = diff_refs.get("base_sha") or ""
    head_sha = diff_refs.get("head_sha") or ""
    start_sha = diff_refs.get("start_sha") or ""

    notes = fetch_all_notes(project, mr)
    last_head, note_id, _reviewed = find_latest_marker(notes)
    mode, diff_range = decide_mode(last_head, head_sha, target, source)

    return {
        "mr": mr,
        "project": project,
        "mode": mode,
        "source_branch": source,
        "target_branch": target,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "start_sha": start_sha,
        "last_head_sha": last_head,
        "diff_range": diff_range,
        "marker_note_id": note_id,
        "mr_state": mr_data.get("state"),
        "title": mr_data.get("title"),
    }


def run_github(pr: str) -> dict:
    """Resolve scope from PR reviews + issue comments (not inline review comments).

    PR: GET /repos/{owner}/{repo}/pulls/{n}
      head.sha, head.ref, base.ref, base.sha, state, title
      https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request
    Reviews (summary body + marker): GET .../pulls/{n}/reviews
      https://docs.github.com/en/rest/pulls/reviews
    Issue comments (timeline): GET .../issues/{n}/comments
      https://docs.github.com/en/rest/issues/comments
    Inline review comments (.../pulls/{n}/comments) are not scanned —
    post_review.py puts the marker on the review body.
    """
    require_gh()

    ok, pr_data = gh_json([f"repos/:owner/:repo/pulls/{pr}"])
    if not ok or not isinstance(pr_data, dict):
        print(f"ERRO: pr view: {pr_data}", file=sys.stderr)
        sys.exit(2)

    head = pr_data.get("head") or {}
    base = pr_data.get("base") or {}
    if not isinstance(head, dict):
        head = {}
    if not isinstance(base, dict):
        base = {}

    source = head.get("ref") or ""
    target = base.get("ref") or ""
    head_sha = head.get("sha") or ""
    base_sha = base.get("sha") or ""

    reviews = fetch_github_pages(f"repos/:owner/:repo/pulls/{pr}/reviews")
    comments = fetch_github_pages(f"repos/:owner/:repo/issues/{pr}/comments")
    notes = (
        [github_item_as_note(r, "submitted_at", "created_at") for r in reviews]
        + [github_item_as_note(c, "created_at") for c in comments]
    )
    last_head, note_id, _reviewed = find_latest_marker(notes)
    mode, diff_range = decide_mode(last_head, head_sha, target, source)

    return {
        "pr": pr,
        "mr": pr,
        "mode": mode,
        "source_branch": source,
        "target_branch": target,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "start_sha": "",
        "last_head_sha": last_head,
        "diff_range": diff_range,
        "marker_note_id": note_id,
        "mr_state": pr_data.get("state"),
        "title": pr_data.get("title"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Resolve power-review scope for an MR (GitLab) or PR (GitHub)."
    )
    ap.add_argument("--mr", default=None, help="MR IID (GitLab)")
    ap.add_argument("--pr", default=None, help="PR number (GitHub)")
    ap.add_argument(
        "--forge",
        default=None,
        choices=("gitlab", "github"),
        help="github | gitlab. --pr implica github; --mr sem --forge implica gitlab.",
    )
    ap.add_argument("--project", default=None, help="GitLab project id (optional)")
    a = ap.parse_args()

    iid, forge = resolve_iid_and_forge(a)
    if forge == "github":
        out = run_github(iid)
    else:
        out = run_gitlab(iid, a.project)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
