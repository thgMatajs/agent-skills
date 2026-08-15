# Referência — power-review

## Formato do review.json

```json
{
  "mr": "2457",
  "project": "5",
  "base_sha": "e5dc93333f2502a6eae67b63499c90aa2386e081",
  "head_sha": "41c30cb9290c64bdb0252a0b10958be89ebd2c4d",
  "start_sha": "6b425acd40e62ef0d1857be3a0051196bffbc3da",
  "comments": [
    {
      "path": "feature/search/.../SearchRepositoryImpl.kt",
      "new_line": 43,
      "body": "**[CRÍTICO — Concorrência] — ...**\n\n**Problema:** ...\n\n**Antes:**\n```kotlin\n...\n```\n\n**Depois (sugestão):**\n```kotlin\n...\n```\n\n**Por quê:** ...\n\n**Referência:** https://..."
    }
  ],
  "summary": "## Power review — ...\n...\n\n<!-- power-review:head_sha=41c30cb9290c64bdb0252a0b10958be89ebd2c4d reviewed_at=2026-07-30T23:00:00-03:00 -->"
}
```

- `forge` opcional (`gitlab` | `github` | `bitbucket` | `azure`); senão infere (URL, ou `pr` sem `mr` → github).
- GitHub: `pr` (ou `mr`) + `head_sha` + `comments[].new_line` (linha do lado novo).
- GitLab: `project` opcional; senão `glab api projects/:id`. Também `base_sha` + `start_sha`.
- `path` relativo à raiz do repo.
- `new_line` = linha **adicionada** no `head_sha`.
- `summary` **deve** terminar com o marcador HTML `power-review` (não sanitizar).
- Acentuação: UTF-8 (`ensure_ascii=False` no script).

## Scripts

| Script | Uso |
|---|---|
| `scripts/detect_stack.py` | Detecta a stack, grava `.power-review/stack.json` |
| `scripts/detect_forge.py` | Detecta forge/CLI, decide `mr`/`pr`/`local`, instrui setup |
| `scripts/post_review.py` | Publica discussions inline + nota-resumo |
| `scripts/resolve_review_scope.py` | Detecta marcador e define `full` / `incremental` / `noop` |
| `scripts/apply_review_workflow.py` | `start` / `finish` — labels, reviewer, Jira |
| `scripts/detect_tracker.py` | Detecta Jira/Linear + se o API token está pronto |
| `scripts/fetch_context_pack.py` | Pack via token (`source: api_token`) ou `--from-json --source mcp`. Exit 1 = pular (token). Scripts não chamam MCP. |
| `scripts/fetch_figma_spec.py` | Helper REST Figma (chamado pelo fetch após achar o link) |
| `scripts/resolve_context_pack.py` | Legado: acha `jira-figma-context` se ainda estiver instalada |

`$SKILL_DIR` = diretório desta skill (o que contém `SKILL.md`).

```bash
python3 $SKILL_DIR/scripts/detect_stack.py --root <repo> --skill-dir "$SKILL_DIR" --write
python3 $SKILL_DIR/scripts/detect_stack.py --root <repo> --stack ios-swift --write
python3 $SKILL_DIR/scripts/detect_forge.py --root <repo> --url <MR_ou_PR> --write
python3 $SKILL_DIR/scripts/post_review.py --input review.json [--dry-run]
python3 $SKILL_DIR/scripts/resolve_review_scope.py --mr <IID>
python3 $SKILL_DIR/scripts/resolve_review_scope.py --pr <IID> [--forge github]
python3 $SKILL_DIR/scripts/apply_review_workflow.py start --mr <IID> [--jira-key KEY] [--dry-run]
python3 $SKILL_DIR/scripts/apply_review_workflow.py start --pr <IID> [--forge github] [--jira-key KEY] [--dry-run]
python3 $SKILL_DIR/scripts/apply_review_workflow.py finish --mr <IID> --has-blocking-findings true|false [--dry-run]
python3 $SKILL_DIR/scripts/apply_review_workflow.py finish --pr <IID> [--forge github] --has-blocking-findings true|false [--dry-run]
python3 $SKILL_DIR/scripts/detect_tracker.py --root <repo> --key ABC-12 --write
python3 $SKILL_DIR/scripts/fetch_context_pack.py --root <repo> --key ABC-12
python3 $SKILL_DIR/scripts/fetch_context_pack.py --from-json ticket.json --source mcp
```

## Tracker / Context Pack

Perfil: `<repo>/.power-review/tracker.json` (sem token). Guia:
[references/trackers/setup.md](references/trackers/setup.md).

| Tracker | Env | API |
|---|---|---|
| Jira | `JIRA_BASE_URL` + `JIRA_EMAIL` + `JIRA_API_TOKEN` | REST `/rest/api/3/issue/{key}` |
| Linear | `LINEAR_API_KEY` (sem `Bearer`) | GraphQL `issue(id: "ENG-12")` |
| Figma | `FIGMA_ACCESS_TOKEN` / `FIGMA_TOKEN` | REST `GET /v1/files/:key/nodes` ou `?depth=2` |

Sem token/chave: `can_fetch=false`, instructor no preview, review segue.
`jira-figma-context` **não** é mais obrigatória.

## Stack (primeira execução e revalidação)

O perfil fica no **repo sob review**, não no install global:

`<repo>/.power-review/stack.json`

Regras centrais: [references/persona.md](references/persona.md). Overlay:
`references/stacks/<id>.md` (`android-kotlin`, `ios-swift`, `flutter-dart`,
`web-typescript`, `python`, `ruby`, `go`, `rust`, `lua`, `generic`).

