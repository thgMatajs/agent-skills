# Audit Report Template

**The delivered report is written in pt-BR (with accents).** Headers below are already
in pt-BR; keep dimension labels, code, paths and `file:line` refs as-is and write all
prose (notes, findings, suggestions) in Portuguese.

**No prioritization, no prescription.** The report's job is to make the state of the skill
legible — not to decide what happens next. List **every** suggested improvement, unranked.
Do NOT produce a "top N", do NOT order by leverage/effort/severity-of-fix, do NOT say what
should be done first or whether to do it at all. That call belongs to the author and the
team. Severity labels on *findings* are still required (they describe the defect's impact);
what is forbidden is ranking or sequencing the *work*.

```markdown
# Auditoria de Skill — <nome-da-skill>

**Veredito:** <A/B/C/D/F> — <nota>/<denominador> (<%>)
**Cap de nota aplicado:** <nenhum | cap de C por 0 em Contracts/Security — e se altera ou não o resultado>
**Modo:** <lite | deep>

## Resumo executivo

<2–4 parágrafos curtos, nesta ordem:>
<1. O que a skill faz bem — nomeie os acertos concretos ANTES das críticas. Uma auditoria
    que só lista defeitos é lida como injusta e perde credibilidade.>
<2. O que está errado, em uma frase que já entrega a consequência (não "há problemas de
    contrato", mas "a Fase 3 trava em toda invocação").>
<3. A conclusão principal em destaque (blockquote), se houver uma que reordene a leitura
    do resto — ex.: "o gargalo não é este arquivo, são as dependências".>

## Notas (0–2 por dimensão)
| Dimensão | Nota | Observação |
|---|---|---|
| Directness | /2 | |
| Novelty | /2 | |
| Clarity & interpretation-safety | /2 | |
| Routing | /2 | |
| Contracts & subagent-prompt | /2 | |
| Scope & refactorability | /2 | |
| Efficiency | /2 ou N/A | |
| Security | /2 | |
| **Total** | **/16** | (denominador = <16 ou menos se houver N/A>); média do corpus ~52% |

## Tiers rodados
- Tier 0: <passou/parou + porquê>
- Tier 1 (scripts): <resumo audit_structure + audit_writing>
- Tier 1.5 (cadeia causal): <traçada, ou "N/A — skill de passo único, sem encadeamento">
- Tier 2 (writing-quality / contracts-subagent / scope-refactorability): <achados-chave>
- Tier 4 (security): <achados; exists vs reachable; cobertura fresh/STALE>
- Tier 3 (behavioral): <PRG + delta de custo, ou "N/A — <motivo>">

## Cadeia causal

<Árvore no formato de `references/call-chain.md`: bloco `<pre>`, uma linha por ação,
indentação = profundidade, nomes linkados, branches como `[se X → …]`. Marque `🔴n` no
nó exato de cada defeito (numerados na ordem do fluxo) e `✅` no que você validou de
fato. Omita esta seção só se Tier 1.5 for N/A — e diga isso em "Tiers rodados".>

| # | Nó | Defeito | Dimensão |
|---|---|---|---|
| 🔴1 | | | |
| ✅ | | <o que foi validado, e como> | — |

<Uma frase: o que a topologia mostra que a prosa não mostrou — onde os defeitos se
concentram e, portanto, se o problema é o miolo da skill ou suas fronteiras.>

## Achados

| # | Severidade | Local | Defeito | Consequência concreta |
|---|---|---|---|---|
| 1 | 🔴 Crítico / 🟠 Alto / 🟡 Médio / 🔵 Baixo | `arquivo:linha` | | <o que acontece de fato, não "pode causar problemas"> |

<Ordem: da ordem do fluxo ou do arquivo — NUNCA por "o que corrigir primeiro".>

## Dependências e costuras
<Só para skills que encadeiam outras. Uma linha por dependência, com gradação explícita —
sem ela o leitor não distingue "impede a execução" de "degrada o resultado":>

| Dependência | Gravidade | O que quebra na costura |
|---|---|---|
| `<skill>` (Fase N) | 🔴 **Rompido** — <trava o run \| perda de dado> | |
| `<skill>` (Fase N) | 🟡 Instável — degrada sem travar | |

<Depois da tabela, afirme a consequência sem rodeios: quais itens impedem uma execução
completa mesmo que todos os achados desta skill sejam resolvidos, e quais só degradam.
Diga também se a dívida é desta entrega ou de código já mergeado — omitir isso faz o
relatório ler como se o autor fosse responsável por dívida de terceiros.>

## O que está certo e vale preservar
- <acerto concreto + por que preservar>

## Responsabilidades
<Veredito de responsabilidade única. Se over-scoped: nomeie as 2–3 skills em que deveria
ser dividida. Se houver sobreposição de charter com outra skill do acervo, cite a
`description` concorrente verbatim e diga se é duplicata, sobreposição ou distinta.>

## Melhorias sugeridas (inventário completo — sem ordem de prioridade)

<TODAS as melhorias identificadas, sem ranquear e sem recomendar sequência. Uma linha por
item. "Tipo" indica a forma que a melhoria tomaria; "Dimensão" liga ao que foi pontuado.>

| # | Local | Tipo | Melhoria | Dimensão |
|---|---|---|---|---|
| 1 | `arquivo:§` | script | <o que extrair e o shape de saída> | Scope |
| 2 | `arquivo:§` | template | <formato de saída repetido a extrair> | Efficiency |
| 3 | `arquivo:§` | contrato | <input/output a declarar> | Contracts |
| 4 | `arquivo:linha` | correção | <a mudança concreta> | <dimensão> |
| 5 | `arquivo:linha` | documentação | <o que declarar/avisar> | <dimensão> |

<Feche com uma nota de completude: "Lista completa dos <N> itens identificados. Sem ordem
de prioridade — a decisão de o quê, quando e se fazer é do time.">

## Escopo e limites desta auditoria
- **Dentro:** <o que foi auditado, em que modo>
- **Fora:** <o que não foi auditado, e por quê>
- **Não executado:** <tiers que não rodaram + o que isso significa que o relatório NÃO afirma>
- **Correções a conclusões intermediárias:** <se durante a auditoria você reverteu uma
  hipótese, registre — dá calibragem ao leitor e evita que um erro seu vire fato>
```

Rules (internal — the report itself is pt-BR per above):
- Every `file:line` you cite must be one you actually read and can quote verbatim
  (the auditors carry the quote in their `evidence:` field). A cited location you
  didn't read is confabulation — cut it.
- Every finding carries a **concrete** suggestion (the *what* and *where*) — a finding with
  no actionable content is noise. But **never** rank the suggestions, estimate a sequence,
  or tell the reader what to tackle first.
- State consequences, not risks: "trava em toda invocação" beats "pode causar problemas".
  A consequence the reader can picture is what makes a finding actionable without a ranking.
- Grade the **defect**, never the person or the PR author. Attribute pre-existing debt
  explicitly to pre-existing code.
- If a tier was skipped, say so and say what the report therefore does NOT claim. Don't
  imply coverage you didn't run.
- Omit a section only if genuinely empty — and write "nenhum" rather than deleting it, so
  the reader can tell the difference between "checked, clean" and "not checked".
