#!/usr/bin/env python3
"""Detect the git forge + CLI and decide review mode (mr / pr / local).

Reads an optional MR/PR URL and the repo remotes. Checks whether the matching
CLI is installed and authenticated. If anything is missing, mode is local —
the review still runs, and stdout always includes setup steps.

Usage:
    python3 detect_forge.py --root <repo>
    python3 detect_forge.py --root <repo> --url https://github.com/org/repo/pull/12
    python3 detect_forge.py --root <repo> --url <url> --write
    python3 detect_forge.py --url <url>          # no clone yet; still instructs

Prints JSON on stdout. Exit 0 on success, 2 on bad args.
Profile: <repo>/.power-review/forge.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PROFILE_REL = Path(".power-review") / "forge.json"

URL_PATTERNS = (
    ("gitlab", re.compile(r"/merge_requests/(\d+)", re.I), "mr"),
    ("github", re.compile(r"/pull/(\d+)", re.I), "pr"),
    ("bitbucket", re.compile(r"/pull-requests/(\d+)", re.I), "pr"),
    ("azure", re.compile(r"pullrequest/(\d+)", re.I), "pr"),
)

HOST_FORGE = (
    ("github.com", "github"),
    ("gitlab.com", "gitlab"),
    ("bitbucket.org", "bitbucket"),
    ("dev.azure.com", "azure"),
    ("visualstudio.com", "azure"),
)

# Hosted GitLab often uses gitlab.* ; we treat unknown git hosts as gitlab-like
# only when the URL path already matched merge_requests.

FORGES: dict[str, dict[str, Any]] = {
    "gitlab": {
        "label": "GitLab",
        "cli": "glab",
        "mode_ready": "mr",
        "can_publish": True,
        "auth_cmd": ["glab", "auth", "status"],
        "smoke": "glab mr view {iid} --output json",
        "setup": [
            "brew install glab   # ou: https://gitlab.com/gitlab-org/cli#installation",
            "glab auth login     # self-hosted: glab auth login --hostname <host>",
            "glab mr view {iid} --output json",
        ],
    },
    "github": {
        "label": "GitHub",
        "cli": "gh",
        "mode_ready": "pr",
        "can_publish": True,
        "auth_cmd": ["gh", "auth", "status"],
        "smoke": "gh pr view {iid} --json number,title,body,baseRefName,headRefName,state,url",
        "setup": [
            "brew install gh   # ou: https://cli.github.com/",
            "gh auth login",
            "gh pr view {iid}",
        ],
    },
    "bitbucket": {
        "label": "Bitbucket",
        "cli": "bb",
        "mode_ready": "pr",
        "can_publish": True,
        "auth_cmd": ["bb", "auth", "status"],
        "smoke": "bb pr view {iid}",
        "setup": [
            "Bitbucket Cloud: publicação via REST (sem CLI oficial tipo gh/glab).",
            "API token (oficial; substitui app password): https://support.atlassian.com/bitbucket-cloud/docs/api-tokens/",
            "Uso do API token (Basic: email Atlassian + token): https://support.atlassian.com/bitbucket-cloud/docs/using-api-tokens/",
            "Auth REST: https://developer.atlassian.com/cloud/bitbucket/rest/intro/#authentication",
            "export BITBUCKET_USERNAME='<email da conta Atlassian>'",
            "export BITBUCKET_API_TOKEN='<api-token>'",
            "Ou access token do repositório (Bearer): https://support.atlassian.com/bitbucket-cloud/docs/using-access-tokens/",
            "export BITBUCKET_ACCESS_TOKEN='<repository-access-token>'",
            "Escopo para comentar PR: read:pullrequest:bitbucket",
            "python3 $SKILL_DIR/scripts/detect_forge.py --root . --url <url> --write",
            "Leitura do PR (opcional): CLI comunitário `bb` se o time já usar.",
        ],
    },
    "azure": {
        "label": "Azure DevOps",
        "cli": "az",
        "mode_ready": "pr",
        "can_publish": True,
        "auth_cmd": ["az", "account", "show"],
        "smoke": "az repos pr show --id {iid}",
        "setup": [
            "brew install azure-cli   # ou: https://learn.microsoft.com/cli/azure/install-azure-cli",
            "az login   # sessão Entra para `az rest`",
            "az rest (CLI autenticado): https://learn.microsoft.com/en-us/cli/azure/use-azure-cli-rest-command",
            "Recurso Azure DevOps no az rest: --resource 499b84ac-1321-427f-aa17-267ca6975798",
            "https://learn.microsoft.com/en-us/azure/devops/pipelines/get-started/manage-pipelines-with-azure-cli",
            "Fallback PAT (não grave em disco): https://learn.microsoft.com/en-us/azure/devops/cli/log-in-via-pat",
            "export AZURE_DEVOPS_EXT_PAT='<pat>'   # ou AZURE_DEVOPS_PAT",
            "PAT HTTP Basic: https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate",
            "python3 $SKILL_DIR/scripts/detect_forge.py --root . --url <url> --write",
            "Leitura do PR (opcional): az extension add --name azure-devops && az repos pr show --id {iid}",
        ],
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run(cmd: list[str], timeout: int = 8) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout or "", r.stderr or ""
    except FileNotFoundError:
        return 127, "", "not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def classify_host(host: str) -> str | None:
    host = (host or "").lower().rstrip(".")
    for needle, forge in HOST_FORGE:
        if host == needle or host.endswith("." + needle):
            return forge
    if host.startswith("gitlab.") or ".gitlab." in host:
        return "gitlab"
    if host.startswith("github.") or host.endswith(".ghe.com"):
        return "github"
    if "bitbucket" in host:
        return "bitbucket"
    if "azure" in host or host.endswith(".visualstudio.com"):
        return "azure"
    return None


def parse_git_remote(raw: str) -> tuple[str | None, str | None]:
    raw = raw.strip()
    if not raw:
        return None, None
    if raw.startswith("git@"):
        # git@host:group/repo.git
        rest = raw[4:]
        host, _, _path = rest.partition(":")
        return host.split("%")[0] or None, classify_host(host)
    parsed = urlparse(raw if "://" in raw else "https://" + raw)
    host = parsed.hostname
    return host, classify_host(host or "")


def parse_url(url: str) -> dict[str, Any] | None:
    url = (url or "").strip()
    if not url:
        return None
    if re.fullmatch(r"\d+", url):
        return {"kind": "iid_only", "iid": url, "url": url, "forge": None, "host": None}
    parsed = urlparse(url if "://" in url else "https://" + url)
    host = parsed.hostname
    path = parsed.path or ""
    for forge, cre, kind in URL_PATTERNS:
        m = cre.search(path)
        if m:
            return {
                "kind": kind,
                "iid": m.group(1),
                "url": url,
                "forge": forge,
                "host": host,
            }
    # GitLab self-hosted sometimes uses /merge_requests/ without gitlab in host
    if "/merge_requests/" in path or "/-/merge_requests/" in path:
        m = re.search(r"/merge_requests/(\d+)", path)
        return {
            "kind": "mr",
            "iid": m.group(1) if m else None,
            "url": url,
            "forge": "gitlab",
            "host": host,
        }
    return {
        "kind": "unknown_url",
        "iid": None,
        "url": url,
        "forge": classify_host(host or ""),
        "host": host,
    }


def list_remotes(root: Path) -> list[dict[str, Any]]:
    code, out, err = run(["git", "-C", str(root), "remote", "-v"])
    if code != 0:
        return []
    seen: dict[str, dict[str, Any]] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        host, forge = parse_git_remote(url)
        key = f"{name}:{url}"
        if key in seen:
            continue
        seen[key] = {"name": name, "url": url, "host": host, "forge": forge}
    return list(seen.values())


def cli_status(cli: str, auth_cmd: list[str]) -> dict[str, Any]:
    path = shutil.which(cli)
    installed = bool(path)
    if not installed:
        return {"cli": cli, "installed": False, "auth_ok": False, "detail": "not on PATH"}
    code, out, err = run(auth_cmd)
    text = (out + "\n" + err).strip()
    auth_ok = code == 0
    # gh prints to stderr and exits 1 when logged out
    if cli == "gh" and "not logged" in text.lower():
        auth_ok = False
    if cli == "glab" and code != 0:
        auth_ok = False
    return {
        "cli": cli,
        "installed": True,
        "path": path,
        "auth_ok": auth_ok,
        "detail": text[:400] or f"exit {code}",
    }


def fill_setup(steps: list[str], iid: str | None) -> list[str]:
    token = iid or "<IID>"
    return [s.replace("{iid}", token) for s in steps]


def _env_set(name: str) -> bool:
    return bool((os.environ.get(name) or "").strip())


def bitbucket_publish_ready() -> bool:
    """Publish needs env creds — not the community `bb` CLI.

    Official (2026-08-14): API token = Basic (Atlassian email + token);
    repository/project/workspace access token = Bearer.
    """
    if _env_set("BITBUCKET_ACCESS_TOKEN"):
        return True
    if _env_set("BITBUCKET_USERNAME") and _env_set("BITBUCKET_API_TOKEN"):
        return True
    if _env_set("BITBUCKET_USERNAME") and _env_set("BITBUCKET_APP_PASSWORD"):
        return True
    return False


def azure_pat_present() -> bool:
    return _env_set("AZURE_DEVOPS_EXT_PAT") or _env_set("AZURE_DEVOPS_PAT")


def azure_publish_ready(cli_ok: bool, auth_ok: bool) -> bool:
    """az installed + logged in (enough for `az rest`) OR PAT in env."""
    return bool((cli_ok and auth_ok) or azure_pat_present())


def compute_can_publish(
    forge: str | None,
    can_resolve: bool,
    cli_ok: bool,
    auth_ok: bool,
    adapter: bool,
) -> bool:
    if forge == "bitbucket":
        return bitbucket_publish_ready()
    if forge == "azure":
        return azure_publish_ready(cli_ok, auth_ok)
    return bool(can_resolve and adapter)


def pick_forge(
    url_info: dict[str, Any] | None,
    remotes: list[dict[str, Any]],
) -> tuple[str | None, str, list[str]]:
    """Return (forge, source, candidates)."""
    if url_info and url_info.get("forge"):
        return url_info["forge"], "url", [url_info["forge"]]
    forges = []
    for r in remotes:
        if r.get("forge") and r["forge"] not in forges:
            forges.append(r["forge"])
    if len(forges) == 1:
        return forges[0], "remote", forges
    if len(forges) > 1:
        return None, "ambiguous_remotes", forges
    if remotes:
        return None, "unknown_host", []
    return None, "no_remote", []


def instructor(
    forge: str | None,
    mode: str,
    cli_ok: bool,
    auth_ok: bool,
    can_publish: bool,
    setup: list[str],
    reasons: list[str],
) -> dict[str, Any]:
    label = FORGES.get(forge, {}).get("label", forge)
    if mode == "local" and not forge:
        headline = (
            "Forge não identificado. Review será LOCAL (só no chat). "
            "Passe a URL do MR/PR ou rode dentro de um clone com remote."
        )
    elif forge in {"bitbucket", "azure"} and not can_publish:
        headline = (
            f"Publicação no {label} está bloqueada (sem credenciais). "
            "O review continua no chat."
        )
    elif mode == "local" and can_publish:
        headline = (
            f"{label}: publicação inline possível (credenciais no ambiente). "
            "Leitura do PR pela URL depende do CLI; o review segue no chat."
        )
    elif mode == "local" and not cli_ok:
        headline = (
            f"CLI de {label} não está instalado. "
            "Review será LOCAL (só no chat). Instale e autentique para revisar pela URL."
        )
    elif mode == "local" and not auth_ok:
        headline = (
            f"CLI encontrado, mas sem login. Review será LOCAL (só no chat). "
            "Autentique e rode o detector de novo."
        )
    elif mode in {"mr", "pr"} and not can_publish:
        headline = (
            f"{label} + CLI ok — consigo LER o MR/PR pela URL. "
            "Publicação inline bloqueada. Review completo no chat."
        )
    else:
        headline = (
            f"{label} + CLI autenticado. "
            "Posso resolver a URL e publicar inline após aprovação."
        )
    return {
        "headline": headline,
        "reasons": reasons,
        "steps": setup,
        "docs": "references/forges/setup.md",
    }


def build_profile(
    root: Path | None,
    url: str | None,
    prefer_local: bool,
) -> dict[str, Any]:
    url_info = parse_url(url) if url else None
    remotes = list_remotes(root) if root else []

    forge, source, candidates = pick_forge(url_info, remotes)
    reasons: list[str] = []
    if url_info and url_info.get("kind") == "iid_only" and not forge:
        reasons.append("entrada é só um número — preciso da URL ou do remote para saber o forge")
    if source == "ambiguous_remotes":
        reasons.append(f"remotes apontam para forges diferentes: {candidates}")
    if source == "unknown_host":
        reasons.append("remote existe, mas o host não foi reconhecido (github/gitlab/bitbucket/azure)")
    if source == "no_remote":
        reasons.append("sem git remote e sem URL de MR/PR")

    meta = FORGES.get(forge or "") or {}
    cli_name = meta.get("cli")
    status = (
        cli_status(cli_name, meta["auth_cmd"])
        if cli_name
        else {"cli": None, "installed": False, "auth_ok": False, "detail": "no forge"}
    )
    cli_ok = bool(status.get("installed"))
    auth_ok = bool(status.get("auth_ok"))
    iid = (url_info or {}).get("iid")
    setup = fill_setup(list(meta.get("setup") or [
        "Passe a URL do merge request / pull request.",
        "Ou clone o repo (git remote -v deve mostrar github/gitlab/bitbucket).",
    ]), iid)

    can_resolve = bool(forge and cli_ok and auth_ok)
    can_publish = compute_can_publish(
        forge, can_resolve, cli_ok, auth_ok, bool(meta.get("can_publish"))
    )
    user_wants_remote = bool(
        url_info
        and url_info.get("kind") in {"mr", "pr", "iid_only"}
        and (url_info.get("forge") or forge)
    )

    if prefer_local:
        mode = "local"
        reasons.append("pedido explícito de review local")
    elif source == "ambiguous_remotes" and not (url_info and url_info.get("forge")):
        mode = "local"
        reasons.append("ambíguo — pergunte qual remote/URL usar")
    elif can_resolve and user_wants_remote:
        mode = meta["mode_ready"]
    elif can_resolve and not user_wants_remote:
        # CLI ok, no URL: still local unless later we find an open MR/PR
        mode = "local"
        reasons.append("sem URL de MR/PR — default local; use a URL para modo remoto")
    else:
        mode = "local"
        if user_wants_remote and not can_resolve:
            reasons.append(
                "URL de MR/PR recebida, mas CLI/auth não está ok — leitura local"
            )
            if not can_publish:
                reasons.append("publicação bloqueada (sem credenciais)")

    host = (url_info or {}).get("host")
    if not host:
        for r in remotes:
            if r.get("forge") == forge and r.get("host"):
                host = r["host"]
                break

    smoke = fill_setup([meta["smoke"]], iid)[0] if meta.get("smoke") else None

    has_token = False
    if forge == "bitbucket":
        has_token = bitbucket_publish_ready()
    elif forge == "azure":
        has_token = azure_pat_present()

    profile: dict[str, Any] = {
        "forge": forge,
        "label": meta.get("label"),
        "host": host,
        "source": source,
        "candidates": candidates,
        "url": (url_info or {}).get("url"),
        "iid": iid,
        "url_kind": (url_info or {}).get("kind"),
        "cli": cli_name,
        "cli_ok": cli_ok,
        "auth_ok": auth_ok,
        "cli_detail": status.get("detail"),
        "can_resolve": can_resolve,
        "can_publish": can_publish,
        "mode": mode,
        "smoke": smoke,
        "setup": setup,
        "remotes": remotes,
        "detected_at": now_iso(),
        "instructor": instructor(
            forge, mode, cli_ok, auth_ok, can_publish, setup, reasons
        ),
    }
    if forge in {"bitbucket", "azure"}:
        profile["has_token"] = has_token
    return profile


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
    slim = {k: v for k, v in profile.items() if k != "cli_detail"}
    # Never persist token/password values — booleans only (has_token).
    for secret_key in (
        "token",
        "pat",
        "password",
        "app_password",
        "access_token",
        "api_token",
        "BITBUCKET_ACCESS_TOKEN",
        "BITBUCKET_API_TOKEN",
        "BITBUCKET_APP_PASSWORD",
        "AZURE_DEVOPS_EXT_PAT",
        "AZURE_DEVOPS_PAT",
    ):
        slim.pop(secret_key, None)
    path.write_text(json.dumps(slim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect forge CLI and review mode.")
    ap.add_argument("--root", default=".", help="Repo root (optional if only --url)")
    ap.add_argument("--url", default=None, help="MR/PR URL or numeric IID")
    ap.add_argument("--write", action="store_true", help="Write .power-review/forge.json")
    ap.add_argument("--prefer-local", action="store_true", help="Force mode=local")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"root is not a directory: {root}"}, ensure_ascii=False))
        return 2

    profile = build_profile(root, args.url, args.prefer_local)
    dest = root / PROFILE_REL
    action = "detected"
    if args.write:
        existed = dest.is_file()
        write_profile(dest, profile)
        action = "updated" if existed else "created"
    profile["action"] = action
    profile["profile_path"] = str(dest)
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