Linguagens sem overlay (PHP, Java, C#, Elixir, …) caem em `generic` com
`languages[]` apontando a doc oficial pela extensão dos arquivos.

| `action` | Significado |
|---|---|
| `created` | Primeira vez — perfil gravado |
| `unchanged` | Mesma stack; sinais/linter atualizados |
| `mismatch` | Salvo ≠ detectado — não sobrescreve sem `--force` |
| `detected` | Só imprimiu (sem `--write`) |

`confidence=medium` + vários `candidates` → perguntar e usar `--stack`.
Install **dentro** do repo: `--skill-dir` também gera
`references/active-stack.md`. Install global: ignore esse arquivo.

## Forge / CLI

Perfil: `<repo>/.power-review/forge.json`. Guia:
[references/forges/setup.md](references/forges/setup.md).

O JSON **sempre** traz `instructor.headline` + `instructor.steps`. Mostre
os dois em todo run. Sem `can_resolve` → `mode=local` (review no chat).
`can_publish` é true em GitLab + `glab` autenticado, GitHub + `gh`
autenticado, Bitbucket Cloud com credenciais no env (API token ou access
token), ou Azure DevOps com `az` autenticado (`az rest`) **ou** PAT no env.
GitHub publica via `POST /repos/{owner}/{repo}/pulls/{n}/reviews`
([docs](https://docs.github.com/en/rest/pulls/reviews#create-a-review-for-a-pull-request)),
não via `gh pr comment`. Bitbucket:
[create PR comment](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pullrequests/#api-repositories-workspace-repo-slug-pullrequests-pull-request-id-comments-post).
Azure: [pull request threads create](https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-request-threads/create?view=azure-devops-rest-7.1)
(`api-version=7.1`).

Figma: se o ticket tiver URL e `FIGMA_ACCESS_TOKEN` / `FIGMA_TOKEN`, o fetch
preenche o bloco via REST (sem gravar o token). Sem token: `blocked` +
instructor; o review segue. Passo 5 usa o bloco do pack; MCP Figma só se
`blocked`. Ver [references/trackers/figma.md](references/trackers/figma.md).

## SHAs e branches (MR)

```bash
glab mr view <IID> --output json
```

Campos: `source_branch`, `target_branch`, `diff_refs.{base_sha,head_sha,start_sha}`, `state`.

Validar `git merge-base origin/<source> origin/<target>`; se ≠ `base_sha`, avisar e
preferir `diff_refs` para `position` na API.

## Ancoragem inline

API: `POST /projects/:id/merge_requests/:iid/discussions` com `position` completo.
Linha adicionada: informar `new_line` (+ paths). Ver `post_review.py`.

## Marcador de re-review

```html
<!-- power-review:head_sha=<full_or_abbrev_sha> reviewed_at=<iso8601> -->
```

`resolve_review_scope.py` busca o marcador mais recente: notes do MR (GitLab)
ou bodies de reviews + comentários de issue do PR (GitHub; `submitted_at` /
`created_at`). Comentários inline do review não entram.

## Side-effects

Ver [references/mr-jira-workflow.md](references/mr-jira-workflow.md).

| Momento | Ação |
|---|---|
| Start (MR `opened` / PR `open`/`OPEN`) | `stat:under review`, reviewer = user glab/`gh api user`, Jira → Code Reviewing |
| Finish (após publish) | `requested_change` se ≥1 CRÍTICO/ALTO/MÉDIO |

Jira REST usa `JIRA_BASE_URL` + `ATLASSIAN_API_TOKEN` / `JIRA_API_TOKEN` + email.
Sem base ou token: skip no script; o agente pode tentar MCP Atlassian e registrar
o resultado. Labels e status Jira são configuráveis — ver
[references/mr-jira-workflow.md](references/mr-jira-workflow.md).

## Troubleshooting

| Sintoma | Causa | Correção |
|---|---|---|
| HTTP 415 | Sem `Content-Type: application/json` | Já tratado em `post_review.py` |
| 400 no `position` | SHAs/linha fora do diff | Usar `diff_refs` + linha adicionada na worktree |
| Comentário na linha errada | Arquivo desatualizado | Ler linha na worktree no `head_sha` |
| `glab` sem host | Fora do repo | Rodar no clone ou passar `project` |
| Review “não publicou” | `can_publish=false` ou CLI sem auth | Esperado; seguir `instructor.steps` |
| Re-review full demais | Marcador ausente/quebrado | Conferir nota-resumo com HTML comment |
| Label/Jira skip | MR não opened / sem token | Esperado; não travar review |
| Falsos positivos de base | Target errado | Seguir modes.md; perguntar se ambíguo |

## Heurísticas de análise

- **Bug/corretude:** null-safety, off-by-one, erros, bordas.
- **Concorrência:** estado compartilhado, cancelamento, races — detalhes no overlay.
- **SOLID / KISS / YAGNI / DRY:** contratos, código morto, abstração prematura, duplicação.
- **Camadas:** sem regra de negócio na UI; sem persistência na presentation.
- **Testes:** fluxo com efeito colateral observável tem cobertura.
- **Cache:** chave completa, teto, invalidação, thread-safety.
- **Smell / estilo:** só o linter do perfil. Ver
  [references/linters.md](references/linters.md).

Combine com [references/persona.md](references/persona.md) e o overlay em
`persona_ref`. Docs oficiais: campo `docs` do perfil (versão atual na data
do review).
