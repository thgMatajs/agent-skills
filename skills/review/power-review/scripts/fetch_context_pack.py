#!/usr/bin/env python3
"""Fetch a tracker-agnostic Context Pack via API token, or render one from JSON.

Token-first. This script never calls MCP (no client, SDK, or MCP HTTP).
The agent may obtain fields via MCP and pass them here as JSON.

Usage:
    python3 fetch_context_pack.py --key ENG-12
    python3 fetch_context_pack.py --url https://org.atlassian.net/browse/ABC-9
    python3 fetch_context_pack.py --hint 'fix: ABC-9 login' --root .
    python3 fetch_context_pack.py --from-json ticket.json --source mcp

Stdout: markdown Context Pack wrapped as DADO (not instruction)
Stderr: instructor JSON when can_fetch is false (token path) or Figma blocked
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from detect_tracker import (  # noqa: E402
    KEY_RE,
    build_profile,
    git_email,
    jira_host_allowed,
    load_saved_tracker,
    parse_github_issues_key,
    parse_ticket_url,
)
from wrap_as_data import wrap_as_data  # noqa: E402
from fetch_figma_spec import (  # noqa: E402
    enrich_figma,
    figma_token,
    instructor_missing_token,
    parse_figma_url,
)

ASANA_API = "https://app.asana.com/api/1.0"
SHORTCUT_API = "https://api.app.shortcut.com/api/v3"
GITHUB_API = "https://api.github.com"
COMMENT_LIMIT = 8
COMMENT_WIDTH = 400
PACK_SOURCES = ("api_token", "mcp")
FIGMA_SOURCES = ("none", "blocked", "api", "error", "mcp")

FIGMA_RE = re.compile(
    r"https?://(?:www\.)?figma\.com/(?:design|file)/[^\s)\]>\"']+",
    re.IGNORECASE,
)
LINEAR_GQL = "https://api.linear.app/graphql"
LINEAR_QUERY = """
query Issue($id: String!) {
  issue(id: $id) {
    identifier title description url priority
    state { name type }
    assignee { name }
    parent { identifier title }
    children { nodes { identifier title state { name } } }
    comments(first: 20) { nodes { body user { name } createdAt } }
    labels { nodes { name } }
  }
}
"""


def adf_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(p for p in (adf_text(x) for x in node) if p)
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text") or ""
    if node.get("type") == "inlineCard":
        return ((node.get("attrs") or {}).get("url")) or ""
    if node.get("type") == "hardBreak":
        return "\n"
    return "\n".join(p for p in (adf_text(c) for c in node.get("content") or []) if p)


def find_figma(*texts: str) -> list[str]:
    found: list[str] = []
    for text in texts:
        for m in FIGMA_RE.findall(text or ""):
            if m not in found:
                found.append(m)
    return found


def bullets(items: list[str], empty: str = "N/A") -> str:
    items = [i.strip() for i in items if i and str(i).strip()]
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {i}" for i in items)


def acs_from_text(text: str) -> list[str]:
    out: list[str] = []
    for line in (text or "").splitlines():
        s = line.strip()
        if re.match(r"^[-*]\s*\[[ xX]\]\s+", s) or re.match(r"^[-*]\s+(AC|Given|When|Then)\b", s, re.I):
            out.append(re.sub(r"^[-*]\s*", "", s))
    return out[:20]


def http_json(url: str, headers: dict[str, str], payload: dict | None = None) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=45) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _jira_base_url(url_info: dict[str, Any] | None) -> str:
    """Only Atlassian Cloud or JIRA_BASE_URL / JIRA_ALLOWED_HOSTS — never a random /browse/ host."""
    url_base = ((url_info or {}).get("base_url") or "").rstrip("/")
    if url_base:
        host = urlparse(url_base).hostname or ""
        if jira_host_allowed(host):
            return url_base
    env = (os.environ.get("JIRA_BASE_URL") or "").rstrip("/")
    if env:
        raw = env if "://" in env else "https://" + env
        if urlparse(raw).hostname:
            return env
    return ""


def fetch_jira(key: str, base_url: str) -> dict[str, Any]:
    host = urlparse(base_url if "://" in base_url else "https://" + base_url).hostname or ""
    if not jira_host_allowed(host):
        raise ValueError(f"jira host not allowlisted: {host}")
    token = (os.environ.get("ATLASSIAN_API_TOKEN") or os.environ.get("JIRA_API_TOKEN") or "").strip()
    email = (os.environ.get("JIRA_EMAIL") or git_email() or "").strip()
    raw = f"{email}:{token}".encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": "Basic " + base64.b64encode(raw).decode("ascii"),
        "User-Agent": "power-review/context-pack",
    }
    fields = "summary,status,issuetype,description,comment,parent,subtasks"
    issue = http_json(
        f"{base_url.rstrip('/')}/rest/api/3/issue/{urllib_quote(key)}?fields={fields}",
        headers,
    )
    fields_d = issue.get("fields") or {}
    desc = adf_text(fields_d.get("description"))
    comments = []
    for c in ((fields_d.get("comment") or {}).get("comments") or [])[-8:]:
        body = adf_text(c.get("body"))
        author = ((c.get("author") or {}).get("displayName")) or "?"
        if body:
            comments.append(f"{author}: {body[:400]}")
    parent = fields_d.get("parent") or {}
    parent_key = parent.get("key")
    parent_sum = ((parent.get("fields") or {}).get("summary")) or ""
    siblings = []
    for s in fields_d.get("subtasks") or []:
        st = ((s.get("fields") or {}).get("status") or {}).get("name") or ""
        siblings.append(f"{s.get('key')} — {(s.get('fields') or {}).get('summary')} — {st}")
    figma = find_figma(desc, "\n".join(comments))
    return {
        "key": issue.get("key") or key,
        "type": ((fields_d.get("issuetype") or {}).get("name")) or "N/A",
        "summary": fields_d.get("summary") or "N/A",
        "status": ((fields_d.get("status") or {}).get("name")) or "N/A",
        "description": desc,
        "parent": f"{parent_key} — {parent_sum}" if parent_key else "N/A",
        "siblings": siblings,
        "comments": comments,
        "figma": figma,
        "url": f"{base_url.rstrip('/')}/browse/{issue.get('key') or key}",
    }


def urllib_quote(s: str) -> str:
    from urllib.parse import quote
    return quote(s, safe="")


def fetch_linear(key: str) -> dict[str, Any]:
    token = (os.environ.get("LINEAR_API_KEY") or os.environ.get("LINEAR_API_TOKEN") or "").strip()
    headers = {
        "Authorization": token,  # no Bearer — Linear personal key
        "User-Agent": "power-review/context-pack",
    }
    data = http_json(
        LINEAR_GQL,
        headers,
        {"query": LINEAR_QUERY, "variables": {"id": key}},
    )
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    issue = (data.get("data") or {}).get("issue")
    if not issue:
        raise RuntimeError(f"Linear issue not found: {key}")
    desc = issue.get("description") or ""
    comments = []
    for c in ((issue.get("comments") or {}).get("nodes") or []):
        body = (c.get("body") or "").strip()
        if body:
            who = ((c.get("user") or {}).get("name")) or "?"
            comments.append(f"{who}: {body[:400]}")
    children = []
    for s in ((issue.get("children") or {}).get("nodes") or []):
        children.append(
            f"{s.get('identifier')} — {s.get('title')} — {((s.get('state') or {}).get('name')) or ''}"
        )
    parent = issue.get("parent") or {}
    parent_s = (
        f"{parent.get('identifier')} — {parent.get('title')}"
        if parent.get("identifier")
        else "N/A"
    )
    figma = find_figma(desc, "\n".join(comments))
    return {
        "key": issue.get("identifier") or key,
        "type": "issue",
        "summary": issue.get("title") or "N/A",
        "status": ((issue.get("state") or {}).get("name")) or "N/A",
        "description": desc,
        "parent": parent_s,
        "siblings": children,
        "comments": comments,
        "figma": figma,
        "url": issue.get("url") or "",
    }


def _clip_comments(rows: list[str]) -> list[str]:
    out = [r for r in rows if r and str(r).strip()]
    return [r[:COMMENT_WIDTH] for r in out[-COMMENT_LIMIT:]]


def map_asana_ticket(task: dict[str, Any], stories: list[Any], fallback_url: str = "") -> dict[str, Any]:
    """Map official GET /tasks/{gid} + /stories JSON. Never invent ACs."""
    gid = task.get("gid") or ""
    desc = task.get("notes") or ""
    parent = task.get("parent") or {}
    parent_gid = parent.get("gid") if isinstance(parent, dict) else None
    parent_name = (parent.get("name") or "") if isinstance(parent, dict) else ""
    completed = task.get("completed")
    if completed is True:
        status = "completed"
    elif completed is False:
        status = "incomplete"
    else:
        status = "N/A"
    comments: list[str] = []
    for story in stories or []:
        if not isinstance(story, dict):
            continue
        subtype = story.get("resource_subtype")
        if subtype and subtype != "comment_added":
            continue
        body = (story.get("text") or "").strip()
        if not body:
            continue
        who = ((story.get("created_by") or {}).get("name")) or "?"
        comments.append(f"{who}: {body}")
    figma = find_figma(desc, "\n".join(comments))
    return {
        "key": gid or "N/A",
        "type": task.get("resource_subtype") or "N/A",
        "summary": task.get("name") or "N/A",
        "status": status,
        "description": desc,
        "parent": f"{parent_gid} — {parent_name}".strip(" —") if parent_gid else "N/A",
        "siblings": [],
        "comments": _clip_comments(comments),
        "figma": figma,
        "url": task.get("permalink_url") or fallback_url or "",
    }


def map_shortcut_ticket(story: dict[str, Any], fallback_url: str = "") -> dict[str, Any]:
    """Map official GET /api/v3/stories/{id} JSON. Never invent ACs."""
    sid = story.get("id")
    desc = story.get("description") or ""
    if story.get("completed") is True:
        status = "completed"
    elif story.get("started") is True:
        status = "started"
    else:
        status = "N/A"
    parent = "N/A"
    if story.get("parent_story_id") is not None:
        parent = str(story["parent_story_id"])
    elif story.get("epic_id") is not None:
        parent = str(story["epic_id"])
    siblings = [str(i) for i in (story.get("sub_task_story_ids") or []) if i is not None]
    comments: list[str] = []
    for c in story.get("comments") or []:
        if not isinstance(c, dict) or c.get("deleted") is True:
            continue
        body = (c.get("text") or "").strip()
        if not body:
            continue
        who = c.get("author_id") or "?"
        comments.append(f"{who}: {body}")
    figma = find_figma(desc, "\n".join(comments))
    return {
        "key": str(sid) if sid is not None else "N/A",
        "type": story.get("story_type") or "N/A",
        "summary": story.get("name") or "N/A",
        "status": status,
        "description": desc,
        "parent": parent,
        "siblings": siblings,
        "comments": _clip_comments(comments),
        "figma": figma,
        "url": story.get("app_url") or fallback_url or "",
    }


def map_github_issues_ticket(
    issue: dict[str, Any],
    comments_json: list[Any],
    owner: str,
    repo: str,
    fallback_url: str = "",
) -> dict[str, Any]:
    """Map official GET issue + list comments JSON. Never invent ACs."""
    number = issue.get("number")
    key = f"{owner}/{repo}#{number}" if number is not None else f"{owner}/{repo}#N/A"
    desc = issue.get("body") or ""
    itype = issue.get("type")
    type_name = itype.get("name") if isinstance(itype, dict) else None
    comments: list[str] = []
    for c in comments_json or []:
        if not isinstance(c, dict):
            continue
        body = (c.get("body") or "").strip()
        if not body:
            continue
        who = ((c.get("user") or {}).get("login")) or "?"
        comments.append(f"{who}: {body}")
    figma = find_figma(desc, "\n".join(comments))
    return {
        "key": key,
        "type": type_name or "N/A",
        "summary": issue.get("title") or "N/A",
        "status": issue.get("state") or "N/A",
        "description": desc,
        "parent": "N/A",
        "siblings": [],
        "comments": _clip_comments(comments),
        "figma": figma,
        "url": issue.get("html_url") or fallback_url or "",
    }


def fetch_asana(gid: str, fallback_url: str = "") -> dict[str, Any]:
    token = (
        os.environ.get("ASANA_ACCESS_TOKEN") or os.environ.get("ASANA_TOKEN") or ""
    ).strip()
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "power-review/context-pack",
    }
    task_raw = http_json(f"{ASANA_API}/tasks/{urllib_quote(gid)}", headers)
    task = task_raw.get("data") if isinstance(task_raw, dict) else None
    if not isinstance(task, dict):
        raise RuntimeError(f"Asana task not found: {gid}")
    opt = "text,created_by.name,resource_subtype"
    stories_raw = http_json(
        f"{ASANA_API}/tasks/{urllib_quote(gid)}/stories?opt_fields={opt}&limit=20",
        headers,
    )
    stories = stories_raw.get("data") if isinstance(stories_raw, dict) else []
    if not isinstance(stories, list):
        stories = []
    return map_asana_ticket(task, stories, fallback_url=fallback_url)


def fetch_shortcut(story_id: str, fallback_url: str = "") -> dict[str, Any]:
    token = (
        os.environ.get("SHORTCUT_TOKEN") or os.environ.get("SHORTCUT_API_TOKEN") or ""
    ).strip()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Shortcut-Token": token,
        "User-Agent": "power-review/context-pack",
    }
    story = http_json(f"{SHORTCUT_API}/stories/{urllib_quote(str(story_id))}", headers)
    if not isinstance(story, dict) or story.get("id") is None:
        raise RuntimeError(f"Shortcut story not found: {story_id}")
    return map_shortcut_ticket(story, fallback_url=fallback_url)


def fetch_github_issues(
    owner: str,
    repo: str,
    number: str,
    fallback_url: str = "",
) -> dict[str, Any]:
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "power-review/context-pack",
    }
    issue = http_json(
        f"{GITHUB_API}/repos/{urllib_quote(owner)}/{urllib_quote(repo)}/issues/{urllib_quote(str(number))}",
        headers,
    )
    if not isinstance(issue, dict) or issue.get("number") is None:
        raise RuntimeError(f"GitHub issue not found: {owner}/{repo}#{number}")
    comments = http_json(
        f"{GITHUB_API}/repos/{urllib_quote(owner)}/{urllib_quote(repo)}/issues/{urllib_quote(str(number))}/comments?per_page=20",
        headers,
    )
    if not isinstance(comments, list):
        comments = []
    return map_github_issues_ticket(
        issue, comments, owner, repo, fallback_url=fallback_url
    )


def _figma_items(items: list[dict[str, str]]) -> str:
    if not items:
        return "- N/A"
    lines = []
    for it in items:
        nid = it.get("id") or "?"
        name = it.get("name") or "?"
        ntype = it.get("type") or "?"
        lines.append(f"- {name} (`{nid}`, {ntype})")
    return "\n".join(lines)


def _na(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return "N/A"
    if isinstance(value, str):
        return value if value.strip() else "N/A"
    if isinstance(value, (int, float)):
        return str(value)
    return "N/A"


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def ticket_from_json(raw: dict[str, Any]) -> dict[str, Any]:
    """Map provided ticket keys only. Extra keys ignored. Missing → N/A."""
    key_raw = raw.get("key")
    if isinstance(key_raw, bool) or key_raw is None:
        raise ValueError("missing key")
    if isinstance(key_raw, str):
        key = key_raw.strip()
    elif isinstance(key_raw, (int, float)):
        key = str(key_raw)
    else:
        raise ValueError("missing key")
    if not key:
        raise ValueError("missing key")
    desc = raw.get("description")
    if desc is None:
        description = ""
    elif isinstance(desc, dict):
        description = adf_text(desc)
    elif isinstance(desc, str):
        description = desc
    else:
        description = str(desc)
    url_raw = raw.get("url")
    if url_raw is None:
        url = ""
    elif isinstance(url_raw, str):
        url = url_raw
    else:
        url = str(url_raw)
    return {
        "key": key,
        "type": _na(raw.get("type")),
        "summary": _na(raw.get("summary")),
        "status": _na(raw.get("status")),
        "description": description,
        "parent": _na(raw.get("parent")),
        "siblings": _as_str_list(raw.get("siblings")),
        "comments": _as_str_list(raw.get("comments")),
        "figma": _as_str_list(raw.get("figma")),
        "url": url,
    }


def figma_block_from_json(raw: Any) -> dict[str, Any] | None:
    """Same shape enrich_figma produces. Absent / non-object → None."""
    if not isinstance(raw, dict):
        return None
    src = raw.get("source")
    if src not in FIGMA_SOURCES:
        src = "none"
    frames = raw.get("frames") if isinstance(raw.get("frames"), list) else []
    states = raw.get("states") if isinstance(raw.get("states"), list) else []
    blockers = raw.get("blockers") if isinstance(raw.get("blockers"), list) else []
    urls = raw.get("urls") if isinstance(raw.get("urls"), list) else []
    return {
        "source": src,
        "url": raw.get("url") or "",
        "urls": [u for u in urls if isinstance(u, str) and u],
        "file_key": raw.get("file_key"),
        "node_id": raw.get("node_id"),
        "file_name": raw.get("file_name"),
        "frames": [f for f in frames if isinstance(f, dict)],
        "states": [s for s in states if isinstance(s, dict)],
        "blockers": [b for b in blockers if isinstance(b, str) and b],
    }


def blocked_figma_from_urls(urls: list[str]) -> dict[str, Any]:
    clean: list[str] = []
    for u in urls or []:
        u = (u or "").strip().rstrip(".,;)]>'\"")
        if u and u not in clean:
            clean.append(u)
    parsed = None
    for u in clean:
        parsed = parse_figma_url(u)
        if parsed:
            break
    return {
        "source": "blocked",
        "url": clean[0] if clean else "",
        "urls": clean,
        "file_key": (parsed or {}).get("file_key"),
        "node_id": (parsed or {}).get("node_id"),
        "file_name": None,
        "frames": [],
        "states": [],
        "blockers": ["sem FIGMA_ACCESS_TOKEN / FIGMA_TOKEN"],
        "instructor": instructor_missing_token(),
    }


def resolve_figma_from_json(
    ticket: dict[str, Any],
    figma_block: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if figma_block is not None:
        return figma_block
    urls = ticket.get("figma") or []
    if not urls:
        return None
    if figma_token():
        return enrich_figma(urls)
    return blocked_figma_from_urls(urls)


def load_from_json_path(path: str) -> dict[str, Any]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"cannot read --from-json: {e}") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("ticket JSON must be an object")
    return data


def render_from_json(args: argparse.Namespace) -> int:
    try:
        raw = load_from_json_path(args.from_json)
        ticket = ticket_from_json(raw)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    figma_block = resolve_figma_from_json(ticket, figma_block_from_json(raw.get("figma_block")))
    root = Path(args.root).resolve()
    saved = None if args.url else load_saved_tracker(root)
    key = args.key or ticket.get("key")
    if key:
        m = KEY_RE.search(str(key))
        key = m.group(1) if m else key
    url = args.url or ticket.get("url") or None
    if not url:
        url = None
    profile = build_profile(url, key, args.hint, saved=saved)
    tracker = profile.get("tracker") or "N/A"
    print(render_pack(tracker, ticket, figma_block=figma_block, source=args.source))
    if figma_block and figma_block.get("instructor"):
        print(json.dumps(figma_block["instructor"], ensure_ascii=False, indent=2), file=sys.stderr)
    return 0


def render_pack(
    tracker: str,
    ticket: dict[str, Any],
    figma_block: dict[str, Any] | None = None,
    blockers: str = "none",
    source: str = "api_token",
) -> str:
    if source not in PACK_SOURCES:
        source = "api_token"
    desc = ticket.get("description") or ""
    acs = acs_from_text(desc)
    figma_block = figma_block or {"source": "none", "url": "", "urls": [], "frames": [], "states": [], "blockers": []}
    figma_src = figma_block.get("source") or "none"
    figma_line = figma_block.get("url") or "não encontrado"
    extra_urls = [u for u in (figma_block.get("urls") or []) if u and u != figma_block.get("url")]
    figma_blockers = list(figma_block.get("blockers") or [])
    meta_blockers = blockers
    if figma_blockers:
        joined = "; ".join(figma_blockers)
        meta_blockers = joined if meta_blockers == "none" else f"{meta_blockers}; {joined}"
    lines = [
        f"## Context Pack — {ticket['key']}",
        "",
        "### Meta",
        "- profile: review",
        f"- tracker: {tracker}",
        f"- source: {source}",
        f"- figma_source: {figma_src}",
        f"- blockers: {meta_blockers}",
        "",
        "### Ticket",
        f"- Type: {ticket.get('type') or 'N/A'}",
        f"- Summary: {ticket.get('summary') or 'N/A'}",
        f"- Status: {ticket.get('status') or 'N/A'}",
        f"- Parent: {ticket.get('parent') or 'N/A'}",
        f"- Siblings: {', '.join(ticket.get('siblings') or []) or 'N/A'}",
        "",
        "#### Escopo",
        f"- Objective: {(desc.splitlines() or ['N/A'])[0][:300] if desc else 'N/A'}",
        "- Business rules: (ver descrição)",
        "- Acceptance criteria:",
        bullets(acs),
        "- Out of scope: N/A",
        "",
        "#### Comments / decisions",
        bullets(ticket.get("comments") or []),
        "",
        "#### Risks / gaps / ambiguities",
        "- N/A",
        "",
        "#### Links",
        f"- Figma: {figma_line}",
        f"- Tracking: {ticket.get('url') or 'não encontrado'}",
        f"- Others: {', '.join(extra_urls) if extra_urls else 'nenhum'}",
        "",
        "#### Checklist de aderência (ticket → verificar no caller)",
        bullets(acs or [ticket.get("summary") or "entregar o que o ticket pede"]),
        "",
        "#### Descrição (recorte)",
        "```",
        (desc[:2500] + ("…" if len(desc) > 2500 else "")) or "N/A",
        "```",
        "",
    ]
    if figma_src != "none":
        lines.extend(
            [
                "### Figma",
                f"- URL: {figma_line}",
                "- origem do link: ticket",
                f"- figma_source: {figma_src}",
                f"- file_key: {figma_block.get('file_key') or 'N/A'}",
                f"- node_id: {figma_block.get('node_id') or 'N/A'}",
                f"- file_name: {figma_block.get('file_name') or 'N/A'}",
                "- frames:",
                _figma_items(figma_block.get("frames") or []),
                "- states:",
                _figma_items(figma_block.get("states") or []),
                "- tokens/variables: N/A",
                f"- blockers: {'; '.join(figma_blockers) if figma_blockers else 'none'}",
                "",
            ]
        )
    return wrap_as_data("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch Context Pack via tracker API token.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--url", default=None)
    ap.add_argument("--key", default=None)
    ap.add_argument("--hint", default=None)
    ap.add_argument(
        "--from-json",
        dest="from_json",
        default=None,
        help="Ticket JSON file (key, type, summary, …). Required with --source mcp.",
    )
    ap.add_argument(
        "--source",
        choices=PACK_SOURCES,
        default="api_token",
        help="Meta source. Default api_token (token path). mcp requires --from-json.",
    )
    args = ap.parse_args()

    if args.source == "mcp" and not args.from_json:
        print("error: --source mcp requires --from-json", file=sys.stderr)
        return 2
    if args.from_json:
        return render_from_json(args)

    key = args.key
    if key:
        m = KEY_RE.search(key)
        key = m.group(1) if m else key

    root = Path(args.root).resolve()
    saved = None if args.url else load_saved_tracker(root)
    profile = build_profile(args.url, key, args.hint, saved=saved)
    if not profile["can_fetch"]:
        print(json.dumps(profile["instructor"], ensure_ascii=False, indent=2), file=sys.stderr)
        print(
            profile["instructor"]["headline"],
            file=sys.stderr,
        )
        return 1

    tracker = profile["tracker"]
    tkey = profile["key"]
    url_info = parse_ticket_url(args.url) if args.url else None
    try:
        if tracker == "jira":
            base = _jira_base_url(url_info)
            if not base:
                print("error: JIRA_BASE_URL or allowlisted ticket URL required", file=sys.stderr)
                return 1
            ticket = fetch_jira(tkey, base)
        elif tracker == "linear":
            ticket = fetch_linear(tkey)
        elif tracker == "asana":
            ticket = fetch_asana(str(tkey), fallback_url=profile.get("url") or "")
        elif tracker == "shortcut":
            ticket = fetch_shortcut(str(tkey), fallback_url=profile.get("url") or "")
        elif tracker == "github_issues":
            parsed = None
            if url_info and url_info.get("owner"):
                parsed = (url_info["owner"], url_info["repo"], url_info["number"])
            else:
                parsed = parse_github_issues_key(str(tkey or ""))
            if not parsed:
                print("error: github_issues key must be owner/repo#n", file=sys.stderr)
                return 1
            owner, repo, number = parsed
            ticket = fetch_github_issues(
                owner, repo, str(number), fallback_url=profile.get("url") or ""
            )
        else:
            print("error: unknown tracker", file=sys.stderr)
            return 1
    except urllib.error.HTTPError as e:
        print(f"error: {tracker} HTTP {e.code} {e.reason}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"error: {tracker} {e}", file=sys.stderr)
        return 1

    figma_block = enrich_figma(ticket.get("figma") or [])
    print(render_pack(tracker, ticket, figma_block=figma_block, source="api_token"))
    if figma_block.get("instructor"):
        print(json.dumps(figma_block["instructor"], ensure_ascii=False, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
