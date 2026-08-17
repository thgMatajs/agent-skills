#!/usr/bin/env python3
"""Slim Figma spec via official REST (token header). No MCP. No layout invention.

Env: FIGMA_ACCESS_TOKEN or FIGMA_TOKEN — never written to disk / .power-review/.
Docs: references/trackers/figma.md
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from urllib.parse import parse_qs, urlparse

# Official REST base: https://developers.figma.com/docs/rest-api/
FIGMA_API_BASE = "https://api.figma.com"
TOKEN_ENVS = ("FIGMA_ACCESS_TOKEN", "FIGMA_TOKEN")
FRAME_TYPES = frozenset(
    {"FRAME", "COMPONENT", "COMPONENT_SET", "INSTANCE", "SECTION", "CANVAS"}
)
MAX_LISTED = 40
PAT_HELP = "https://help.figma.com/hc/en-us/articles/8085703771159-Manage-personal-access-tokens"
PAT_DOCS = "https://developers.figma.com/docs/rest-api/personal-access-tokens/"


def figma_token() -> str:
    for key in TOKEN_ENVS:
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return ""


def figma_auth() -> dict[str, Any]:
    token = figma_token()
    return {
        "ok": bool(token),
        "has_token": bool(token),
        "missing": [] if token else ["FIGMA_ACCESS_TOKEN (ou FIGMA_TOKEN)"],
    }


def instructor_missing_token() -> dict[str, Any]:
    return {
        "headline": (
            "Link Figma no ticket, mas sem FIGMA_ACCESS_TOKEN / FIGMA_TOKEN. "
            "Review segue; bloco Figma fica blocked (sem frames inventados)."
        ),
        "reasons": ["figma_url_without_token"],
        "steps": [
            f"Gere um personal access token: {PAT_HELP}",
            f"Passos oficiais: {PAT_DOCS}",
            "Figma → menu da conta (canto superior esquerdo) → Settings → aba Security",
            "Personal access tokens → Generate new token",
            "Escopo mínimo: file_content:read (GET /v1/files e /v1/files/:key/nodes)",
            "export FIGMA_ACCESS_TOKEN='<token>'   # ou FIGMA_TOKEN",
            "NÃO grave o token em .power-review/ nem em arquivo do repo",
            "python3 $SKILL_DIR/scripts/fetch_context_pack.py --root . --key <KEY>",
        ],
        "docs": "references/trackers/figma.md",
        "missing": ["FIGMA_ACCESS_TOKEN (ou FIGMA_TOKEN)"],
    }


def node_id_to_api(raw: str) -> str:
    """URL node-id uses hyphen; REST ids use colon (official examples: ids=1:2)."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if ":" in raw:
        return raw
    return raw.replace("-", ":")


def figma_host_allowed(host: str) -> bool:
    """figma.com or a subdomain — not evilfigma.com."""
    host = (host or "").lower().rstrip(".")
    return host == "figma.com" or host.endswith(".figma.com")


def parse_figma_url(url: str) -> dict[str, Any] | None:
    """Parse https://www.figma.com/:file_type/:file_key/:file_name?node-id=:id

    Official: https://developers.figma.com/docs/rest-api/file-endpoints/
    node-id hyphen → colon: https://developers.figma.com/docs/embeds/resources/
    """
    url = (url or "").strip().rstrip(".,;)]>'\"")
    if not url:
        return None
    parsed = urlparse(url if "://" in url else "https://" + url)
    host = (parsed.hostname or "").lower()
    if not figma_host_allowed(host):
        return None
    parts = [p for p in (parsed.path or "").split("/") if p]
    if len(parts) < 2:
        return None
    file_type = parts[0].lower()
    if file_type not in {"design", "file", "proto"}:
        return None
    file_key = parts[1]
    if not file_key:
        return None
    api_key = file_key
    if len(parts) >= 4 and parts[2].lower() == "branch" and parts[3]:
        api_key = parts[3]
    qs = parse_qs(parsed.query or "")
    node_raw = (qs.get("node-id") or [""])[0]
    node_api = node_id_to_api(node_raw)
    return {
        "url": url,
        "file_type": file_type,
        "file_key": file_key,
        "api_key": api_key,
        "node_id_url": node_raw or None,
        "node_id": node_api or None,
    }


def _slim(node: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(node.get("id") or ""),
        "name": str(node.get("name") or ""),
        "type": str(node.get("type") or ""),
    }


