# Report Template

**The delivered report is written in pt-BR (with accents).** Headers below are already in
pt-BR. Keep code identifiers, file paths, `file:line` refs, commands, rule IDs, URLs and
dimension labels as-is; write all prose in Portuguese.

Save it to disk **before** replying (destination rules in `SKILL.md` §Fase 4), then state
the path and whether it is committed.

```markdown
# Auditoria do corpus de instruções agênticas — <nome do repo>

- **Gerado em**: <YYYY-MM-DD HH:MM TZ — data/hora do SO, Fase 0>
- **Fronteira auditada**: branch `<branch>` @ `<HEAD>` — afirmações valem para este checkout
- **Stack detectado**: <top linguagens/frameworks + versões fixadas relevantes>
- **Superfícies auditadas**: <N arquivos, M linhas> — <lista curta com o agente que lê cada uma>
- **Modo**: <deep (N pesquisadores + 7 auditores) | lite (inline)>
- **Não auditado**: <outras branches/worktrees, skills, hooks, o que ficou fora — seja explícito>

## 1. Panorama

<3–6 linhas: o que o corpus é, onde ele acerta, e a natureza dominante dos defeitos
(executabilidade? contradição? custo?). Sem ordem de ataque.>

| Dimensão | Findings | Tier mais severo | Nota de uma linha |
|---|---|---|---|
| Executability | N | T1 | |
| Consistency | N | T2 | |
| Enforcement | N | T3 | |
| Currency | N | T4 | |
| Coverage | N | T5 | |
| Context economy | N | T6 | |
| Instruction quality | N | T7 | |

## 2. Ranking de findings (todos, por impacto)

Impacto = `tier × alcance × confiança` (modelo em `references/severity-model.md`).

| # | Impacto | Tier | Dimensão | Onde | Defeito | Correção | Fatores |
|---|---|---|---|---|---|---|---|
| 1 | | | | `file:line` | | | tier×alcance×confiança |

> Sequenciamento não é entregável desta auditoria. O ranking mede impacto; a ordem de
> execução depende de prioridade de produto, risco aceito e capacidade — decisão humana.

**Verifique esta tabela depois de gravar o relatório** (Fase 4, passo 5 — o arquivo já está em
disco, então isso não acrescenta passo de workflow):

```bash
python3 "$SKILL_DIR"/scripts/summarize_run.py --check <caminho-do-relatorio>.md
```

Ele re-deriva o §2 dos fatores que a própria seção publicou, lendo os pesos e os domínios de
`references/severity-model.md` em runtime (sem cópia que possa ficar obsoleta). Confere:
aritmética de `Impacto`; se o peso usado em `Fatores` é o do tier nomeado na coluna `Tier`;
se `alcance` e `confiança` estão nos domínios declarados; ordenação decrescente; e **empate
exibido como empate** — adjacente *e* com a célula `Impacto` byte-idêntica, porque `15` ao lado
de `15.0` é um empate que o leitor não vê. Arredondar é divergência, não tolerância. Saídas: `0`
limpo, `1` conferido com divergências, `2` não deu para conferir (relatório ausente, §2 ausente,
linha ilegível, modelo de severidade ilegível) — "não deu para conferir" nunca se confunde com
"está limpo".

**O que ele NÃO decide, e não pode:** se um finding é **verdadeiro** — nunca abre o repo
auditado, então um `Onde` apontando para `file:line` inexistente passa; se `evidence`/`proof`
existem ou foram citados verbatim; se o tier atribuído é o **certo** (mecanismo de dano é
julgamento); se `alcance`/`confiança` foram bem avaliados, só que estão no domínio; e um empate
desfeito empurrando um fator continua invisível, porque a aritmética segue autoconsistente. Ele
também não lê o §3 nem procura linguagem de sequenciamento: um scan de `P0`/`P1` não distingue o
rótulo do próprio relatório de um citado do corpus auditado, e check que não decide é pior que
nenhum. Passar no `--check` significa **§2 autoconsistente**, nada além disso.

## 3. Findings detalhados

Um bloco por finding, na ordem do ranking. Cada bloco:

### #<rank> — <título curto> · <Tier> · <Dimensão>

- **Onde**: `file:line`
- **Evidência**: `"<linha verbatim>"`
- **Prova**: <comando rodado + output observado | grep + resultado | config lida | fonte datada
  | para **T7**, a própria linha citada: `evidence` + `occurrences` + `samples`>
- **Defeito**: <o que quebra, e o que o agente faz de errado por causa disso>
- **Correção**: <concreta e verificável>
- **Fatores**: tier <T> · alcance <3|2|1> · confiança <1.0|0.7|0.4> → impacto <n>

**Variante para finding de ausência** (Coverage/T5 — uma lacuna não tem linha para citar,
e cobrar `file:line` dela criaria o defeito que `severity-model.md` proíbe):

- **Onde**: `<superfície em que a orientação deveria estar>` (ausência)
- **Prova de necessidade**: <por que este stack/domínio exige — evidência no repo>
- **Prova de ausência**: <grep repo-wide + resultado vazio>
- **Defeito / Correção / Fatores**: como acima

A regra "todo `file:line` citado tem de ter citação verbatim" **não** se aplica a esta
variante: ela não cita `file:line`. Não corte findings de Coverage por falta de `evidence`.
O carve-out normativo que o **auditor** recebe vive em `references/severity-model.md`
§"Evidence contract" (T5 de ausência); esta seção é só a forma de apresentação dele.

O mesmo vale para **T7**: `severity-model.md` §"Evidence contract" declara que a linha citada
**é** a prova, e que `evidence` + `occurrences` + `samples` satisfazem o contrato sem rebaixar
`confidence`. Nas duas variantes, o arquivo dono é `severity-model.md` — se elas mudarem lá,
mude a linha **Prova** acima também; foi a dessincronia entre esses dois arquivos que já custou
uma dimensão neste pacote.

## 4. Custo de contexto por sessão

**Corpus sem superfície de prosa (`.md`/`.mdc`) — a única forma autorizada de §4 sem o script.**
Se a Fase 0 tomou esse ramo, a Fase 1 não rodou e os três artefatos não existem, então o script
não tem entrada. Nesse caso escreva §4 como **N/A com o motivo declarado** ("corpus sem
superfície de prosa: `settings.json`/hooks/config de vendor não são injetados como prosa; custo
por sessão não medido"), liste as superfícies detectadas e pare aí. **Não** monte a tabela à mão
para preencher a seção: um número inventado é pior que uma seção honestamente vazia. Esta é a
**única** exceção à frase abaixo.

**Não monte à mão a parte determinística.** Este arquivo é o **dono único** desta frase
normativa — `SKILL.md` §"Custo de contexto" só aponta para cá. `scripts/summarize_run.py`
faz bookkeeping determinístico sobre os **três** artefatos (`detect`, `measure`, `claims`) e
emite exatamente: os 2 bullets de cabeçalho, a tabela por arquivo, as linhas de `excluded`, a
reconciliação dos dois totais e as linhas 0–1 de §9.

**Os três blocos restantes NÃO saem do script** e você os monta a partir do bloco de retorno
do auditor de Context economy (`references/auditors/context-economy.md` §"Return contract"):
**Peso morto identificado** ← os findings T6 (`kind`/`where`/`lines`/`tokens_est`/`audience`/
`fix`); **Orçamento proposto** ← o bloco `budget` (`always_on_tokens_est`,
`target_always_on_tokens_est`, `cuts[]`); a linha de risco oposto ← o parágrafo de risco
oposto que o mesmo brief exige (§3). Sem esse bloco, §4 sai com a medição de custo e sem
nenhuma das duas tabelas que produzem ação.

Invocação da parte determinística (Fase 4, passo 4):

```bash
SKILL_DIR=<caminho absoluto da pasta que contém o SKILL.md desta skill>
python3 "$SKILL_DIR"/scripts/summarize_run.py \
  --detect /tmp/agent-rules-<repo>-detect.json \
  --measure /tmp/agent-rules-<repo>-measure.json \
  --claims /tmp/agent-rules-<repo>-claims.json
