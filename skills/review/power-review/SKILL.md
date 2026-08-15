---
name: power-review
description: >-
  Faz power review crítico de um MR/PR (GitLab, GitHub, Bitbucket, Azure) ou
  de uma branch local. Detecta stack e forge/CLI (glab, gh, …); sem CLI
  autenticado entrega o review local e mostra o setup. Context Pack opcional,
  cruzamento Figma×código, re-review   incremental, anti-duplicação. Publicação
  inline via glab (GitLab) ou gh api (GitHub). Use quando o usuário pedir power review,
  re-review, review desta branch, ou passar URL/IID de MR/PR.
disable-model-invocation: true
---

# Power Review (MR/PR ou branch local)

Review crítico com tolerância zero. As **regras centrais** (SOLID / KISS /
YAGNI / DRY, camadas, anti-bug) são as mesmas em qualquer stack. A **persona,
docs oficiais e linter** vêm do perfil de stack. O **forge** (glab / gh / …)
decide se dá para ler a URL e se dá para publicar.

| `mode` | Quando | Entrega |
|---|---|---|
| `mr` | GitLab + `glab` autenticado + URL/IID | Lê o MR; **pode publicar** após aprovação |
| `pr` | GitHub + `gh` autenticado + URL | Lê o PR; **pode publicar** inline via `gh api` |
| `pr` (outros) | Bitbucket/Azure + `can_publish` | Lê se o CLI ok; publica se `can_publish` |
| `local` | Sem CLI/auth, sem URL, ou pedido local | **Só no chat** + aviso com passos de setup |

Idioma: **pt-br, com acentuação correta**.

**Path:** `$SKILL_DIR` é o diretório desta skill (o que contém este `SKILL.md`).
Scripts: `python3 $SKILL_DIR/scripts/…`.

**Pré-requisitos:** nenhum CLI é obrigatório. Sem ele, o review roda local.
Context Pack (Jira / Linear / Asana / Shortcut / GitHub Issues) é **opcional**
e vai de **API token** primeiro. MCP só se o token não puder rodar.
Sem pack, o review segue e o instructor mostra o setup. Side-effects Jira/labels só com
`can_publish` (GitLab, GitHub, Bitbucket ou Azure). Sem credenciais nesses
forges: review no chat. Ver
[references/forges/setup.md](references/forges/setup.md).

Antes de analisar, leia:

1. Stack (passo 0) → `.power-review/stack.json`
2. Forge (passo 0b) → `.power-review/forge.json` — **mostre `instructor`**
3. [references/persona.md](references/persona.md) + overlay `persona_ref`
4. [references/linters.md](references/linters.md)
5. [references/modes.md](references/modes.md)
6. `date` — use a data atual nas docs oficiais

## Regras de análise (TOLERÂNCIA ZERO)

Aplique a persona central **e** o overlay da stack: bugs, ambiguidades,
gambiarras, SOLID / KISS / YAGNI / DRY. Não ignore por "é pequeno". Ao citar
boa prática, pesquise a doc oficial **atual nos hosts do perfil** e linke.

**Smell / estilo / naming / complexidade:** só o linter do projeto
([references/linters.md](references/linters.md)). Regra off ou abaixo do
threshold → não abrir achado. Bugs e camadas continuam tolerância zero.

## Fluxo (copie e acompanhe)

```
- [ ] 0. Detectar / revalidar stack (detect_stack.py) e carregar overlay
- [ ] 0b. Detectar forge/CLI (detect_forge.py --url se houver) e mostrar instructor
- [ ] 1. Resolver entrada (URL/IID ou branch) + source/target/SHAs
- [ ] 2. Side-effects start — só se can_publish e MR/PR aberto
- [ ] 3. Escopo do diff (full | incremental via marcador) — só se can_resolve
- [ ] 4. Context Pack (token primeiro; MCP só se token ausente) — review nunca para
- [ ] 5. Cruzar Figma × código — REST se `api`; MCP só se `blocked`; sem URL: PULAR
- [ ] 6. Fetch + worktree da source / tip local
- [ ] 7. Ler arquivos alterados por completo + carregar config do linter
- [ ] 8. (Opcional) Rodar o linter do perfil nos módulos tocados
- [ ] 9. Prior-comments — só se can_resolve (MR/PR)
- [ ] 10. Analisar (persona + overlay + linter + tolerância zero)
- [ ] 11. Calcular new_line; montar achados
- [ ] 12. Preview + APROVAÇÃO do usuário (inclui instructor do forge)
- [ ] 13. Publicar só se can_publish; senão entregar no chat
- [ ] 14. Label requested_change — só se can_publish e ≥1 CRÍTICO/ALTO/MÉDIO
- [ ] 15. Remover worktree (SEMPRE)
```