def _listed_children(node: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for child in node.get("children") or []:
        if not isinstance(child, dict):
            continue
        if child.get("type") in FRAME_TYPES:
            out.append(_slim(child))
        if len(out) >= MAX_LISTED:
            break
    return out


def _extract_nodes_payload(data: dict[str, Any], node_id: str) -> dict[str, Any]:
    nodes = data.get("nodes") or {}
    entry = nodes.get(node_id)
    if entry is None:
        return {
            "file_name": data.get("name"),
            "frames": [],
            "states": [],
            "blocker": (
                f"node `{node_id}` ausente ou null na resposta "
                "(id inexistente no arquivo — não inventar frames)"
            ),
        }
    doc = entry.get("document") if isinstance(entry, dict) else None
    if not isinstance(doc, dict):
        return {
            "file_name": data.get("name"),
            "frames": [],
            "states": [],
            "blocker": f"node `{node_id}` sem document na API — não inventar frames",
        }
    frames = [_slim(doc)]
    frames.extend(_listed_children(doc))
    states: list[dict[str, str]] = []
    if doc.get("type") == "COMPONENT_SET":
        states = _listed_children(doc)
    return {
        "file_name": data.get("name"),
        "frames": frames[:MAX_LISTED],
        "states": states[:MAX_LISTED],
        "blocker": None,
    }


def _extract_file_payload(data: dict[str, Any]) -> dict[str, Any]:
    frames: list[dict[str, str]] = []
    doc = data.get("document")
    if isinstance(doc, dict):
        for page in doc.get("children") or []:
            if not isinstance(page, dict):
                continue
            if page.get("type") in FRAME_TYPES:
                frames.append(_slim(page))
            for child in page.get("children") or []:
                if not isinstance(child, dict):
                    continue
                if child.get("type") in FRAME_TYPES:
                    frames.append(_slim(child))
                if len(frames) >= MAX_LISTED:
                    break
            if len(frames) >= MAX_LISTED:
                break
    return {
        "file_name": data.get("name"),
        "frames": frames[:MAX_LISTED],
        "states": [],
        "blocker": None,
    }


def _figma_get(path: str, token: str) -> dict[str, Any]:
    url = f"{FIGMA_API_BASE}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "X-Figma-Token": token,
            "Accept": "application/json",
            "User-Agent": "power-review/figma-spec",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return {"ok": True, "status": resp.status, "data": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:800]
        err_msg = e.reason
        try:
            parsed = json.loads(body)
            err_msg = parsed.get("err") or parsed.get("message") or err_msg
        except json.JSONDecodeError:
            pass
        return {
            "ok": False,
            "status": e.code,
            "error": f"HTTP {e.code} {err_msg}",
        }
    except urllib.error.URLError as e:
        return {"ok": False, "status": None, "error": f"URL error: {e.reason}"}
    except json.JSONDecodeError:
        return {"ok": False, "status": None, "error": "resposta Figma não é JSON"}


def _empty_block(source: str) -> dict[str, Any]:
    return {
        "source": source,
        "url": "",
        "urls": [],
        "file_key": None,
        "api_key": None,
        "node_id": None,
        "node_id_url": None,
        "file_name": None,
        "frames": [],
        "states": [],
        "blockers": [],
        "endpoint": None,
        "instructor": None,
    }


def enrich_figma(urls: list[str]) -> dict[str, Any]:
    """Fill a slim Figma block. Never invents frames. No API call if no URL."""
    clean = []
    for u in urls or []:
        u = (u or "").strip().rstrip(".,;)]>'\"")
        if u and u not in clean:
            clean.append(u)
    if not clean:
        return _empty_block("none")

    parsed = None
    for u in clean:
        parsed = parse_figma_url(u)
        if parsed:
            break

    token = figma_token()
    block = _empty_block("blocked" if not token else "error")
    block["url"] = clean[0]
    block["urls"] = clean
    if parsed:
        block["file_key"] = parsed["file_key"]
        block["api_key"] = parsed["api_key"]
        block["node_id"] = parsed["node_id"]
        block["node_id_url"] = parsed["node_id_url"]
    else:
        block["source"] = "error"
        block["blockers"] = [
            "URL Figma não parseável (fileKey ausente) — não chamar API, não inventar frames"
        ]
        return block

    if not token:
        block["source"] = "blocked"
        block["blockers"] = ["sem FIGMA_ACCESS_TOKEN / FIGMA_TOKEN"]
        block["instructor"] = instructor_missing_token()
        return block

    api_key = urllib.parse.quote(parsed["api_key"], safe="")
    if parsed["node_id"]:
        qs = urllib.parse.urlencode({"ids": parsed["node_id"], "depth": "1"})
        path = f"/v1/files/{api_key}/nodes?{qs}"
    else:
        qs = urllib.parse.urlencode({"depth": "2"})
        path = f"/v1/files/{api_key}?{qs}"
    block["endpoint"] = f"GET {path.split('?')[0]}"

    result = _figma_get(path, token)
    if not result.get("ok"):
        block["source"] = "error"
        block["blockers"] = [
            f"Figma REST {result.get('error') or 'falhou'} — não inventar frames"
        ]
        block["instructor"] = {
            "headline": (
                f"Figma REST falhou ({result.get('error')}). "
                "Review segue; link preservado; sem frames inventados."
            ),
            "reasons": ["figma_http_error"],
            "steps": [],
            "docs": "references/trackers/figma.md",
            "missing": [],
        }
        return block

    data = result.get("data") or {}
    extracted = (
        _extract_nodes_payload(data, parsed["node_id"])
        if parsed["node_id"]
        else _extract_file_payload(data)
    )
    block["file_name"] = extracted.get("file_name")
    block["frames"] = extracted.get("frames") or []
    block["states"] = extracted.get("states") or []
    if extracted.get("blocker"):
        block["source"] = "error"
        block["blockers"] = [extracted["blocker"]]
        return block
    block["source"] = "api"
    if len(block["frames"]) >= MAX_LISTED:
        block["blockers"] = [f"lista de frames truncada em {MAX_LISTED} (API; não inventados)"]
    return block
