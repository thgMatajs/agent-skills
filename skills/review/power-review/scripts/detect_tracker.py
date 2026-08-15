#!/usr/bin/env python3
"""Detect the ticket tracker and whether an API token is ready.

Token-first. No MCP in this path. Missing token → can_fetch=false, review
continues without a Context Pack, and stdout always includes setup steps.

Jira / Linear: URL, KEY_RE (ABC-12), or a single tracker token.
Asana / Shortcut / GitHub Issues: discriminating URL only (not a bare
number, not token-alone).

Usage:
    python3 detect_tracker.py --root <repo>
    python3 detect_tracker.py --root <repo> --url https://linear.app/team/issue/ENG-12
    python3 detect_tracker.py --root <repo> --key ENG-12 --write
    python3 detect_tracker.py --hint 'feat: ABC-9 add login'

Prints JSON. Profile: <repo>/.power-review/tracker.json (never stores tokens).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_figma_spec import figma_auth  # noqa: E402

PROFILE_REL = Path(".power-review") / "tracker.json"
KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
GITHUB_ISSUE_KEY_RE = re.compile(r"^([^/#\s]+)/([^/#\s]+)#(\d+)$")
ASANA_V1_TASK_RE = re.compile(r"/task/(\d+)")
ASANA_V0_TASK_RE = re.compile(r"^/0/[^/]+/(\d+)(?:/f)?/?$")
SHORTCUT_STORY_RE = re.compile(r"/story/(\d+)(?:/|$)")
GITHUB_ISSUES_PATH_RE = re.compile(r"^/([^/]+)/([^/]+)/issues/(\d+)(?:/|$)")
LINEAR_HOSTS = ("linear.app",)
JIRA_HINTS = ("atlassian.net", "jira.")
ASANA_HOSTS = ("app.asana.com",)
SHORTCUT_HOSTS = ("app.shortcut.com",)
GITHUB_HOSTS = ("github.com", "www.github.com")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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


def asana_task_gid(path: str) -> str | None:
    """Task gid from official permalink shapes.

    V1 example: https://app.asana.com/1/12345/task/123456789
    (https://developers.asana.com/reference/gettask permalink_url)
    V0 example: https://app.asana.com/0/67890/12345
    (https://developers.asana.com/docs/quick-start)
    """
    path = path or ""
    m = ASANA_V1_TASK_RE.search(path)
    if m:
        return m.group(1)
    m = ASANA_V0_TASK_RE.match(path)
    return m.group(1) if m else None


def shortcut_story_id(path: str) -> str | None:
    """Public story id from app.shortcut.com/.../story/{id}."""
    m = SHORTCUT_STORY_RE.search(path or "")
    return m.group(1) if m else None


def parse_github_issues_key(key: str) -> tuple[str, str, str] | None:
    m = GITHUB_ISSUE_KEY_RE.match((key or "").strip())
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def github_issues_from_path(path: str) -> dict[str, str] | None:
    """github.com/{owner}/{repo}/issues/{n} — not /pull/{n}."""
    m = GITHUB_ISSUES_PATH_RE.match(path or "")
    if not m:
        return None
    owner, repo, number = m.group(1), m.group(2), m.group(3)
    return {
        "key": f"{owner}/{repo}#{number}",
        "owner": owner,
        "repo": repo,
        "number": number,
    }


def load_saved_tracker(root: Path) -> dict[str, Any] | None:
    """Reuse tracker+key from a prior --write. File has no tokens.

    Do not invent a tracker if the field is missing.
    """
    path = root / PROFILE_REL
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("tracker"):
        return None
    return data


def parse_ticket_url(url: str) -> dict[str, Any] | None:
    url = (url or "").strip()
    if not url:
        return None
    parsed = urlparse(url if "://" in url else "https://" + url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    query = parse_qs(parsed.query or "")
    key = None
    m = KEY_RE.search(path) or KEY_RE.search(url)
    if m:
        key = m.group(1)
    if not key and query.get("selectedIssue"):
        m = KEY_RE.search(query["selectedIssue"][0])
        key = m.group(1) if m else query["selectedIssue"][0]
    if host in ASANA_HOSTS:
        gid = asana_task_gid(path)
        return {"tracker": "asana" if gid else None, "key": gid, "url": url, "host": host}
    if host in SHORTCUT_HOSTS:
        sid = shortcut_story_id(path)
        if sid:
            return {"tracker": "shortcut", "key": sid, "url": url, "host": host}
        return {"tracker": None, "key": key, "url": url, "host": host}
    if host in GITHUB_HOSTS:
        gh = github_issues_from_path(path)
        if gh:
            return {"tracker": "github_issues", "url": url, "host": host, **gh}
        return {"tracker": None, "key": key, "url": url, "host": host}
    if host.endswith("linear.app") or host == "linear.app":
        return {"tracker": "linear", "key": key, "url": url, "host": host}
    if any(h in host for h in JIRA_HINTS) or "/browse/" in path:
        base = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else None
        return {"tracker": "jira", "key": key, "url": url, "host": host, "base_url": base}
    if key:
        return {"tracker": None, "key": key, "url": url, "host": host}
    return {"tracker": None, "key": None, "url": url, "host": host}


def jira_auth() -> dict[str, Any]:
    token = (
        os.environ.get("ATLASSIAN_API_TOKEN")
        or os.environ.get("JIRA_API_TOKEN")
        or ""
    ).strip()
    email = (os.environ.get("JIRA_EMAIL") or git_email() or "").strip()
    base = (os.environ.get("JIRA_BASE_URL") or "").rstrip("/")
    missing = []
    if not token:
        missing.append("JIRA_API_TOKEN (ou ATLASSIAN_API_TOKEN)")
    if not email:
        missing.append("JIRA_EMAIL (ou git user.email)")
    if not base:
        missing.append("JIRA_BASE_URL (ex. https://your-org.atlassian.net)")
    return {
        "ok": not missing,
        "missing": missing,
        "has_token": bool(token),
        "has_email": bool(email),
        "has_base": bool(base),
        "base_url": base or None,
    }


def linear_auth() -> dict[str, Any]:
    token = (
        os.environ.get("LINEAR_API_KEY")
        or os.environ.get("LINEAR_API_TOKEN")
        or ""
    ).strip()
    return {
        "ok": bool(token),
        "missing": [] if token else ["LINEAR_API_KEY"],
        "has_token": bool(token),
    }


def asana_auth() -> dict[str, Any]:
    token = (
        os.environ.get("ASANA_ACCESS_TOKEN")
        or os.environ.get("ASANA_TOKEN")
        or ""
    ).strip()
    return {
        "ok": bool(token),
        "missing": [] if token else ["ASANA_ACCESS_TOKEN (ou ASANA_TOKEN)"],
        "has_token": bool(token),
    }


def shortcut_auth() -> dict[str, Any]:
    token = (
        os.environ.get("SHORTCUT_TOKEN")
        or os.environ.get("SHORTCUT_API_TOKEN")
        or ""
    ).strip()
    return {
        "ok": bool(token),
        "missing": [] if token else ["SHORTCUT_TOKEN (ou SHORTCUT_API_TOKEN)"],
        "has_token": bool(token),
    }


def github_issues_auth() -> dict[str, Any]:
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    return {
        "ok": bool(token),
        "missing": [] if token else ["GITHUB_TOKEN (ou GH_TOKEN)"],
        "has_token": bool(token),
    }


def pick_tracker(
    url_info: dict[str, Any] | None,
    key: str | None,
    hint: str | None,
    saved: dict[str, Any] | None = None,
) -> tuple[str | None, str, str | None]:
    if url_info and url_info.get("tracker"):
        return url_info["tracker"], "url", url_info.get("key") or key
    extracted = key
    if not extracted and url_info:
        extracted = url_info.get("key")
    if not extracted and hint:
        m = KEY_RE.search(hint)
        extracted = m.group(1) if m else None
    if saved and saved.get("tracker"):
        return saved["tracker"], "profile", extracted or saved.get("key")
    jira = jira_auth()
    linear = linear_auth()
    jira_ready = bool(jira["ok"] or jira["has_token"])
    linear_ready = bool(linear["ok"] or linear["has_token"])
    if jira_ready and not linear_ready:
        return "jira", "token", extracted
    if linear_ready and not jira_ready:
        return "linear", "token", extracted
    if jira_ready and linear_ready:
        return None, "ambiguous_tokens", extracted
    return None, "unknown", extracted


def instructor(tracker: str | None, can_fetch: bool, auth: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    if can_fetch:
        headline = (
            f"Tracker {tracker} + API token ok. Vou buscar o Context Pack "
            "(profile review). Figma: REST se houver URL no ticket e "
            "FIGMA_ACCESS_TOKEN / FIGMA_TOKEN."
        )
        steps = []
    elif tracker == "jira":
        headline = (
            "Jira detectado, mas falta API token/base. Review segue SEM Context Pack. "
            "Configure as env e rode o detector de novo."
        )
        steps = [
            "Crie um API token: https://id.atlassian.com/manage-profile/security/api-tokens",
            "export JIRA_BASE_URL='https://your-org.atlassian.net'",
            "export JIRA_EMAIL='voce@empresa.com'",
            "export JIRA_API_TOKEN='<token>'",
            "python3 $SKILL_DIR/scripts/detect_tracker.py --root . --key <KEY>",
        ]
    elif tracker == "linear":
        headline = (
            "Linear detectado, mas falta LINEAR_API_KEY. Review segue SEM Context Pack. "
            "Configure a env e rode o detector de novo."
        )
        steps = [
            "Linear → Settings → Account → Security & access → Personal API keys",
            "export LINEAR_API_KEY='lin_api_...'",
            "python3 $SKILL_DIR/scripts/detect_tracker.py --root . --key ENG-123",
        ]
    elif tracker == "asana":
        headline = (
            "Asana detectado, mas falta ASANA_ACCESS_TOKEN. Review segue SEM Context Pack. "
            "Configure a env e rode o detector de novo."
        )
        steps = [
            "Gere um PAT: https://app.asana.com/0/my-apps",
            "Docs: https://developers.asana.com/docs/personal-access-token",
            "export ASANA_ACCESS_TOKEN='<token>'   # ou ASANA_TOKEN",
            "Header oficial: Authorization: Bearer <token>",
            "python3 $SKILL_DIR/scripts/detect_tracker.py --root . --url '<url da task Asana>'",
        ]
    elif tracker == "shortcut":
        headline = (
            "Shortcut detectado, mas falta SHORTCUT_TOKEN. Review segue SEM Context Pack. "
            "Configure a env e rode o detector de novo."
        )
        steps = [
            "Gere um token: https://app.shortcut.com/settings/account/api-tokens",
            "Docs: https://developer.shortcut.com/api/rest/v3",
            "export SHORTCUT_TOKEN='<token>'   # ou SHORTCUT_API_TOKEN",
            "Header oficial: Shortcut-Token",
            "python3 $SKILL_DIR/scripts/detect_tracker.py --root . --url '<url da story Shortcut>'",
        ]
    elif tracker == "github_issues":
        headline = (
            "GitHub Issues detectado, mas falta GITHUB_TOKEN / GH_TOKEN. "
            "Review segue SEM Context Pack. Configure a env e rode o detector de novo."
        )
        steps = [
            "Crie um PAT: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens",
            "Fine-grained: permission Issues = read "
            "(https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens)",
            "export GITHUB_TOKEN='<token>'   # ou GH_TOKEN",
            "Header oficial: Authorization: Bearer <token>",
            "python3 $SKILL_DIR/scripts/detect_tracker.py --root . --url 'https://github.com/org/repo/issues/12'",
        ]
    elif not tracker:
        headline = (
            "Tracker não identificado (Jira / Linear / Asana / Shortcut / GitHub Issues). "
            "Review segue SEM Context Pack. Passe a URL do ticket ou a chave Jira/Linear "
            "(ABC-12 / ENG-12)."
        )
        steps = [
            "Jira: URL .../browse/ABC-12 + JIRA_BASE_URL + JIRA_EMAIL + JIRA_API_TOKEN",
            "Linear: URL linear.app/.../ENG-12 + LINEAR_API_KEY",
            "Asana: URL app.asana.com/.../task/{gid} + ASANA_ACCESS_TOKEN",
            "Shortcut: URL app.shortcut.com/.../story/{id} + SHORTCUT_TOKEN",
            "GitHub Issues: URL github.com/{owner}/{repo}/issues/{n} + GITHUB_TOKEN "
            "(não /pull/{n})",
            "Docs: references/trackers/setup.md",
        ]
    else:
        headline = "Tracker sem token. Review segue SEM Context Pack."
        steps = ["Ver references/trackers/setup.md"]
    return {
        "headline": headline,
        "reasons": reasons,
        "steps": steps,
        "docs": "references/trackers/setup.md",
        "missing": auth.get("missing") or [],
    }


def _auth_for(tracker: str | None, jira: dict[str, Any], linear: dict[str, Any]) -> dict[str, Any]:
    if tracker == "jira":
        return jira
    if tracker == "linear":
        return linear
    if tracker == "asana":
        return asana_auth()
    if tracker == "shortcut":
        return shortcut_auth()
    if tracker == "github_issues":
        return github_issues_auth()
    return {"ok": False, "missing": []}


def build_profile(
    url: str | None,
    key: str | None,
    hint: str | None,
    saved: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url_info = parse_ticket_url(url) if url else None
    tracker, source, resolved_key = pick_tracker(
        url_info, key, hint, saved=None if url else saved
    )
    reasons: list[str] = []
    if source == "ambiguous_tokens":
        reasons.append("JIRA_* e LINEAR_API_KEY estão setados — passe a URL do ticket")
    if source == "unknown" and not resolved_key:
        reasons.append("sem URL, sem chave e sem token")
    if url_info and url_info.get("base_url") and tracker == "jira":
        # URL already has the site; token+email enough even without JIRA_BASE_URL
        pass

    jira = jira_auth()
    linear = linear_auth()
    asana = asana_auth()
    shortcut = shortcut_auth()
    github_issues = github_issues_auth()
    figma = figma_auth()
    if tracker == "jira" and url_info and url_info.get("base_url"):
        jira = dict(jira)
        jira["base_url"] = url_info["base_url"]
        jira["has_base"] = True
        jira["missing"] = [m for m in jira["missing"] if "JIRA_BASE_URL" not in m]
        jira["ok"] = bool(jira["has_token"] and jira["has_email"])
    auth = _auth_for(tracker, jira, linear)
    can_fetch = bool(tracker and auth.get("ok") and resolved_key)
    if tracker and auth.get("ok") and not resolved_key:
        reasons.append("token ok, mas sem chave/URL do ticket — extraia do título do MR/PR")
    if tracker == "jira" and not (url_info and url_info.get("base_url")) and not jira.get("has_base"):
        if "JIRA_BASE_URL" not in reasons:
            reasons.append("Jira precisa de JIRA_BASE_URL ou da URL do ticket")

    return {
        "tracker": tracker,
        "source": source,
        "key": resolved_key,
        "url": (url_info or {}).get("url") or url or (saved or {}).get("url"),
        "can_fetch": can_fetch,
        "auth": {
            "jira": jira,
            "linear": linear,
            "asana": asana,
            "shortcut": shortcut,
            "github_issues": github_issues,
            "figma": figma,
        },
        "detected_at": now_iso(),
        "instructor": instructor(tracker, can_fetch, auth, reasons),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect tracker and API-token readiness.")
    ap.add_argument("--root", default=".", help="Repo root (for .power-review/)")
    ap.add_argument("--url", default=None, help="Ticket URL (Jira, Linear, Asana, Shortcut, GitHub Issues)")
    ap.add_argument("--key", default=None, help="Ticket key (ABC-12 / ENG-12 / owner/repo#n)")
    ap.add_argument("--hint", default=None, help="MR/PR title+description+branch to extract a key")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"root is not a directory: {root}"}, ensure_ascii=False))
        return 2

    key = args.key
    if key:
        m = KEY_RE.search(key)
        key = m.group(1) if m else key

    profile = build_profile(args.url, key, args.hint)
    dest = root / PROFILE_REL
    action = "detected"
    if args.write:
        existed = dest.is_file()
        dest.parent.mkdir(parents=True, exist_ok=True)
        slim = {k: v for k, v in profile.items() if k != "auth"}
        slim["auth_ok"] = profile["can_fetch"]
        dest.write_text(json.dumps(slim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        action = "updated" if existed else "created"
    profile["action"] = action
    profile["profile_path"] = str(dest)
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
