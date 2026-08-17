#!/usr/bin/env python3
"""Publica review inline no GitLab (glab), GitHub (gh api), Bitbucket Cloud
ou Azure DevOps.

GitLab: uma discussion por achado + nota-resumo
  POST /projects/:id/merge_requests/:iid/discussions  (position + new_line)
  POST /projects/:id/merge_requests/:iid/notes

GitHub (docs oficiais):
  POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews
  https://docs.github.com/en/rest/pulls/reviews
  Um review com `comments[]` (path + line + side) e `body` = resumo.
  `gh pr comment` NÃO ancora em linha — por isso usamos `gh api`.

Bitbucket Cloud (docs oficiais, 2026-08-14):
  POST https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{id}/comments
  https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pullrequests/#api-repositories-workspace-repo-slug-pullrequests-pull-request-id-comments-post
  Inline: `inline` com `path` + `to` (linha nova). Um POST por achado.
  Resumo: mesmo endpoint sem `inline`.
  Auth: API token (Basic, email + token) ou access token (Bearer).
  https://developer.atlassian.com/cloud/bitbucket/rest/intro/#authentication
  https://support.atlassian.com/bitbucket-cloud/docs/using-api-tokens/
  https://support.atlassian.com/bitbucket-cloud/docs/using-access-tokens/
  Só bitbucket.org (Cloud). Token só no env — nunca em disco.

Azure DevOps (docs oficiais, 2026-08-14):
  POST https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{id}/threads?api-version=7.1
  https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-request-threads/create?view=azure-devops-rest-7.1
  api-version 7.1 = latest released (7.2 é preview: 7.2-preview.1).
  Inline: comments[].content + threadContext.filePath + rightFileStart/End.line
  Resumo: thread sem threadContext.
  Preferir `az rest` (sessão Entra). Recurso Azure DevOps:
  --resource 499b84ac-1321-427f-aa17-267ca6975798
  https://learn.microsoft.com/en-us/cli/azure/use-azure-cli-rest-command
  https://learn.microsoft.com/en-us/azure/devops/pipelines/get-started/manage-pipelines-with-azure-cli
  Fallback PAT: AZURE_DEVOPS_EXT_PAT ou AZURE_DEVOPS_PAT, Basic (user vazio + PAT).
  https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate
  https://learn.microsoft.com/en-us/azure/devops/cli/log-in-via-pat

Uso:
    python3 post_review.py --input review.json [--dry-run]
    python3 post_review.py --input review.json --forge github
    python3 post_review.py --input review.json --forge bitbucket --dry-run
    python3 post_review.py --input review.json --forge azure --dry-run
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


# Azure DevOps Entra resource (official az rest --resource for Azure DevOps).
# https://learn.microsoft.com/en-us/azure/devops/pipelines/get-started/manage-pipelines-with-azure-cli
AZURE_DEVOPS_RESOURCE = "499b84ac-1321-427f-aa17-267ca6975798"
AZURE_API_VERSION = "7.1"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "references" / "review.schema.json"
SUMMARY_MARKER_RE = re.compile(
    r"<!--\s*power-review:head_sha=[0-9a-fA-F]{7,40}"
    r"(?:\s+reviewed_at=\S+)?\s*-->",
    re.I,
)


def _json_type(val: object) -> str:
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "integer"
    if isinstance(val, float):
        return "number"
    if isinstance(val, str):
        return "string"
    if isinstance(val, list):
        return "array"
    if isinstance(val, dict):
        return "object"
    return type(val).__name__


def _type_ok(declared, actual: str) -> bool:
    allowed = declared if isinstance(declared, list) else [declared]
    if actual in allowed:
        return True
    return actual == "integer" and "number" in allowed


def validate_review_schema(review: dict) -> list[str]:
    """Stdlib check against references/review.schema.json. No jsonschema dep."""
    if not SCHEMA_PATH.is_file():
        return [f"schema não encontrado: {SCHEMA_PATH}"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errs: list[str] = []
    props = schema.get("properties") or {}

    for key in schema.get("required") or []:
        if key not in review or review[key] in (None, ""):
            errs.append(f"faltando obrigatório: {key}")

    any_of = schema.get("anyOf") or []
    if any_of:
        matched = False
        for alt in any_of:
            reqs = alt.get("required") or []
            if reqs and all(review.get(k) not in (None, "") for k in reqs):
                matched = True
                break
        if not matched:
            labels = " ou ".join("/".join(a.get("required") or []) for a in any_of)
            errs.append(f"informe {labels}")

    for key, spec in props.items():
        if key not in review or review[key] is None:
            continue
        val = review[key]
        declared = spec.get("type")
        if declared and not _type_ok(declared, _json_type(val)):
            errs.append(f"{key}: tipo {_json_type(val)}, esperado {declared}")
        enum = spec.get("enum")
        if enum is not None and val not in enum:
            errs.append(f"{key}: {val!r} fora de {enum}")
        min_len = spec.get("minLength")
        if isinstance(val, str) and min_len and len(val) < min_len:
            errs.append(f"{key}: minLength {min_len}")
        if key != "comments" or not isinstance(val, list):
            continue
        item_spec = spec.get("items") or {}
        item_req = item_spec.get("required") or []
        item_props = item_spec.get("properties") or {}
        for i, item in enumerate(val):
            if not isinstance(item, dict):
                errs.append(f"comments[{i}]: deve ser objeto")
                continue
            for rk in item_req:
                if rk not in item or item[rk] in (None, ""):
                    errs.append(f"comments[{i}].{rk} obrigatório")
            for pk, ps in item_props.items():
                if pk not in item or item[pk] is None:
                    continue
                iv = item[pk]
                dt = ps.get("type")
                if dt and not _type_ok(dt, _json_type(iv)):
                    errs.append(
                        f"comments[{i}].{pk}: tipo {_json_type(iv)}, esperado {dt}"
                    )
                if isinstance(iv, str) and ps.get("minLength") and len(iv) < ps["minLength"]:
                    errs.append(f"comments[{i}].{pk}: vazio")
                minimum = ps.get("minimum")
                if isinstance(iv, int) and not isinstance(iv, bool) and minimum is not None:
                    if iv < minimum:
                        errs.append(f"comments[{i}].{pk}: mínimo {minimum}")

    summary = review.get("summary") or ""
    if isinstance(summary, str) and summary.strip():
        matches = list(SUMMARY_MARKER_RE.finditer(summary))
        if not matches or summary[matches[-1].end() :].strip():
            errs.append(
                "summary deve terminar com "
                "<!-- power-review:head_sha=<sha> reviewed_at=<iso> -->"
            )
    return errs


def run_api(cli: str, args: list[str]):
    r = subprocess.run([cli, "api", *args], capture_output=True, text=True)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip()
    try:
        return True, json.loads(r.stdout)
    except json.JSONDecodeError:
        return True, r.stdout.strip()


def post_json(cli: str, endpoint: str, payload: dict, dry_run: bool):
    if dry_run:
        print(f"  [dry-run] {cli} POST {endpoint}")
        return True, "dry-run"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
        path = f.name
    try:
        return run_api(cli, [
            endpoint,
            "--method", "POST",
            "--header", "Content-Type: application/json",
            "--header", "Accept: application/vnd.github+json",
            "--input", path,
        ])
    finally:
        os.unlink(path)


def _review_url(review: dict) -> str:
    for key in ("url", "html_url", "web_url", "pr_url", "mr_url"):
        val = review.get(key)
        if val:
            return str(val).strip()
    return ""


def _forge_from_url(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url if "://" in url else "https://" + url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    if "bitbucket.org" in host:
        return "bitbucket"
    if host == "dev.azure.com" or host.endswith(".visualstudio.com"):
        return "azure"
    if "github.com" in host or host.endswith(".ghe.com"):
        return "github"
    if "gitlab" in host or "/merge_requests/" in path:
        return "gitlab"
    if "/pull-requests/" in path:
        return "bitbucket"
    if "pullrequest/" in path.lower():
        return "azure"
    if re.search(r"/pull/\d+", path):
        return "github"
    return None


def infer_forge(review: dict, explicit: str | None) -> str:
    if explicit:
        return explicit
    if review.get("forge"):
        return str(review["forge"])
    from_url = _forge_from_url(_review_url(review))
    if from_url:
        return from_url
    if review.get("pr") and not review.get("mr"):
        return "github"
    return "gitlab"


def iid_of(review: dict) -> str:
    for key in ("pr", "mr", "iid"):
        if review.get(key) is not None:
            return str(review[key])
    print("ERRO: review.json precisa de 'pr' ou 'mr'.", file=sys.stderr)
    sys.exit(2)


def _strip_git_suffix(name: str) -> str:
    name = (name or "").strip().rstrip("/")
    if name.endswith(".git"):
        name = name[:-4]
    return name


def _git_remotes() -> list[str]:
    try:
        r = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if r.returncode != 0:
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        url = parts[1]
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _parse_bitbucket_url(url: str) -> tuple[str, str, str | None]:
    """Return (workspace, repo_slug, iid) from a bitbucket.org URL or remote. Empty if not Cloud."""
    raw = (url or "").strip()
    if not raw:
        return "", "", None
    host = ""
    path = ""
    if raw.startswith("git@"):
        rest = raw[4:]
        host, _, path = rest.partition(":")
        path = "/" + path
    else:
        parsed = urlparse(raw if "://" in raw else "https://" + raw)
        host = parsed.hostname or ""
        path = parsed.path or ""
    host = host.lower()
    if host != "bitbucket.org" and not host.endswith(".bitbucket.org"):
        return "", "", None
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return "", "", None
    workspace = parts[0]
    repo_slug = _strip_git_suffix(parts[1])
    iid = None
    for i, part in enumerate(parts):
        if part.lower() in {"pull-requests", "pullrequest"} and i + 1 < len(parts):
            if re.fullmatch(r"\d+", parts[i + 1]):
                iid = parts[i + 1]
            break
    return workspace, repo_slug, iid


def _parse_azure_url(url: str) -> tuple[str, str, str, str | None]:
    """Return (org, project, repo, iid) from a DevOps URL or remote. Never invent."""
    raw = (url or "").strip()
    if not raw:
        return "", "", "", None
    org = project = repo = ""
    iid = None
    if raw.startswith("git@"):
        rest = raw[4:]
        host, _, path = rest.partition(":")
        host = host.lower()
        parts = [p for p in path.split("/") if p]
        # git@ssh.dev.azure.com:v3/{org}/{project}/{repo}
        if "dev.azure.com" in host and len(parts) >= 4 and parts[0] == "v3":
            return parts[1], parts[2], _strip_git_suffix(parts[3]), None
        return "", "", "", None
    parsed = urlparse(raw if "://" in raw else "https://" + raw)
    host = (parsed.hostname or "").lower()
    parts = [p for p in (parsed.path or "").split("/") if p]
    if host.endswith(".visualstudio.com"):
        org = host.split(".")[0]
        if parts and parts[0].lower() == "defaultcollection":
            parts = parts[1:]
        if "_git" in parts:
            gi = parts.index("_git")
            if gi >= 1 and gi + 1 < len(parts):
                project = parts[gi - 1]
                repo = _strip_git_suffix(parts[gi + 1])
        elif len(parts) >= 2:
            project, repo = parts[0], _strip_git_suffix(parts[1])
    elif host == "dev.azure.com" or host.endswith(".dev.azure.com"):
        if len(parts) >= 1:
            org = parts[0]
        if "_git" in parts:
            gi = parts.index("_git")
            if gi >= 2 and gi + 1 < len(parts):
                project = parts[gi - 1]
                repo = _strip_git_suffix(parts[gi + 1])
        elif len(parts) >= 3:
            project, repo = parts[1], _strip_git_suffix(parts[2])
    else:
        return "", "", "", None
    for i, part in enumerate(parts):
        if part.lower() == "pullrequest" and i + 1 < len(parts):
            num = parts[i + 1].split("?")[0]
            if re.fullmatch(r"\d+", num):
                iid = num
            break
    return org, project, repo, iid


def resolve_bitbucket_coords(review: dict) -> tuple[str, str]:
    workspace = str(review.get("workspace") or "").strip()
    repo_slug = str(review.get("repo_slug") or review.get("repo") or "").strip()
    project = str(review.get("project") or "").strip()
    if (not workspace or not repo_slug) and project:
        if "/" in project:
            left, right = project.split("/", 1)
            workspace = workspace or left.strip()
            repo_slug = repo_slug or _strip_git_suffix(right)
    if not workspace or not repo_slug:
        w, r, _ = _parse_bitbucket_url(_review_url(review))
        workspace = workspace or w
        repo_slug = repo_slug or r
    if not workspace or not repo_slug:
        for remote in _git_remotes():
            w, r, _ = _parse_bitbucket_url(remote)
            if w and r:
                workspace = workspace or w
                repo_slug = repo_slug or r
                break
    return workspace, repo_slug


def resolve_azure_coords(review: dict) -> tuple[str, str, str]:
    org = str(review.get("organization") or review.get("org") or "").strip()
    project = str(review.get("project") or "").strip()
    repo = str(
        review.get("repository")
        or review.get("repo")
        or review.get("repo_slug")
        or ""
    ).strip()
    if not org or not project or not repo:
        o, p, r, _ = _parse_azure_url(_review_url(review))
        org = org or o
        project = project or p
        repo = repo or r
    if not org or not project or not repo:
        for remote in _git_remotes():
            o, p, r, _ = _parse_azure_url(remote)
            if o and p and r:
                org = org or o
                project = project or p
                repo = repo or r
                break
    return org, project, repo


def bitbucket_creds_ok() -> bool:
    if (os.environ.get("BITBUCKET_ACCESS_TOKEN") or "").strip():
        return True
    user = (os.environ.get("BITBUCKET_USERNAME") or "").strip()
    if user and (os.environ.get("BITBUCKET_API_TOKEN") or "").strip():
        return True
    if user and (os.environ.get("BITBUCKET_APP_PASSWORD") or "").strip():
        return True
    return False


def azure_pat() -> str:
    return (
        (os.environ.get("AZURE_DEVOPS_EXT_PAT") or "").strip()
        or (os.environ.get("AZURE_DEVOPS_PAT") or "").strip()
    )


def azure_az_rest_ok() -> bool:
    if not shutil.which("az"):
        return False
    try:
        r = subprocess.run(
            ["az", "account", "show"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def _bitbucket_auth_header() -> str | None:
    access = (os.environ.get("BITBUCKET_ACCESS_TOKEN") or "").strip()
    if access:
        return "Bearer " + access
    user = (os.environ.get("BITBUCKET_USERNAME") or "").strip()
    api = (os.environ.get("BITBUCKET_API_TOKEN") or "").strip()
    if user and api:
        token = base64.b64encode(f"{user}:{api}".encode("utf-8")).decode("ascii")
        return "Basic " + token
    app = (os.environ.get("BITBUCKET_APP_PASSWORD") or "").strip()
    if user and app:
        token = base64.b64encode(f"{user}:{app}".encode("utf-8")).decode("ascii")
        return "Basic " + token
    return None


def _http_json_post(url: str, payload: dict, auth_header: str) -> tuple[bool, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return True, raw.strip()[:200]
            cid = parsed.get("id") if isinstance(parsed, dict) else None
            return True, f"id={cid}" if cid is not None else "ok"
    except urllib.error.HTTPError as e:
        e.read()
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"URL error: {e.reason}"


def _azure_file_path(path: str) -> str:
    path = (path or "").strip()
    if not path:
        return path
    # Official create example uses a leading slash on filePath.
    # https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-request-threads/create?view=azure-devops-rest-7.1
    return path if path.startswith("/") else "/" + path


def post_gitlab(review: dict, dry_run: bool) -> int:
    mr = iid_of(review)
    ok, data = run_api("glab", ["projects/:id"])
    project = str(review.get("project") or "")
    if not project:
        if ok and isinstance(data, dict) and data.get("id"):
            project = str(data["id"])
        else:
            print(f"ERRO: project id: {data}", file=sys.stderr)
            return 2
    base_sha = review["base_sha"]
    head_sha = review["head_sha"]
    start_sha = review["start_sha"]
    comments = review.get("comments") or []
    disc = f"projects/{project}/merge_requests/{mr}/discussions"
    notes = f"projects/{project}/merge_requests/{mr}/notes"
    fails = 0
    for i, c in enumerate(comments, start=1):
        payload = {
            "body": c["body"],
            "position": {
                "position_type": "text",
                "base_sha": base_sha,
                "head_sha": head_sha,
                "start_sha": start_sha,
                "old_path": c["path"],
                "new_path": c["path"],
                "new_line": int(c["new_line"]),
            },
        }
        ok, detail = post_json("glab", disc, payload, dry_run)
        if not ok:
            fails += 1
        print(f"[{i:02d}] {'OK  ' if ok else 'FALHA'} {c['path']}:{c['new_line']} {detail if ok and isinstance(detail, dict) else detail}")
    if review.get("summary"):
        ok, detail = post_json("glab", notes, {"body": review["summary"]}, dry_run)
        print(f"[resumo] {'OK' if ok else 'FALHA'} {detail if ok and isinstance(detail, dict) else detail}")
        if not ok:
            fails += 1
    total = len(comments) + (1 if review.get("summary") else 0)
    print(f"\nPublicados (GitLab): {total - fails}/{total} | Falhas: {fails}")
    return 1 if fails else 0


def post_github(review: dict, dry_run: bool, allow_approve: bool = False) -> int:
    """Um Pull Request Review com comments inline + body (resumo).

    Docs: POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews
    Cada comment: path, line (lado novo do diff), side=RIGHT.
    A linha precisa existir no diff do PR; senão a API responde 422.
    """
    pr = iid_of(review)
    head_sha = review.get("head_sha")
    if not head_sha:
        ok, data = run_api("gh", [f"repos/:owner/:repo/pulls/{pr}"])
        if ok and isinstance(data, dict):
            head_sha = (data.get("head") or {}).get("sha")
        if not head_sha:
            print(f"ERRO: head_sha: {data if not head_sha else ''}", file=sys.stderr)
            return 2
    comments = []
    for c in review.get("comments") or []:
        comments.append({
            "path": c["path"],
            "line": int(c["new_line"]),
            "side": c.get("side") or "RIGHT",
            "body": c["body"],
        })
    event = review.get("event") or "COMMENT"
    if event not in {"COMMENT", "REQUEST_CHANGES", "APPROVE"}:
        print(f"ERRO: event GitHub inválido: {event}", file=sys.stderr)
        return 2
    if event == "APPROVE" and not allow_approve:
        print(
            "ERRO: event=APPROVE exige --allow-approve (só se o usuário pediu aprovação no GitHub).",
            file=sys.stderr,
        )
        return 2
    payload = {
        "commit_id": head_sha,
        "event": event,
        "comments": comments,
    }
    if review.get("summary"):
        payload["body"] = review["summary"]
    elif event in {"COMMENT", "REQUEST_CHANGES"}:
        payload["body"] = "Power review"
    endpoint = f"repos/:owner/:repo/pulls/{pr}/reviews"
    if dry_run:
        print(f"  [dry-run] gh POST {endpoint} ({len(comments)} inline, event={event})")
        for i, c in enumerate(comments, start=1):
            print(f"[{i:02d}] OK   {c['path']}:{c['line']} dry-run")
        if payload.get("body"):
            print("[resumo] OK dry-run")
        return 0
    ok, detail = post_json("gh", endpoint, payload, False)
    if ok:
        rid = detail.get("id") if isinstance(detail, dict) else detail
        print(f"[review] OK id={rid} event={event} inline={len(comments)}")
        for i, c in enumerate(comments, start=1):
            print(f"[{i:02d}] OK   {c['path']}:{c['line']}")
        if payload.get("body"):
            print("[resumo] OK (body do review)")
        print(f"\nPublicados (GitHub): 1 review / {len(comments)} inline")
        return 0
    print(f"[review] FALHA {detail}", file=sys.stderr)
    return 1


def post_bitbucket(review: dict, dry_run: bool) -> int:
    workspace, repo_slug = resolve_bitbucket_coords(review)
    if not workspace or not repo_slug:
        print(
            "ERRO: Bitbucket Cloud precisa de workspace e repo_slug "
            "(review.json, URL do PR ou git remote). Não invento esses campos.",
            file=sys.stderr,
        )
        return 2
    if not dry_run and not bitbucket_creds_ok():
        print(
            "ERRO: publicação Bitbucket bloqueada — defina no ambiente "
            "BITBUCKET_ACCESS_TOKEN (Bearer) ou "
            "BITBUCKET_USERNAME + BITBUCKET_API_TOKEN "
            "(Basic: email Atlassian + API token). "
            "Docs: https://support.atlassian.com/bitbucket-cloud/docs/using-api-tokens/ "
            "e https://developer.atlassian.com/cloud/bitbucket/rest/intro/#authentication",
            file=sys.stderr,
        )
        return 2
    pr = iid_of(review)
    ws_q = urllib.parse.quote(workspace, safe="")
    repo_q = urllib.parse.quote(repo_slug, safe="")
    endpoint = (
        f"https://api.bitbucket.org/2.0/repositories/{ws_q}/{repo_q}"
        f"/pullrequests/{urllib.parse.quote(pr, safe='')}/comments"
    )
    comments = review.get("comments") or []
    fails = 0
    auth = None if dry_run else _bitbucket_auth_header()
    for i, c in enumerate(comments, start=1):
        payload = {
            "content": {"raw": c["body"]},
            "inline": {"path": c["path"], "to": int(c["new_line"])},
        }
        if dry_run:
            print(f"  [dry-run] POST {endpoint}")
            print(f"[{i:02d}] OK   {c['path']}:{c['new_line']} dry-run")
            continue
        ok, detail = _http_json_post(endpoint, payload, auth or "")
        if not ok:
            fails += 1
        print(f"[{i:02d}] {'OK  ' if ok else 'FALHA'} {c['path']}:{c['new_line']} {detail}")
    if review.get("summary"):
        payload = {"content": {"raw": review["summary"]}}
        if dry_run:
            print(f"  [dry-run] POST {endpoint}")
            print("[resumo] OK dry-run")
        else:
            ok, detail = _http_json_post(endpoint, payload, auth or "")
            print(f"[resumo] {'OK' if ok else 'FALHA'} {detail}")
            if not ok:
                fails += 1
    total = len(comments) + (1 if review.get("summary") else 0)
    print(f"\nPublicados (Bitbucket): {total - fails}/{total} | Falhas: {fails}")
    return 1 if fails else 0


def _az_rest_post(uri: str, payload: dict) -> tuple[bool, str]:
    body = json.dumps(payload, ensure_ascii=False)
    r = subprocess.run(
        [
            "az",
            "rest",
            "--method",
            "post",
            "--uri",
            uri,
            "--body",
            body,
            "--resource",
            AZURE_DEVOPS_RESOURCE,
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        # Never echo a PAT if az printed env hints.
        err = re.sub(r"(?i)(pat|token|authorization)[=:]\s*\S+", r"\1=<redacted>", err)
        return False, err[:400] or f"az rest exit {r.returncode}"
    try:
        parsed = json.loads(r.stdout) if r.stdout else {}
    except json.JSONDecodeError:
        return True, (r.stdout or "").strip()[:200]
    tid = parsed.get("id") if isinstance(parsed, dict) else None
    return True, f"id={tid}" if tid is not None else "ok"


def post_azure(review: dict, dry_run: bool) -> int:
    org, project, repo = resolve_azure_coords(review)
    if not org or not project or not repo:
        print(
            "ERRO: Azure DevOps precisa de organization, project e repository "
            "(review.json, URL do PR ou git remote). Não invento esses campos.",
            file=sys.stderr,
        )
        return 2
    use_az = azure_az_rest_ok()
    pat = azure_pat()
    if not dry_run and not use_az and not pat:
        print(
            "ERRO: publicação Azure DevOps bloqueada — `az login` "
            "(para `az rest`) ou defina AZURE_DEVOPS_EXT_PAT / AZURE_DEVOPS_PAT. "
            "Docs: https://learn.microsoft.com/en-us/cli/azure/use-azure-cli-rest-command "
            "e https://learn.microsoft.com/en-us/azure/devops/cli/log-in-via-pat",
            file=sys.stderr,
        )
        return 2
    pr = iid_of(review)
    org_q = urllib.parse.quote(org, safe="")
    project_q = urllib.parse.quote(project, safe="")
    repo_q = urllib.parse.quote(repo, safe="")
    endpoint = (
        f"https://dev.azure.com/{org_q}/{project_q}/_apis/git/repositories/{repo_q}"
        f"/pullRequests/{urllib.parse.quote(pr, safe='')}/threads"
        f"?api-version={AZURE_API_VERSION}"
    )
    comments = review.get("comments") or []
    fails = 0
    auth = None
    if not dry_run and not use_az:
        token = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
        auth = "Basic " + token

    def send(payload: dict) -> tuple[bool, str]:
        if use_az:
            return _az_rest_post(endpoint, payload)
        return _http_json_post(endpoint, payload, auth or "")

    for i, c in enumerate(comments, start=1):
        line = int(c["new_line"])
        payload = {
            "comments": [{"content": c["body"]}],
            "threadContext": {
                "filePath": _azure_file_path(c["path"]),
                "rightFileStart": {"line": line, "offset": 1},
                "rightFileEnd": {"line": line, "offset": 1},
            },
        }
        if dry_run:
            print(f"  [dry-run] POST {endpoint}")
            print(f"[{i:02d}] OK   {c['path']}:{c['new_line']} dry-run")
            continue
        ok, detail = send(payload)
        if not ok:
            fails += 1
        print(f"[{i:02d}] {'OK  ' if ok else 'FALHA'} {c['path']}:{c['new_line']} {detail}")
    if review.get("summary"):
        payload = {"comments": [{"content": review["summary"]}]}
        if dry_run:
            print(f"  [dry-run] POST {endpoint}")
            print("[resumo] OK dry-run")
        else:
            ok, detail = send(payload)
            print(f"[resumo] {'OK' if ok else 'FALHA'} {detail}")
            if not ok:
                fails += 1
    total = len(comments) + (1 if review.get("summary") else 0)
    print(f"\nPublicados (Azure DevOps): {total - fails}/{total} | Falhas: {fails}")
    return 1 if fails else 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Posta review inline no GitLab, GitHub, Bitbucket Cloud ou Azure DevOps."
    )
    ap.add_argument("--input", required=True, help="Caminho do review.json")
    ap.add_argument(
        "--forge",
        choices=("gitlab", "github", "bitbucket", "azure"),
        default=None,
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--allow-approve",
        action="store_true",
        help="Permite event=APPROVE no GitHub. Só com pedido explícito do usuário.",
    )
    a = ap.parse_args()

    try:
        with open(a.input, encoding="utf-8") as f:
            review = json.load(f)
    except FileNotFoundError:
        print(f"ERRO: review.json não encontrado: {a.input}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(
            f"ERRO: review.json inválido ({a.input}): {exc.msg} "
            f"(linha {exc.lineno}, coluna {exc.colno}). "
            "Shape: references/review.schema.json "
            "(head_sha, summary, mr ou pr; comments[].path/new_line/body).",
            file=sys.stderr,
        )
        sys.exit(2)
    if not isinstance(review, dict):
        print("ERRO: review.json deve ser um objeto JSON.", file=sys.stderr)
        sys.exit(2)

    schema_errs = validate_review_schema(review)
    if schema_errs:
        print("ERRO: review.json fora de references/review.schema.json:", file=sys.stderr)
        for item in schema_errs:
            print(f"  - {item}", file=sys.stderr)
        sys.exit(2)

    if not review.get("comments") and not review.get("summary"):
        print("ERRO: nada para postar (sem 'comments' e sem 'summary').", file=sys.stderr)
        sys.exit(2)

    forge = infer_forge(review, a.forge)
    if forge == "github":
        raise SystemExit(post_github(review, a.dry_run, allow_approve=a.allow_approve))
    if forge == "gitlab":
        raise SystemExit(post_gitlab(review, a.dry_run))
    if forge == "bitbucket":
        raise SystemExit(post_bitbucket(review, a.dry_run))
    if forge == "azure":
        raise SystemExit(post_azure(review, a.dry_run))
    print(f"ERRO: forge sem adaptador de publish: {forge}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