Passos 4–5 podem rodar em paralelo com 6–7. O passo 5 depende do pack (link Figma).

### 0. Stack do projeto

As regras centrais **não mudam**. Este passo só escolhe overlay (persona,
docs, linter) e grava o perfil **no repo sob review** — não no catálogo
global.

```bash
python3 $SKILL_DIR/scripts/detect_stack.py --root <repo> --skill-dir "$SKILL_DIR" --write
```

| `action` | O que fazer |
|---|---|
| `created` / `unchanged` | Usar o JSON. Ler `persona.md` + `persona_ref`. |
| `mismatch` | Stack salva ≠ detectada. Mostrar as duas; só então `--write --force` ou `--stack <id> --write`. |
| `confidence=medium` e `candidates` > 1 | Monorepo/ambíguo. **Perguntar**. Gravar com `--stack <id> --write`. |

`--skill-dir` só reescreve `references/active-stack.md` se a skill estiver
**dentro** do repo (install por projeto). Install global: o perfil fica só
em `<repo>/.power-review/stack.json` (pode commitar).

Pesquise docs **somente** nos URLs de `docs`. Snippets no idioma de
`snippet_lang`.

### 0b. Forge / CLI

```bash
python3 $SKILL_DIR/scripts/detect_forge.py --root <repo> [--url <URL>] --write
```

`--url` aceita MR/PR do GitLab, GitHub, Bitbucket ou Azure (ou um IID
numérico, se o remote já disser o forge).

**Sempre** mostre `instructor.headline` e `instructor.steps` ao usuário
(mesmo com CLI ok). Detalhes: [references/forges/setup.md](references/forges/setup.md).

| Campo | Uso |
|---|---|
| `mode` | `mr` / `pr` / `local` |
| `can_resolve` | Posso ler o MR/PR via CLI (`smoke`) |
| `can_publish` | Posso postar inline (GitLab/`glab`, GitHub/`gh api`, Bitbucket REST ou Azure `az rest`/PAT) |
| `setup` | Passos para quem for rodar depois |

`candidates` > 1 (dois remotes) → **perguntar** qual URL/remote.
Não publique com `curl` / token. Sem `can_resolve`: siga **local**.

### 1. Resolver entrada e branches

Siga [references/modes.md](references/modes.md). Use o `smoke` do perfil
quando `can_resolve`:

```bash
# GitLab
glab mr view <IID> --output json
# GitHub
gh pr view <IID> --json number,title,body,baseRefName,headRefName,state,url
```

Guarde source/target/SHAs. Nunca inventar base: GitLab → `diff_refs`;
GitHub → `baseRefOid` / `headRefOid` quando existirem.

**Local** (default se `mode=local`): target via MR/PR da branch se
`can_resolve`, senão `develop`/`master`/`main` ancestral, senão perguntar.
Diff: `origin/<target>...HEAD`. Sem publicação e sem side-effects.

Preview sempre inclui:

```
Comparing: <source> → <target> (base=<sha7>, head=<sha7>, mode=full|incremental)
Stack: <stack_id> (<label>)
Forge: <forge> | CLI: <cli> <ok|missing|no-auth> | review_mode=<mr|pr|local>
<instructor.headline>
```

### 2. Side-effects ao iniciar (só `can_publish` + aberto)

Ver [references/mr-jira-workflow.md](references/mr-jira-workflow.md).

