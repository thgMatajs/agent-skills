# Setup do tracker (API token — Jira / Linear / Asana / Shortcut / GitHub Issues / Figma)

O Context Pack é **opcional**. Sem token de tracker, o review **segue** e o
preview mostra estes passos. Token primeiro. MCP é **fallback** só se o
token não puder rodar (`can_fetch=false` / instructor missing-token) — nunca
quando o token funcionou. Se o MCP precisar de auth → instructor
(connect/login oficial) + `source: none`; review segue. Scripts **não**
chamam MCP (sem cliente/SDK/HTTP); o agente renderiza com
`--from-json` + `--source mcp`. Detalhe: [mcp.md](mcp.md).

```bash
python3 $SKILL_DIR/scripts/detect_tracker.py --root <repo> \
  [--url <ticket>] [--key ABC-12] [--hint '<título do MR>'] --write
python3 $SKILL_DIR/scripts/fetch_context_pack.py --root <repo> --key ABC-12
python3 $SKILL_DIR/scripts/fetch_context_pack.py --from-json ticket.json --source mcp
```

`detect_tracker.py` **nunca** grava o token. Só `tracker`, `key`, `can_fetch`
(e `auth.figma.has_token` no stdout — sem o valor do token).

## Jira Cloud

1. Token: https://id.atlassian.com/manage-profile/security/api-tokens
2. Env:

```bash
export JIRA_BASE_URL='https://your-org.atlassian.net'
export JIRA_EMAIL='voce@empresa.com'
export JIRA_API_TOKEN='<token>'
```

`ATLASSIAN_API_TOKEN` também vale. Sem `JIRA_BASE_URL`, passe a URL
`.../browse/ABC-12` — o host sai dali.

Self-hosted: o mesmo, com a base da sua instância (`/rest/api/3/issue/...`).

## Linear

1. Linear → Settings → Account → [Security & access](https://linear.app/settings/account/security) → Personal API keys
2. Env:

```bash
export LINEAR_API_KEY='lin_api_...'
```

Header: `Authorization: <key>` — **sem** `Bearer`. Endpoint:
`https://api.linear.app/graphql`. A query `issue(id: "ENG-12")` aceita o
identificador público.

## Asana

1. Token: [developer console](https://app.asana.com/0/my-apps) —
   [Personal access token](https://developers.asana.com/docs/personal-access-token)
2. Env (nunca gravar em `.power-review/`):

```bash
export ASANA_ACCESS_TOKEN='<token>'   # ou ASANA_TOKEN
```

Header oficial: `Authorization: Bearer <token>`.

GET: `https://app.asana.com/api/1.0/tasks/{task_gid}` e
`/tasks/{task_gid}/stories` ([get task](https://developers.asana.com/reference/gettask),
[stories](https://developers.asana.com/reference/getstoriesfortask)).

URL da task (oficial `permalink_url`):
`https://app.asana.com/1/{workspace}/task/{gid}` ou
`https://app.asana.com/0/{container}/{gid}`. Sem URL discriminante, **não**
escolhe Asana só pelo token. `key` no pack = task gid.

## Shortcut

1. Token: https://app.shortcut.com/settings/account/api-tokens —
   [REST API v3](https://developer.shortcut.com/api/rest/v3)
2. Env (oficial `SHORTCUT_API_TOKEN`; alias `SHORTCUT_TOKEN`):

```bash
export SHORTCUT_TOKEN='<token>'   # ou SHORTCUT_API_TOKEN
```

Header oficial: `Shortcut-Token`. **Não** use o query `token` (deprecated).

GET: `https://api.app.shortcut.com/api/v3/stories/{story-public-id}`.

URL: `https://app.shortcut.com/.../story/{id}`. Sem essa URL, **não** escolhe
Shortcut só pelo token. `key` no pack = story id.

## GitHub Issues

Issues REST — **não** pull reviews. Token + urllib; **não** `gh`.
Sem MCP neste skill → instructor + pular pack.

1. PAT: [Managing your personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
2. Fine-grained: permission **Issues = read**
   ([permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens))
3. Env:

```bash
export GITHUB_TOKEN='<token>'   # ou GH_TOKEN
```

Header oficial: `Authorization: Bearer <token>` (também aceita `token`).
`Accept: application/vnd.github+json`.
`X-GitHub-Api-Version: 2026-03-10`.

GET: `https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}` e
`.../issues/{issue_number}/comments`
([get issue](https://docs.github.com/en/rest/issues/issues#get-an-issue),
[list comments](https://docs.github.com/en/rest/issues/comments#list-issue-comments)).

URL: `https://github.com/{owner}/{repo}/issues/{n}` — **não** `/pull/{n}`.
Sem essa URL, **não** escolhe GitHub Issues só pelo token. `key` no pack =
`owner/repo#n`.

## Figma (REST, depois do link no ticket)

O fetch extrai o link da descrição/comentários. **Não** chama a API se não
houver URL.

1. Token: [Manage personal access tokens](https://help.figma.com/hc/en-us/articles/8085703771159-Manage-personal-access-tokens)
   (Figma → Settings → Security). Docs:
   [Personal access tokens](https://developers.figma.com/docs/rest-api/personal-access-tokens/).
2. Env (nunca gravar em `.power-review/`):

```bash
export FIGMA_ACCESS_TOKEN='<token>'   # ou FIGMA_TOKEN
```

Header: `X-Figma-Token`. Escopo mínimo: `file_content:read`.

| Situação | `figma_source` | Review |
|---|---|---|
| Sem URL | `none` | segue; sem chamada |
| URL + sem token | `blocked` | segue; instructor; MCP Figma opcional (passo 5) |
| URL + token + GET ok | `api` | bloco com frames reais; **não** usar MCP |
| URL + token + HTTP/erro | `error` | segue; blocker explícito; sem frames inventados |
| `blocked` + MCP Figma ok | `mcp` | só nodes/ids/names que a tool devolveu |

Cruzar Figma × código é o passo 5, **usando o bloco do pack**. MCP Figma
só se `blocked` — nunca se `api`. Detalhe: [figma.md](figma.md).

## Sem token / sem chave

`fetch_context_pack.py` sai 1 (tracker) ou 0 com Figma `blocked` (instructor
no stderr). O agente **pode** tentar MCP só nesse caso (Jira:
`getJiraIssue`; Figma: `get_metadata` se `blocked`). Linear / Asana /
Shortcut / GitHub Issues: sem MCP neste skill → instructor + pular pack.
HTTP error **com** token → exit 1, sem MCP. O review **não para**. Anote
“sem Context Pack” ou “Figma blocked” na nota-resumo.
