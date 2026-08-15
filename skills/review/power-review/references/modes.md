# Modos de review — MR / PR / local

O modo **não** se chuta. Rode `detect_forge.py` (passo 0b). Sem
`can_resolve`, o default é `local` + instructor.

## Entrada

| Entrada do usuário | Modo (se CLI/auth ok) | Sem CLI/auth |
|---|---|---|
| URL GitLab `.../merge_requests/123` | `mr` | `local` + setup `glab` |
| URL GitHub `.../pull/123` | `pr` (leitura) | `local` + setup `gh` |
| URL Bitbucket `.../pull-requests/123` | `pr` se `bb` ok; senão local | `local` + setup |
| URL Azure `.../pullrequest/123` | `pr` se `az` ok | `local` + setup `az` |
| Só IID numérico | forge do remote | `local` se remote ambíguo |
| “review desta branch” | `local` (herdar target do MR/PR se `can_resolve`) | `local` |

## Modo `mr`

1. `glab mr view <IID> --output json`
2. Exigir MR **aberto** (`state == opened`) para side-effects; se merged/closed, avisar e pular workflow de labels/Jira (review de código ainda pode rodar se o usuário insistir).
3. Usar **sempre** `source_branch`, `target_branch` e `diff_refs` (`base_sha`, `head_sha`, `start_sha`) do GitLab — nunca inventar base.
4. Fetch:

```bash
git fetch origin <source_branch> <target_branch>
git merge-base origin/<source_branch> origin/<target_branch>
```

5. Se `merge-base` ≠ `base_sha`, **avisar** e preferir `diff_refs` do GitLab para publicação inline.
6. Diff full padrão: `origin/<target>...origin/<source>` (três pontos).
7. Worktree: `git worktree add -f /tmp/pr-<source_sanitizado> origin/<source_branch>` (ou no `head_sha`).

## Modo `pr` (GitHub)

```bash
gh pr view <IID> --json number,title,body,baseRefName,headRefName,state,url,headRefOid
```

Source/target: `headRefName` / `baseRefName`. Diff:
`origin/<base>...origin/<head>`. Head SHA: `head.sha` / `headRefOid`.

Publicar após aprovação: `post_review.py --forge github` (um review com
inline `path`+`line`+`side=RIGHT`). Side-effects (labels, reviewer, Jira):
`apply_review_workflow.py start|finish --pr <IID> [--forge github]`.
PR aberto: `state` `OPEN` (`gh pr view --json`) ou `open` (REST).

Bitbucket / Azure: publicar com `post_review.py` **somente** se
`can_publish` (Bitbucket: credenciais no env; Azure: `az rest` autenticado
ou PAT no env). Sem `can_publish`: chat + instructor.

## Modo `local`

1. Resolver tip: `HEAD` da branch atual (ou a branch nomeada).
2. Resolver **target** nesta ordem:
   1. Se `can_resolve`: MR/PR aberto da branch (`glab mr list` / `gh pr view --json`) → target do ticket.
   2. Entre `develop`, `master`, `main` (existentes em `origin/`): ancestral real via `git merge-base --is-ancestor`; se só uma fizer sentido, usar essa.
   3. Se ambíguo: **perguntar** — não assumir.
3. Diff: `origin/<target>...HEAD` (três pontos).
4. Worktree opcional: tip local ou commit atual.
5. Entrega: **somente no chat** se `can_publish` for false — **não**
   chamar `post_review.py` nesse caso. Se `can_publish` (ex.: Bitbucket
   com token e sem `bb`), pode publicar após aprovação. **Não**
   side-effects. **Sempre** repetir `instructor.steps`.

## Re-review incremental (marcador)

Marcador obrigatório no final de toda nota-resumo publicada:

```html
<!-- power-review:head_sha=<head_sha> reviewed_at=<iso8601> -->
```

Exemplo:

```html
<!-- power-review:head_sha=41c30cb9290c64bdb0252a0b10958be89ebd2c4d reviewed_at=2026-07-30T23:00:00-03:00 -->
```

### Detecção

Use o script:

```bash
# GitLab
python3 $SKILL_DIR/scripts/resolve_review_scope.py --mr <IID>
# GitHub
python3 $SKILL_DIR/scripts/resolve_review_scope.py --pr <IID> [--forge github]
```

Ou manualmente: achar o body mais recente com `<!-- power-review:head_sha=`.
GitLab: notes do MR. GitHub: reviews (`GET .../pulls/{n}/reviews`, `submitted_at`)
e comentários de issue (`GET .../issues/{n}/comments`, `created_at`) — o mais
recente pelo timestamp. Comentários inline (`.../pulls/{n}/comments`) não entram.

### Escopo do diff

| Situação | Diff a analisar | `mode` na nota |
|---|---|---|
| Sem marcador | `target...source` (full) | `full` |
| Com marcador e `last_head ≠ current_head` | `<last_head_sha>...<current_head_sha>` | `incremental desde <sha7>` |
| Com marcador e SHAs iguais | Nada novo — informar usuário; só reanalisar se pedir force-full | `noop` / ou full se usuário pedir |

Ainda assim: ler **arquivos completos** tocados pelo diff em escopo. Comentários inline só em linhas **adicionadas** desse diff.

## Preview obrigatório

Sempre declarar:

```
Comparing: <source> → <target> (base=<sha7>, head=<sha7>, mode=full|incremental)
Forge: <forge> | CLI: <cli> | review_mode=<mr|pr|local>
```

Só publicar se `can_publish` e o usuário aprovou.