```bash
# GitLab
python3 $SKILL_DIR/scripts/apply_review_workflow.py start \
  --mr <IID> [--jira-key KEY]
# GitHub
python3 $SKILL_DIR/scripts/apply_review_workflow.py start \
  --pr <IID> [--forge github] [--jira-key KEY]
```

Falha parcial: registrar e **seguir** o review.

### 3. Escopo do diff (re-review)

```bash
# GitLab
python3 $SKILL_DIR/scripts/resolve_review_scope.py --mr <IID>
# GitHub
python3 $SKILL_DIR/scripts/resolve_review_scope.py --pr <IID> [--forge github]
```

| `mode` | Diff |
|---|---|
| `full` | `origin/<target>...origin/<source>` |
| `incremental` | `<last_head_sha>...<current_head_sha>` |
| `noop` | Informar usuário; só forçar full se pedir |

Marcador obrigatório no fim de toda nota-resumo publicada:

```html
<!-- power-review:head_sha=<head_sha> reviewed_at=<iso8601> -->
```

### 4. Context Pack (Jira / Linear / Asana / Shortcut / GitHub Issues)

Não depende da skill `jira-figma-context`. Token primeiro. Scripts **não**
chamam MCP (sem cliente/SDK/HTTP). Guia:
[references/trackers/setup.md](references/trackers/setup.md) ·
[references/trackers/mcp.md](references/trackers/mcp.md).

Chave Jira/Linear: `\b([A-Z][A-Z0-9]+-\d+)\b` no título/descrição/branch, ou
URL do ticket. Asana / Shortcut / GitHub Issues: **só URL** (ou
`.power-review/tracker.json` de um `--write` anterior). Número solto não
identifica esses três. Token sozinho também não.

```bash
python3 $SKILL_DIR/scripts/detect_tracker.py --root <repo> \
  [--url <ticket>] [--key KEY] --hint '<título+descrição+branch>' --write
python3 $SKILL_DIR/scripts/fetch_context_pack.py --root <repo> \
  [--url <ticket>] [--key KEY] --hint '<...>'
# só depois de o agente obter campos via MCP (nunca no lugar de token ok):
python3 $SKILL_DIR/scripts/fetch_context_pack.py --from-json <ticket.json> --source mcp
```

**Sempre** mostre `instructor.headline` + `steps` (mesmo com token ok).
Se o fetch imprimir instructor Figma no stderr (URL sem token), mostre esses
`steps` também — o review **não para**.

| # | Ordem (obrigatória) |
|---|---|
| 1 | `detect_tracker.py` + `fetch_context_pack.py` (API token). Exit 0 e `source: api_token` → **parar**. Não usar MCP. |
| 2 | Fetch falhou por **token/chave ausente** (`can_fetch=false` / instructor missing-token): o agente PODE chamar a tool MCP **só desse** tracker. |
| 3 | MCP `needsAuth` / erro de auth → instructor (connect/login oficial), `source: none`, review **segue**. Não inventar pack. |
| 4 | MCP devolveu campos reais → mapear **só** esses campos no JSON do pack (ausente = `N/A`) e renderizar com `--from-json` + `--source mcp`. Pack `source: mcp`. |
| 5 | HTTP error **com** token presente **não** dispara MCP (exit 1 / sem pack). MCP não é retry de token ruim. |
| 6 | Figma: `figma_source=api` → não usar MCP Figma. `blocked` (URL + sem token) → o agente PODE tentar MCP Figma; sucesso → `figma_source: mcp` só com nodes/ids/names que a tool devolveu; auth fail → permanece `blocked` + instructor. Nunca inventar frames. |

| Resultado | Ação |
|---|---|
| `can_fetch=true` + fetch exit 0 | Consumir o pack. **Não** chamar MCP. |
| `can_fetch=false` (sem token) | MCP só se houver tool desse tracker; senão pular pack |
| fetch exit 1 com token | **Pular** pack. Não tentar MCP. |
| MCP auth fail / sem MCP do tracker | Instructor + `source: none`. Seguir. |
| `source=ambiguous_tokens` | Perguntar Jira vs Linear (ou passar a URL) |

