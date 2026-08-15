# Setup do forge (glab / gh / bitbucket / azure)

O review **nunca trava** sem CLI. Sem forge+CLI+auth: modo `local` (só
chat) e este guia no preview.

Detector:

```bash
python3 $SKILL_DIR/scripts/detect_forge.py --root <repo> [--url <MR_ou_PR>] --write
```

Leia `instructor.headline` + `instructor.steps` no JSON e **mostre ao
usuário** em todo run — inclusive quando já estiver ok.

## GitLab → `glab`

Publicação inline (discussions + nota) via `post_review.py --forge gitlab`.

```bash
brew install glab
glab auth login
# self-hosted:
glab auth login --hostname git.suaempresa.com
glab mr view <IID> --output json
```

URLs: `https://gitlab.com/<group>/<proj>/-/merge_requests/123`

## GitHub → `gh`

Inline é API oficial, não o `gh pr comment` (esse só posta no timeline).

Docs: [Create a review for a pull request](https://docs.github.com/en/rest/pulls/reviews#create-a-review-for-a-pull-request)
e [Create a review comment](https://docs.github.com/en/rest/pulls/comments#create-a-review-comment-for-a-pull-request).

```bash
brew install gh
gh auth login
gh pr view <IID> --json number,title,body,baseRefName,headRefName,state,url
```

Publicação (a skill usa `post_review.py --forge github`):

```bash
gh api --method POST repos/:owner/:repo/pulls/<IID>/reviews --input review.json
```

Payload: `commit_id` (head SHA), `event` (`COMMENT` ou `REQUEST_CHANGES`),
`body` (resumo + marcador), `comments`: `{path, line, side: "RIGHT"}`.
`line` = linha **nova** no diff (equivalente ao `new_line` do GitLab).

URLs: `https://github.com/<org>/<repo>/pull/123`

## Bitbucket Cloud (`bitbucket.org`)

Não há CLI oficial equivalente a `gh`/`glab`. Leitura do PR: modo
`local` sem `bb`. Publicação: REST oficial quando houver credenciais
no **ambiente** (`can_publish`).

Auth oficial (2026-08-14): API tokens substituem app passwords.

- API tokens: https://support.atlassian.com/bitbucket-cloud/docs/api-tokens/
- Uso (Basic: email Atlassian + token): https://support.atlassian.com/bitbucket-cloud/docs/using-api-tokens/
- Auth REST: https://developer.atlassian.com/cloud/bitbucket/rest/intro/#authentication
- Access token do repositório (Bearer): https://support.atlassian.com/bitbucket-cloud/docs/using-access-tokens/
- Comentário no PR: `POST https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{id}/comments`
  https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pullrequests/#api-repositories-workspace-repo-slug-pullrequests-pull-request-id-comments-post
- Escopo para comentar: `read:pullrequest:bitbucket`

```bash
export BITBUCKET_USERNAME='<email da conta Atlassian>'
export BITBUCKET_API_TOKEN='<api-token>'
# ou:
export BITBUCKET_ACCESS_TOKEN='<repository-access-token>'
python3 $SKILL_DIR/scripts/detect_forge.py --root . --url <url> --write
```

Não publique com `curl` / token cru. Sem credenciais: `can_publish=false`,
review no chat.

URLs: `https://bitbucket.org/<ws>/<repo>/pull-requests/123`

## Azure DevOps → `az rest`

Publicação preferida: `az rest` com a sessão do `az login` (espelho de
`gh api`). Recurso Entra do Azure DevOps:
`499b84ac-1321-427f-aa17-267ca6975798`.

- `az rest`: https://learn.microsoft.com/en-us/cli/azure/use-azure-cli-rest-command
- Exemplo Azure DevOps + `--resource`: https://learn.microsoft.com/en-us/azure/devops/pipelines/get-started/manage-pipelines-with-azure-cli
- Threads: `POST https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{id}/threads?api-version=7.1`
  https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-request-threads/create?view=azure-devops-rest-7.1
- PAT (fallback, env): https://learn.microsoft.com/en-us/azure/devops/cli/log-in-via-pat
- PAT HTTP Basic (user vazio + PAT): https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate

```bash
brew install azure-cli
az login
# fallback se az não estiver autenticado:
export AZURE_DEVOPS_EXT_PAT='<pat>'   # ou AZURE_DEVOPS_PAT
python3 $SKILL_DIR/scripts/detect_forge.py --root . --url <url> --write
```

Não publique com `curl` / PAT cru no instructor. Sem `az` autenticado e
sem PAT: `can_publish=false`, review no chat.

URLs: `https://dev.azure.com/<org>/<project>/_git/<repo>/pullrequest/123`

## Depois de instalar

Rode o detector de novo com a **mesma URL**. `mode` deve mudar de
`local` para `mr` (GitLab) ou `pr` (os outros, leitura). Bitbucket/Azure
podem ficar em `local` (sem CLI de leitura) e mesmo assim ter
`can_publish=true` se as credenciais de publish estiverem no env.

Não publique com `curl` / token cru. Sem `can_publish`: chat.