```

A coluna `Always-on` vem de `measure_context.json.per_file[].always_on`
(`sim | condicional | não | desconhecido`) com sua base ao lado. **`condicional` não é
veredito:** scoped rules (`declares_scope`) **e** nested-doc carregam sob demanda.
Dizer se o runtime honra isso é julgamento do auditor de Context economy — é você quem
preenche `<sim | não | n-a>` e o "como determinou". O que o script não sabe, ele não afirma.

- **Always-on**: <N tokens estimados> · **sob demanda**: <N> · total <N>
- **Metadados de escopo honrados pelo runtime**: <sim/não/n-a> — <como foi determinado>

| Arquivo | Linhas | Tokens est. | Always-on | Observação |
|---|---|---|---|---|

<Uma linha por superfície medida. Feche a tabela com as superfícies detectadas mas FORA da
contabilidade de tokens (`measure_context.json.excluded` — settings, configs de vendor,
hooks), marcadas como tal e com o motivo. Elas continuam auditadas em Enforcement; o que
não vale é somar `totals.lines` e chamar de "o corpus" quando `totals.lines_detected` é
maior — cite os dois números e explique a diferença.>

**Peso morto identificado**

| Tipo | Onde | Linhas | Tokens est. | Público | Substituível por |
|---|---|---|---|---|---|
| duplicação / inerte / duplica-enforcement / volume-diferível | | | | | corte, ponteiro de rule ID, carregamento sob demanda |

**Orçamento proposto**: <atual> → <alvo> tokens always-on. Itens:

| Corte | De onde | Tokens est. |
|---|---|---|
| | | |
| **Soma** | | |

<Uma linha sobre o risco oposto, se aplicável: corpus fino demais force o agente a
buscar tudo, custando mais em turnos.>

## 5. Conversões prosa → enforcement determinístico

| Regra (onde) | Mecanismo concreto | Já garantido por | Efeito |
|---|---|---|---|
| `file:§` | rule ID a habilitar / hook + padrão / step de CI | rule ID existente ou "—" | prosa vira ponteiro de 1 linha |

## 6. Pontos fortes (preservar)

<Lista curta e específica: o que este corpus faz melhor que a média e deve ser mantido
ou usado como padrão interno. Cite `file:§`. Auditoria sem esta seção vira demolição e
perde credibilidade.>

## 7. Falsos positivos descartados

| Candidato | Onde | Por que não é finding |
|---|---|---|

## 8. Perguntas abertas

<Alegações que a pesquisa não resolveu, conflitos de fonte não reconciliados, e decisões
que exigem o humano (ex.: "a11y é requisito ou dívida aceita?"). Uma linha cada.>

## 9. Cobertura desta auditoria

As linhas 0 e 1 saem prontas de `scripts/summarize_run.py` (§4 acima). As linhas 2–4 só
existem depois dos fan-outs — são suas, com os números reais.

| Fase | O que rodou | Números |
|---|---|---|
| 0 contexto | detect_stack.py | <N superfícies, M linhas, stack> |
| 1 medição | measure_context.py, verify_claims.py | <tokens, clusters de duplicação, claims extraídos> |
| 2 pesquisa | <N eixos> | <N alegações verificadas, N fontes primárias> |
| 3 auditoria | <7 auditores / inline> | <comandos rodados, símbolos greppados, configs lidas> |
| 4 consolidação | dedup + ranking | <N findings após dedup, N descartados> |

<Diga explicitamente o que NÃO foi verificado — a lista de limites é parte da entrega.>

## 10. Fontes

<Somente as efetivamente usadas, com data e marcação primária/secundária. Agrupe por
eixo de pesquisa.>
```

Internal rules (the report itself is pt-BR):

- Every `file:line` cited must be one an auditor read and quoted verbatim. No quote → cut.
- A finding without a concrete fix → cut.
- Never emit priority waves, P0/P1 labels, effort-based ordering or "attack this first".
  Rank by impact and stop.
- Report skipped coverage honestly in §9. Implying coverage you didn't run is worse than
  a gap.
- Keep §6 and §7 even when short — they are the credibility controls of the audit.
- Sizing: the report must be smaller than the corpus it audits. If it isn't, you wrote an
  essay, not an audit.
