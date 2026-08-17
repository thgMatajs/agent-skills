---
name: power-review-workflow
description: >-
  Aplica side-effects de review (labels, reviewer, transição Jira) num
  MR/PR GitLab ou GitHub já aprovado no preview do power-review. Use when
  the user asks for labels/Jira workflow after a power-review, or to run
  apply_review_workflow start/finish.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob
---

# Power Review — workflow (labels / Jira)

`disable-model-invocation: true`: só invocação explícita. **Não** faz code
review nem publica inline — isso é `power-review`.

Requer a skill `power-review` no catálogo (o script vive lá).
`$PR_DIR` = diretório de `power-review`.
Bitbucket / Azure / branch local → **sair** (nada a fazer).
GitLab/GitHub + MR/PR aberto → rodar o script. Senão → sair.

MR/PR precisa estar **aberto**. Falha parcial: registrar e não travar.

```bash
# GitLab
python3 $PR_DIR/scripts/apply_review_workflow.py start \
  --mr <IID> [--jira-key KEY] [--dry-run]
python3 $PR_DIR/scripts/apply_review_workflow.py finish \
  --mr <IID> --has-blocking-findings true|false [--dry-run]

# GitHub
python3 $PR_DIR/scripts/apply_review_workflow.py start \
  --pr <IID> [--forge github] [--jira-key KEY] [--dry-run]
python3 $PR_DIR/scripts/apply_review_workflow.py finish \
  --pr <IID> [--forge github] --has-blocking-findings true|false [--dry-run]
```

`--mr` sem `--forge` = GitLab. `--pr` ou `--forge github` = GitHub.

## Quando

| Comando | Quando |
|---|---|
| `start` | Usuário pediu labels/Jira **depois** da aprovação do preview (passo 12 do power-review), MR/PR aberto |
| `finish` | Depois do publish inline. `--has-blocking-findings true` se a lista final tiver ≥1 `CRÍTICO` / `ALTO` / `MÉDIO` |

Não rode `start` no início do review (marcava o ticket se o review fosse cancelado).

O script faz REST (glab/gh + Jira). **Não** reimplemente `glab mr update` /
`gh pr edit` / transições MCP na mão. Sem `JIRA_BASE_URL` o passo Jira é skip.

## Env

| Env | Default | Uso |
|---|---|---|
| `POWER_REVIEW_STATUS_LABEL` | `stat:under review` | Label ao iniciar |
| `POWER_REVIEW_REQUESTED_CHANGE_LABEL` | `requested_change` | Label se achado bloqueante |
| `POWER_REVIEW_COMPETING_LABELS` | (veja script) | Extra CSV de `stat:*` a remover |
| `POWER_REVIEW_JIRA_STATUS` | `code reviewing` | Nome do status/transição |
| `JIRA_BASE_URL` | — | Host Jira (allowlist) |
| `ATLASSIAN_API_TOKEN` / `JIRA_API_TOKEN` | — | Token REST |
| `JIRA_EMAIL` | `git config user.email` | Email da API |

## Fora de escopo

- Code review, Context Pack, `post_review.py`
- Remover `requested_change` em re-review limpo (só se o usuário pedir)
- Criar labels que não existem no repo