Linear / Asana / Shortcut / GitHub Issues: sem MCP neste skill → instructor +
pular pack. Não inventar servidor.

Figma no fetch: URL + `FIGMA_ACCESS_TOKEN`/`FIGMA_TOKEN` → bloco via REST
(`figma_source: api`) — não usar MCP. URL sem token → `blocked` + instructor
no stderr; review **segue** (MCP Figma só no passo 5, se `blocked`). Sem URL
→ `none`. Detalhe:
[references/trackers/figma.md](references/trackers/figma.md).

### 5. Cruzar Figma × implementação

Só se o pack tiver URL Figma (`figma_source` ≠ `none`). Senão: PULAR e anotar
"sem referência de Figma".

**Prefira o bloco Figma já no pack** (REST + token). MCP Figma **só** se
`figma_source=blocked`. Se `api`, não chamar MCP. Não invente frames/nós
que a API/tool não devolveu.

| `figma_source` | Ação |
|---|---|
| `api` | Cruzar frames / `node_id` / states do pack × código. **Não** usar MCP Figma. |
| `blocked` | Mostrar instructor. PODE tentar `get_metadata`; sucesso → `figma_source: mcp` só com nodes/ids/names devolvidos (re-render `--from-json`); auth fail → permanece `blocked`. Nunca inventar frames. |
| `mcp` | Cruzar só nodes/ids/names que estão no pack |
| `error` | Usar o blocker HTTP; não inventar nós |
| `none` | PULAR |

Delegue (`Task`, `generalPurpose`) se o pack listou frames/states. Foque em
fidelidade ao que o pack trouxe — não faça code review geral.

Prompt:

```
Cruze o bloco Figma do Context Pack com a implementação. NÃO faça code review
geral; foque em fidelidade ao que o pack listou (sem inventar layout/nós).
Ticket: <KEY> | Figma: <url> | figma_source: <api|blocked|error|mcp>
file_key / node_id / frames / states: <do pack>
Escopo (ACs/estados): <lista>
Implementação (arquivos/estados): <lista>

Retorne SOMENTE:

## Cruzamento Figma × Implementação — <KEY>
- Figma: <url> | frame(s): <nome/node-id do pack> | origem: <ticket|pai>
### Estados (Figma ↔ código)
| Estado | Figma | Implementação | Divergência | Severidade |
|---|---|---|---|---|
### Divergências de layout
- <item> (severidade)
### Elementos ausentes ou extras
- <item>
### Tokens vs design system
- <item>
### Checklist de fidelidade
- [ ] <estado/AC>
### Bloqueios
- <blocked sem token | HTTP … | tela não localizada | nenhum>
```

Divergências viram achados inline (`CRÍTICO`…`BAIXO`).

### 6–7. Fetch, worktree e leitura completa

```bash
git fetch origin <source_branch> <target_branch>
git worktree add -f /tmp/pr-<source_sanitizado> origin/<source_branch>
```

Leia cada arquivo alterado **inteiro**. Busque no repo para validar hipóteses
(chamadores, cache, etc.). Carregue os configs em `linter.configs`.

### 8. Linter (smell/estilo)

Siga [references/linters.md](references/linters.md). Opcionalmente rode
`linter.command` do perfil nos módulos tocados e use a saída como evidência.

### 9. Prior comments (só MR)

Leia [references/prior-comments.md](references/prior-comments.md). Classifique
candidatos: `NOVO` | `DUPLICADO` | `REFORÇO`. Publique só NOVO + REFORÇO válidos.

### 10–11. Analisar e ancorar

Cruze Context Pack × entrega. Incorpore Figma se o passo 5 rodou. Rode o
checklist anti-bug da persona. Smell/estilo: [linters.md](references/linters.md).

Cada achado: severidade, path, `new_line` (linha **adicionada** no `head_sha`),
corpo no template abaixo. Ordene por severidade. Linguagem do snippet =
`snippet_lang` (ou a do arquivo).

### 12. Preview + aprovação

