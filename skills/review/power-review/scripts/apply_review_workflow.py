#!/usr/bin/env python3
"""Apply GitLab/GitHub + Jira side-effects for power-review.

Subcommands:
  start  — label stat:under review, add current user as reviewer,
           transition Jira to Code Reviewing
  finish — add requested_change when there are blocking findings

Usage:
    python3 apply_review_workflow.py start --mr 2457 [--jira-key KEY] [--dry-run]
    python3 apply_review_workflow.py start --pr 12 [--forge github] [--jira-key KEY] [--dry-run]
    python3 apply_review_workflow.py finish --mr 2457 --has-blocking-findings true [--dry-run]
    python3 apply_review_workflow.py finish --pr 12 [--forge github] --has-blocking-findings true [--dry-run]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

def env_or(name: str, default: str) -> str:
    val = (os.environ.get(name) or "").strip()
    return val if val else default


STATUS_LABEL = env_or("POWER_REVIEW_STATUS_LABEL", "stat:under review")
REQUESTED_CHANGE_LABEL = env_or("POWER_REVIEW_REQUESTED_CHANGE_LABEL", "requested_change")
CODE_REVIEWING = env_or("POWER_REVIEW_JIRA_STATUS", "code reviewing").lower()
KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def competing_status_labels() -> set[str]:
    labels = {
        "stat:awaiting review",
        "stat:under review",
        "stat:under reviewing",
        "stat:awaiting tests",
        STATUS_LABEL,
    }
    extra = os.environ.get("POWER_REVIEW_COMPETING_LABELS") or ""
    for item in extra.split(","):
        item = item.strip()
        if item:
            labels.add(item)
    return labels


def log(msg: str) -> None:
    print(msg)


def glab_run(args: list[str], input_text: str | None = None) -> tuple[int, str, str]:
    r = subprocess.run(
        ["glab", *args],
        input=input_text,
        capture_output=True,
        text=True,
    )
    return r.returncode, r.stdout, r.stderr


def glab_api(args: list[str]) -> tuple[bool, Any]:
    code, out, err = glab_run(["api", *args])
    if code != 0:
        return False, (err or out).strip()
    try:
        return True, json.loads(out)
    except json.JSONDecodeError:
        return True, out.strip()


def glab_api_json(method: str, endpoint: str, payload: dict, dry_run: bool) -> tuple[bool, Any]:
    if dry_run:
        log(f"  [dry-run] {method} {endpoint} {json.dumps(payload, ensure_ascii=False)}")
        return True, "dry-run"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
        path = f.name
    try:
        return glab_api([
            endpoint,
            "--method", method,
            "--header", "Content-Type: application/json",
            "--input", path,
        ])
    finally:
        os.unlink(path)


def resolve_project(explicit: str | None) -> str:
    if explicit:
        return str(explicit)
    ok, data = glab_api(["projects/:id"])
    if ok and isinstance(data, dict) and data.get("id"):
        return str(data["id"])
    print(f"ERRO: project id: {data}", file=sys.stderr)
    sys.exit(2)


def current_username() -> str:
    ok, data = glab_api(["user"])
    if ok and isinstance(data, dict) and data.get("username"):
        return str(data["username"])
    print(f"ERRO: não foi possível resolver o usuário glab: {data}", file=sys.stderr)
    sys.exit(2)


def get_mr(project: str, mr: str) -> dict:
    ok, data = glab_api([f"projects/{project}/merge_requests/{mr}"])
    if not ok or not isinstance(data, dict):
        print(f"ERRO: MR: {data}", file=sys.stderr)
        sys.exit(2)
    return data


def update_labels(project: str, mr: str, labels: list[str], dry_run: bool) -> None:
    payload = {"labels": ",".join(labels)}
    ok, detail = glab_api_json("PUT", f"projects/{project}/merge_requests/{mr}", payload, dry_run)
    if ok:
        log(f"OK labels → {labels}")
    else:
        log(f"FALHA labels: {detail}")


def update_reviewers(project: str, mr: str, reviewer_ids: list[int], dry_run: bool) -> None:
    payload = {"reviewer_ids": reviewer_ids}
    ok, detail = glab_api_json("PUT", f"projects/{project}/merge_requests/{mr}", payload, dry_run)
    if ok:
        log(f"OK reviewers ids → {reviewer_ids}")
    else:
        log(f"FALHA reviewers: {detail}")


def git_email() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "config", "--get", "user.email"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def jira_auth() -> tuple[str, str, str] | None:
    token = (
        os.environ.get("ATLASSIAN_API_TOKEN")
        or os.environ.get("JIRA_API_TOKEN")
        or ""
    ).strip()
    if not token:
        return None
    email = (os.environ.get("JIRA_EMAIL") or git_email() or "").strip()
    if not email:
        return None
    base = (os.environ.get("JIRA_BASE_URL") or "").rstrip("/")
    if not base:
        return None
    return email, token, base


def jira_request(base: str, email: str, token: str, method: str, path: str, body: dict | None = None) -> Any:
    url = f"{base}{path}"
    raw = f"{email}:{token}".encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": "Basic " + base64.b64encode(raw).decode("ascii"),
        "User-Agent": "power-review/1.0",
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = resp.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def resolve_jira_key(explicit: str | None, mr_data: dict) -> str | None:
    if explicit:
        m = KEY_RE.search(explicit)
        return m.group(1) if m else explicit
    for field in (
        mr_data.get("title") or "",
        mr_data.get("description") or "",
        mr_data.get("source_branch") or "",
    ):
        m = KEY_RE.search(field)
        if m:
            return m.group(1)
    return None


def transition_jira_code_reviewing(key: str, dry_run: bool) -> None:
    auth = jira_auth()
    if not auth:
        log(
            "SKIP Jira: sem JIRA_BASE_URL e/ou ATLASSIAN_API_TOKEN/JIRA_API_TOKEN "
            "(use MCP Atlassian no agente se necessário)"
        )
        return
    email, token, base = auth
    try:
        issue = jira_request(base, email, token, "GET", f"/rest/api/3/issue/{key}?fields=status")
        status_name = ((issue.get("fields") or {}).get("status") or {}).get("name") or ""
        if CODE_REVIEWING in status_name.lower():
            log(f"OK Jira {key}: já em '{status_name}'")
            return
        transitions = jira_request(base, email, token, "GET", f"/rest/api/3/issue/{key}/transitions")
        chosen = None
        for t in transitions.get("transitions") or []:
            name = (t.get("name") or "").lower()
            to_name = ((t.get("to") or {}).get("name") or "").lower()
            if CODE_REVIEWING in name or CODE_REVIEWING in to_name:
                chosen = t
                break
        if not chosen:
            log(f"FALHA Jira {key}: transição para Code Reviewing não encontrada")
            return
        if dry_run:
            log(f"  [dry-run] transition {key} → {chosen.get('name')} ({chosen.get('id')})")
            return
        jira_request(
            base, email, token, "POST",
            f"/rest/api/3/issue/{key}/transitions",
            {"transition": {"id": str(chosen["id"])}},
        )
        log(f"OK Jira {key}: transição '{chosen.get('name')}' aplicada")
    except urllib.error.HTTPError as e:
        log(f"FALHA Jira {key}: HTTP {e.code} {e.reason}")
    except Exception as e:  # noqa: BLE001 — surface any REST failure without aborting review
        log(f"FALHA Jira {key}: {e}")


def _forge_arg(value: str) -> str:
    v = (value or "").strip().lower()
    if v not in {"github", "gitlab"}:
        raise argparse.ArgumentTypeError(
            f"{value!r} inválido (gitlab|github). "
            "Bitbucket/Azure não têm side-effects neste script."
        )
    return v


def resolve_iid_and_forge(args: argparse.Namespace) -> tuple[str, str]:
    """Infer IID + forge. --pr or --forge github → github; --mr only → gitlab."""
    mr = getattr(args, "mr", None)
    pr = getattr(args, "pr", None)
    mr_s = str(mr).strip() if mr not in (None, "") else ""
    pr_s = str(pr).strip() if pr not in (None, "") else ""
    forge = getattr(args, "forge", None)

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


def require_gh() -> None:
    if shutil.which("gh") is None:
        print(
            "ERRO: 'gh' não encontrado no PATH. Instale o GitHub CLI "
            "(https://cli.github.com/) e autentique com `gh auth login`.",
            file=sys.stderr,
        )
        sys.exit(2)


def gh_run(args: list[str]) -> tuple[int, str, str]:
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        print(
            "ERRO: 'gh' não encontrado no PATH. Instale o GitHub CLI "
            "(https://cli.github.com/) e autentique com `gh auth login`.",
            file=sys.stderr,
        )
        sys.exit(2)
    return r.returncode, r.stdout, r.stderr


def gh_json(args: list[str]) -> tuple[bool, Any]:
    code, out, err = gh_run(args)
    if code != 0:
        return False, (err or out).strip()
    try:
        return True, json.loads(out)
    except json.JSONDecodeError:
        return True, out.strip()


def github_pr_is_open(state: Any) -> bool:
    """Open PR: REST `open` or GraphQL/gh `OPEN` (case-insensitive).

    REST: https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request
    GraphQL PullRequestState: https://docs.github.com/en/graphql/reference/enums#pullrequeststate
    gh pr view --json state: https://cli.github.com/manual/gh_pr_view
    """
    return str(state or "").strip().lower() == "open"


def get_pr(pr: str) -> dict:
    # https://cli.github.com/manual/gh_pr_view
    ok, data = gh_json([
        "pr", "view", pr, "--json",
        "number,title,body,headRefName,state,labels,reviewRequests,author",
    ])
    if not ok or not isinstance(data, dict):
        print(f"ERRO: PR: {data}", file=sys.stderr)
        sys.exit(2)
    return data


def current_gh_login() -> str | None:
    # GET /user via authenticated gh — https://cli.github.com/manual/gh_api
    # https://docs.github.com/en/rest/users/users#get-the-authenticated-user
    ok, data = gh_json(["api", "user"])
    if ok and isinstance(data, dict) and data.get("login"):
        return str(data["login"])
    log(f"FALHA user: {data}")
    return None


def pr_label_names(pr_data: dict) -> list[str]:
    names: list[str] = []
    for item in pr_data.get("labels") or []:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def pr_reviewer_logins(pr_data: dict) -> set[str]:
    logins: set[str] = set()
    for item in pr_data.get("reviewRequests") or []:
        if isinstance(item, str):
            logins.add(item)
        elif isinstance(item, dict) and item.get("login"):
            logins.add(str(item["login"]))
    return logins


def gh_pr_edit(pr: str, extra: list[str], dry_run: bool) -> tuple[bool, str]:
    """Incremental edit. --add-label/--remove-label/--add-reviewer do not replace lists.

    https://cli.github.com/manual/gh_pr_edit
    REST add (keeps others): POST /repos/{owner}/{repo}/issues/{n}/labels
      https://docs.github.com/en/rest/issues/labels
    REST request reviewers (does not remove others):
      POST /repos/{owner}/{repo}/pulls/{n}/requested_reviewers
      https://docs.github.com/en/rest/pulls/review-requests
    """
    cmd = ["pr", "edit", pr, *extra]
    if dry_run:
        log(f"  [dry-run] gh {' '.join(shlex.quote(a) for a in cmd)}")
        return True, "dry-run"
    code, out, err = gh_run(cmd)
    if code != 0:
        return False, (err or out).strip()
    return True, (out or "").strip()


def github_apply_label_changes(
    pr: str, to_remove: list[str], to_add: list[str], dry_run: bool,
) -> None:
    # Do not auto-create missing repo labels (422 / not found → FALHA, continue).
    if to_remove:
        extra: list[str] = []
        for lb in to_remove:
            extra.extend(["--remove-label", lb])
        ok, detail = gh_pr_edit(pr, extra, dry_run)
        if ok:
            log(f"OK labels remove → {to_remove}")
        else:
            log(f"FALHA labels remove: {detail}")
    if to_add:
        extra = []
        for lb in to_add:
            extra.extend(["--add-label", lb])
        ok, detail = gh_pr_edit(pr, extra, dry_run)
        if ok:
            log(f"OK labels add → {to_add}")
        else:
            log(f"FALHA labels add: {detail}")


def start_github(args: argparse.Namespace, pr: str) -> int:
    require_gh()
    pr_data = get_pr(pr)
    state = pr_data.get("state") or ""
    if not github_pr_is_open(state):
        log(f"SKIP start: PR #{pr} state={state} (só aplica side-effects em open/OPEN)")
        return 0

    current = pr_label_names(pr_data)
    competing = competing_status_labels()
    to_remove = [lb for lb in current if lb in competing and lb != STATUS_LABEL]
    to_add = [] if STATUS_LABEL in current else [STATUS_LABEL]
    if not to_remove and not to_add:
        log(f"OK labels: já em '{STATUS_LABEL}', sem concorrentes")
    else:
        github_apply_label_changes(pr, to_remove, to_add, args.dry_run)

    login = current_gh_login()
    if login:
        existing = pr_reviewer_logins(pr_data)
        if login in existing:
            log(f"OK reviewer: @{login} já solicitado")
        else:
            ok, detail = gh_pr_edit(pr, ["--add-reviewer", login], args.dry_run)
            if ok:
                log(f"OK reviewer → @{login}")
            else:
                log(f"FALHA/SKIP reviewer @{login}: {detail}")
        log(f"Reviewer alvo: @{login}")

    key = resolve_jira_key(args.jira_key, {
        "title": pr_data.get("title") or "",
        "description": pr_data.get("body") or "",
        "source_branch": pr_data.get("headRefName") or "",
    })
    if key:
        transition_jira_code_reviewing(key, args.dry_run)
    else:
        log("SKIP Jira: nenhuma chave encontrada")
    return 0


def finish_github(args: argparse.Namespace, pr: str) -> int:
    require_gh()
    blocking = str(args.has_blocking_findings).lower() in {"1", "true", "yes", "sim"}
    pr_data = get_pr(pr)
    state = pr_data.get("state") or ""
    if not github_pr_is_open(state):
        log(f"SKIP finish: PR #{pr} state={state}")
        return 0
    if not blocking:
        log("OK finish: sem achados CRÍTICO/ALTO/MÉDIO — requested_change não aplicada")
        return 0
    labels = pr_label_names(pr_data)
    if REQUESTED_CHANGE_LABEL in labels:
        log(f"OK finish: label '{REQUESTED_CHANGE_LABEL}' já presente")
        return 0
    ok, detail = gh_pr_edit(pr, ["--add-label", REQUESTED_CHANGE_LABEL], args.dry_run)
    if ok:
        log(f"OK labels add → ['{REQUESTED_CHANGE_LABEL}']")
    else:
        log(f"FALHA labels add: {detail}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    iid, forge = resolve_iid_and_forge(args)
    if forge == "github":
        return start_github(args, iid)
    return start_gitlab(args, iid)


def cmd_finish(args: argparse.Namespace) -> int:
    iid, forge = resolve_iid_and_forge(args)
    if forge == "github":
        return finish_github(args, iid)
    return finish_gitlab(args, iid)


def start_gitlab(args: argparse.Namespace, mr: str) -> int:
    project = resolve_project(args.project)
    mr_data = get_mr(project, mr)
    state = (mr_data.get("state") or "").lower()
    if state != "opened":
        log(f"SKIP start: MR !{mr} state={state} (só aplica side-effects em opened)")
        return 0

    # Labels — remove competing status labels; keep the rest + under review
    current_labels = [str(x) for x in (mr_data.get("labels") or [])]
    kept = [lb for lb in current_labels if lb not in competing_status_labels()]
    if STATUS_LABEL not in kept:
        kept.append(STATUS_LABEL)
    update_labels(project, mr, kept, args.dry_run)

    # Reviewers — add current user id without dropping others
    me_ok, me = glab_api(["user"])
    if not me_ok or not isinstance(me, dict) or not me.get("id"):
        log(f"FALHA user: {me}")
    else:
        me_id = int(me["id"])
        existing = mr_data.get("reviewers") or []
        ids = []
        for r in existing:
            if isinstance(r, dict) and r.get("id") is not None:
                ids.append(int(r["id"]))
        if me_id not in ids:
            ids.append(me_id)
        update_reviewers(project, mr, ids, args.dry_run)
        log(f"Reviewer alvo: @{me.get('username')} (id={me_id})")

    key = resolve_jira_key(args.jira_key, mr_data)
    if key:
        transition_jira_code_reviewing(key, args.dry_run)
    else:
        log("SKIP Jira: nenhuma chave encontrada")
    return 0


def finish_gitlab(args: argparse.Namespace, mr: str) -> int:
    project = resolve_project(args.project)
    blocking = str(args.has_blocking_findings).lower() in {"1", "true", "yes", "sim"}
    mr_data = get_mr(project, mr)
    state = (mr_data.get("state") or "").lower()
    if state != "opened":
        log(f"SKIP finish: MR !{mr} state={state}")
        return 0
    if not blocking:
        log("OK finish: sem achados CRÍTICO/ALTO/MÉDIO — requested_change não aplicada")
        return 0
    labels = [str(x) for x in (mr_data.get("labels") or [])]
    if REQUESTED_CHANGE_LABEL in labels:
        log(f"OK finish: label '{REQUESTED_CHANGE_LABEL}' já presente")
        return 0
    labels.append(REQUESTED_CHANGE_LABEL)
    update_labels(project, mr, labels, args.dry_run)
    return 0


def _add_target_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--mr", default=None, help="IID do MR (GitLab; default se --forge omitido)")
    p.add_argument("--pr", default=None, help="Número do PR (GitHub)")
    p.add_argument(
        "--forge",
        default=None,
        type=_forge_arg,
        help="github | gitlab. --pr implica github; --mr sem --forge implica gitlab.",
    )
    p.add_argument("--project", default=None, help="Project id GitLab (glab); ignorado no GitHub")


def main() -> None:
    ap = argparse.ArgumentParser(description="Side-effects GitLab/GitHub/Jira do power-review.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("start", help="Label under review + reviewer + Jira Code Reviewing")
    _add_target_args(sp)
    sp.add_argument("--jira-key", default=None)
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_start)

    fp = sub.add_parser("finish", help="Add requested_change if blocking findings")
    _add_target_args(fp)
    fp.add_argument("--has-blocking-findings", required=True)
    fp.add_argument("--dry-run", action="store_true")
    fp.set_defaults(func=cmd_finish)

    args = ap.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
