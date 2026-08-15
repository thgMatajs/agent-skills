# Workflow MR/PR + Jira (side-effects)

Aplica-se **somente** a MR **aberto** (`state == opened`) ou PR **aberto**
(`state` `OPEN` no `gh pr view --json` / `open` no REST). Modo local: pular tudo.

Script preferido (`$SKILL_DIR` = diretório desta skill):

```bash
# GitLab
python3 $SKILL_DIR/scripts/apply_review_workflow.py start \
  --mr <IID> [--jira-key KEY] [--dry-run]

python3 $SKILL_DIR/scripts/apply_review_workflow.py finish \
  --mr <IID> --has-blocking-findings true|false [--dry-run]

# GitHub
python3 $SKILL_DIR/scripts/apply_review_workflow.py start \
  --pr <IID> [--forge github] [--jira-key KEY] [--dry-run]

python3 $SKILL_DIR/scripts/apply_review_workflow.py finish \
  --pr <IID> [--forge github] --has-blocking-findings true|false [--dry-run]
```

`--mr` sem `--forge` = GitLab. `--pr` ou `--forge github` = GitHub.
Se `--mr` e `--pr` forem informados com valores diferentes, o script sai 2.

## Convenções (sobrescreva por env)

Defaults pensados para GitLab/GitHub + Jira genéricos. Sem `JIRA_BASE_URL` o passo
Jira é skip — **não** há host embutido.

| Env | Default | Uso |
|---|---|---|
| `POWER_REVIEW_STATUS_LABEL` | `stat:under review` | Label ao iniciar |
| `POWER_REVIEW_REQUESTED_CHANGE_LABEL` | `requested_change` | Label se houver achado bloqueante |
| `POWER_REVIEW_COMPETING_LABELS` | (veja script) | Extra CSV de labels `stat:*` a remover |
| `POWER_REVIEW_JIRA_STATUS` | `code reviewing` | Nome do status/transição Jira (case-insensitive) |
| `JIRA_BASE_URL` | — (obrigatório para REST) | Ex.: `https://your-org.atlassian.net` |
| `ATLASSIAN_API_TOKEN` / `JIRA_API_TOKEN` | — | Token REST |
| `JIRA_EMAIL` | `git config user.email` | Email da API |

Se o script falhar parcialmente, registrar no preview/nota e **não travar** o review.

## Ao iniciar o review (`start`)

Ordem:

### 1. Labels GitLab

- Remover labels de status concorrentes, se presentes:
  - `stat:awaiting review`
  - outras `stat:*` de status de review, exceto a que será aplicada
- Adicionar: `stat:under review` (label real do GitLab)

Via `glab` / API: obter labels atuais, PUT com a lista atualizada, ou:

```bash
glab mr update <IID> --unlabel "stat:awaiting review"
glab mr update <IID> --label "stat:under review"
```

### 2. Reviewer GitLab

- Resolver usuário logado: `glab api user` → `username`.
- Listar reviewers atuais do MR.
- **Adicionar** o usuário atual se ainda não estiver (não remover outros).

```bash
glab mr update <IID> --reviewer <username>
```

(Se a CLI substituir a lista, o script deve fazer GET + PUT com a união dos usernames.)

### 3. Jira → Code Reviewing

- Chave: argumento `--jira-key` ou regex `\b([A-Z][A-Z0-9]+-\d+)\b` no título/descrição/branch.
- Se sem chave: pular Jira; registrar “sem ticket”.
- Se status atual já for **Code Reviewing** (case-insensitive): no-op.
- Caso contrário: listar transições e aplicar a que leve a esse status
  (nome da transição ou do `to.name` contendo `code reviewing`).
- Preferência: REST Jira se houver token (`ATLASSIAN_API_TOKEN` / `JIRA_API_TOKEN`);
  senão MCP Atlassian (`getTransitionsForJiraIssue` + `transitionJiraIssue`).
- Falha/auth: registrar blocker; continuar review.

## GitHub (PR) — `gh` autenticado

Mesmos side-effects, via CLI oficial `gh` (não curl+token). Pesquisa 2026-08-14.

**Estado aberto:** `gh pr view <n> --json state` usa o campo GraphQL
`PullRequest.state` (`OPEN` / `CLOSED` / `MERGED`). O REST
`GET /repos/{owner}/{repo}/pulls/{n}` usa `state: open|closed`.
O script aceita os dois (`state.lower() == "open"`).
Closed / merged: SKIP, exit 0.

- `gh pr view`: https://cli.github.com/manual/gh_pr_view
- REST PR: https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request
- GraphQL enum: https://docs.github.com/en/graphql/reference/enums#pullrequeststate

### Labels GitHub

`--add-label` / `--remove-label` do `gh pr edit` **não** substituem a lista
inteira (add/remove incrementais). Equivalente REST:

- Add (mantém as outras): `POST /repos/{owner}/{repo}/issues/{n}/labels`
- Remove uma: `DELETE /repos/{owner}/{repo}/issues/{n}/labels/{name}`
- **Não** usar `PUT .../labels` (substitui todas)

Docs: https://cli.github.com/manual/gh_pr_edit ·
https://docs.github.com/en/rest/issues/labels

```bash
gh pr view <IID> --json number,title,body,headRefName,state,labels,reviewRequests
gh pr edit <IID> --remove-label "stat:awaiting review"
gh pr edit <IID> --add-label "stat:under review"
```

Label inexistente no repositório (422 / not found): registrar FALHA e
**seguir** — **não** criar a label (`gh label create` / `POST .../labels` do repo).

### Reviewer GitHub

- Usuário atual: `gh api user` → `login`
  (GET `/user`: https://docs.github.com/en/rest/users/users#get-the-authenticated-user ·
  https://cli.github.com/manual/gh_api)
- **Adicionar** sem remover os demais: `gh pr edit <IID> --add-reviewer <login>`
- REST equivalente (também é união, não replace):
  `POST /repos/{owner}/{repo}/pulls/{n}/requested_reviewers`
  https://docs.github.com/en/rest/pulls/review-requests

Se o GitHub recusar (ex.: autor não pode se pedir como reviewer): FALHA/SKIP e
continuar o review.

### Jira

O mesmo helper `transition_jira_code_reviewing`. Chave: `--jira-key` ou regex
no título / body / `headRefName`. Sem chave ou sem token: skip (igual GitLab).

## Após publicar (`finish`)

Condição de label `requested_change`:

- `has-blocking-findings=true` quando a lista **final** (após dedupe) tiver ≥1 achado
  com severidade `CRÍTICO`, `ALTO` ou `MÉDIO`.
- Só `BAIXO` ou zero achados → **não** adicionar.
- Já presente → no-op. **Não** remover `requested_change` automaticamente.

Aplicar **somente depois** da aprovação do usuário e da publicação dos comentários
(nunca no início, para não marcar o MR/PR se o review for cancelado).

```bash
# GitLab
glab mr update <IID> --label "requested_change"
# GitHub (add incremental; não cria a label se ela não existir no repo)
gh pr edit <IID> --add-label "requested_change"
```

## Fora de escopo

- Branch local
- MR/PR merged / closed / locked (avisar; pular side-effects)
- Remover `requested_change` automaticamente em re-reviews limpos (não fazer, a menos que o usuário peça)
- Side-effects Bitbucket / Azure (este script não adapta esses forges)