Mostre: Comparing line, **Stack**, aderência ao ticket, fidelidade Figma,
modo full/incremental, achados (`arquivo:linha` + severidade + título),
omitidos por duplicação, linter lido/executado. **Só publique após aprovação.**

### 13. Publicar ou chat

Só chame `post_review.py` se `can_publish`. Caso contrário: review
completo **no chat** e repita o `instructor`.

```bash
python3 $SKILL_DIR/scripts/post_review.py --input review.json --forge gitlab
python3 $SKILL_DIR/scripts/post_review.py --input review.json --forge github
python3 $SKILL_DIR/scripts/post_review.py --input review.json --forge bitbucket
python3 $SKILL_DIR/scripts/post_review.py --input review.json --forge azure
```

GitHub: um `POST .../pulls/{n}/reviews` com `comments[]` (`path`, `line`,
`side=RIGHT`) + `body` do resumo. A linha tem que existir no **diff** do
PR. `gh pr comment` não ancora em linha — não use.

### 14. Side-effects finish (MR/PR aberto + `can_publish`)

Se a lista **final** tiver ≥1 `CRÍTICO` / `ALTO` / `MÉDIO`:

```bash
# GitLab
python3 $SKILL_DIR/scripts/apply_review_workflow.py finish \
  --mr <IID> --has-blocking-findings true
# GitHub
python3 $SKILL_DIR/scripts/apply_review_workflow.py finish \
  --pr <IID> [--forge github] --has-blocking-findings true
```

Caso contrário: `--has-blocking-findings false` (no-op de label).

### 15. Cleanup (SEMPRE)

```bash
git worktree remove --force /tmp/pr-<source_sanitizado>
```

## Template do comentário inline

````markdown
**[SEVERIDADE — tema] — <título curto do achado>**

**Problema:** <o que está errado e o impacto real>

**Antes:**
```<snippet_lang>
<somente código real existente>
```

**Depois (sugestão):**
```<snippet_lang>
<somente código real proposto>
```

**Por quê:** <justificativa: SOLID/KISS/DRY/YAGNI/bug/thread-safety/etc.>

**Referência:** <link da doc oficial da stack, quando aplicável>
````

Severidades: `CRÍTICO`, `ALTO`, `MÉDIO`, `BAIXO`.

## Regra dos snippets (OBRIGATÓRIA)

- Blocos **Antes** / **Depois**: **somente código real** — nunca comentário no lugar de código.
- Explicação só em **Problema** / **Por quê**.
- Todo achado NOVO traz Antes e Depois. Remoções: mostre o código resultante.

## Nota-resumo (MR)

Incluir:

- Modo: `full` | `incremental desde <sha7>`
- **Stack:** `<stack_id>` (`<label>`)
- **Forge:** `<forge>` / `<mode>` (`can_publish=<true|false>`)
- **Aderência ao ticket `<KEY>`**
- **Fidelidade ao Figma** (ou "sem referência")
- Achados por severidade; omitidos/reforços
- Linter: nome + config lida / execução ou “não executado”
- Pontos positivos
- Referências (docs oficiais da stack; Figma; regras do linter)
- Marcador final: `<!-- power-review:head_sha=<head_sha> reviewed_at=<iso> -->`

## Referências

- Detalhes JSON/scripts/troubleshooting: [reference.md](reference.md)
- Modos / re-review: [references/modes.md](references/modes.md)
- Persona central: [references/persona.md](references/persona.md)
- Stacks: [references/stacks/](references/stacks/)
- Linters: [references/linters.md](references/linters.md)
- Prior comments: [references/prior-comments.md](references/prior-comments.md)
- MR + Jira workflow: [references/mr-jira-workflow.md](references/mr-jira-workflow.md)
- Forge / CLI: [references/forges/setup.md](references/forges/setup.md)
- Tracker / Context Pack: [references/trackers/setup.md](references/trackers/setup.md)
- MCP fallback (depois do token): [references/trackers/mcp.md](references/trackers/mcp.md)
- Figma REST: [references/trackers/figma.md](references/trackers/figma.md)
