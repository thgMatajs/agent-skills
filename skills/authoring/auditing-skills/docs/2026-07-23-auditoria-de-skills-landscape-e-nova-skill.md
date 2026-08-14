# Auditoria de skills — landscape 2026 + nova skill `auditing-skills`

> **Proveniência:** a skill foi promovida do projeto Skynet para uso pessoal em
> 2026-07-23; agora mora em `~/.claude/skills/auditing-skills/` (este spec junto, em
> `docs/`). Cross-refs a specs `2026-07-20-*` apontam para o repo Skynet, fora desta árvore.

**Data:** 2026-07-23
**Autor:** Thiago (com Claude)
**Status:** skill implementada + baseline TDD rodado (§5.1). Ganho de *detecção* real
modesto (PRG outcome ≈ +0,08); o valor está em estrutura/reprodutibilidade/segurança.
Validação empírica **parcial** com confounds conhecidos (§5.2). Não "validada por
terceiros" ainda.

Pesquisa das abordagens modernas de *auditoria de skills agênticas*, comparação
segundo os eixos pedidos (eficiência, diretividade, scripts, templates, qualidade
de subagents, contratos), e entrega de uma skill nova (`auditing-skills`) com
auto-crítica de onde ela pode melhorar.

---

## 1. Por que isso importa agora (números de 2026)

> Os números abaixo vêm de relatórios/resumos de 2026 (não abri todos os PDFs
> primários, exceto a metodologia do SkillAudit). Tratar como ordem de grandeza,
> não como dado primário verificado.


- **Qualidade média baixa.** SkillsBench (47.150 skills públicas): média **6,2/12**.
  Só o quartil de topo (9+) mostrou ganho real de performance.
- **Foco vence volume.** 2–3 skills focadas → **+18,6 p.p.** de pass-rate; abordagem
  monolítica ("tudo num doc") → **−2,9 p.p.**. *Vertical depth beats horizontal breadth.*
- **Segurança é problema de base.** Snyk ToxicSkills: **36%** das skills testadas com
  prompt injection. Auditoria de 22.511 skills: ~6,3 defeitos por skill.
- **Curadoria paga.** Skills bem revisadas: +16,2 p.p. em média (saúde: +51,9).

Tradução para o Skynet: nosso inventário herdado quase certamente está na média
(6,2/12). Auditar antes de promover não é burocracia — é onde está o ganho.

## 2. Landscape — o que existe (jul/2026)

| Ferramenta | Tipo | Executa? | Eixos que cobre bem | Onde peca |
|---|---|---|---|---|
| **agent-skill-linter** (William-Yeh) | Linter estático + regras semânticas | Não | Estrutura, frontmatter, naming, progressive disclosure, plugin manifest; `--fix`; JSON p/ CI | Não mede utilidade/segurança/comportamento; regras semânticas dependem de agente externo |
| **skill-eval** (effectorHQ) | Scorer estático | Não | 7 dimensões estruturais, nota A–F, interfaces tipadas (effector-spec) | v0.1 **não** avalia utilidade/segurança/eficiência/diretividade; sem sandbox |
| **SkillAudit** (arXiv 2606.22613) | Avaliação centrada na skill | Sim | **Utilidade (PRG)**, **eficiência/custo (ECG)**, **segurança** (2 estágios, 21 padrões, 97% recall) | Pesado; exige runtime/sandbox; foco acadêmico |
| **skill-eval-harness** (adewale) | Harness de eval pareado | Sim | Variantes with/without-skill, artefatos de trace, matriz por agente (**inclui subagent**) | Infra-heavy; contratos não são o foco |
| **agent-skills-eval** (darkrishabh) | Test runner pareado | Sim | Baseline vs with-skill + juiz, relatório lado a lado | Só utilidade; sem diretividade/contratos |
| **Anthropic best-practices** (doc oficial) | Guia normativo | — | Diretividade, degrees of freedom, progressive disclosure, checklist, scripts vs instruções | É guia, não auditor — não pontua |
| **superpowers:writing-skills** (interno) | Processo (TDD p/ skills) | — | Routing (description=quando, não o quê), match-form-to-failure, bulletproofing, micro-teste | Foca em *criar*, não em *auditar* inventário de terceiros |

### Leitura dos eixos pedidos

- **Eficiência:** bem coberta por SkillAudit (ECG) e harnesses pareados. Ausente nos
  estáticos.
- **Diretividade:** só o guia da Anthropic e o writing-skills atacam de frente
  ("conciso", "assuma que o modelo já sabe"). Linters genéricos não veem.
- **Scripts:** best-practices tem a regra de ouro — *solve, don't defer*, sem
  "voodoo constants", intenção de execução explícita.
- **Templates:** best-practices formaliza (strict vs flexible template pattern).
- **Qualidade de subagents:** **lacuna real.** Só o skill-eval-harness toca
  (matriz por agente), e mesmo assim como suporte de execução, não como *qualidade
  do contrato do subagent*.
- **Contratos:** **lacuna real.** effector-spec (interfaces tipadas) é a única
  âncora externa; internamente, `ReportFindings` e os agentes `gsd-*` são os
  melhores exemplos de contrato de retorno.

**Conclusão do landscape:** ninguém *tiera* a auditoria (barato→caro) e os dois
eixos pedidos mais fracos no mercado são **subagents** e **contratos**. É aí que a
skill nova se diferencia.

## 3. A skill nova — `auditing-skills`

Localização: `.claude/skills/auditing-skills/`.

Desenho (dogfooding progressive disclosure — SKILL.md fino de 91 linhas + refs):

```
auditing-skills/
├── SKILL.md                              # workflow em tiers + 6 dimensões
├── references/
│   ├── rubric.md                         # 0–2 por dimensão, bandas A–F
│   ├── subagent-and-contract-review.md   # os 2 eixos fracos do mercado
│   ├── security-patterns.md              # injeção/exfil/destrutivo, exists vs reachable
│   ├── behavioral-eval.md                # eval pareado + micro-teste de wording
│   └── report-template.md                # verdict + scores + top-3 fixes
└── scripts/
    └── audit_structure.py                # Tier 1 mecânico (roda em CI)
```

**Contribuição original: auditoria em tiers, para no primeiro que desqualifica.**

- **Tier 0 — deveria ser skill?** Duplicata → merge. Enforçável por regex/hook →
  automatize, não documente. One-off → não é skill reutilizável.
- **Tier 1 — estrutural (mecânico → script).** `audit_structure.py`: frontmatter,
  naming, <500 linhas, refs 1-nível, links mortos, paths Windows. Sai com exit code
  p/ CI.
- **Tier 2 — julgamento semântico (o diferencial).** Diretividade, routing,
  contratos. Pega o que linter não vê: description como *roteador* e não resumo de
  workflow; degrees of freedom vs fragilidade; *match the form to the failure*.
- **Tier 3 — eval comportamental pareado (só se a skill promete mudar comportamento).**
  Pass-rate gain + delta de tokens/tempo. Ganho zero = a skill não paga o contexto.
- **Tier 4 — scan de segurança.** Padrões de injeção/exfil/destrutivo; distingue
  risco *existir* de ser *alcançável*.

**Saída:** verdict + score por dimensão (/12, referência 6,2) + **top-3 fixes
rankeados por alavancagem**. Finding sem fix concreto é ruído.

Por que tiered é novo: o mercado se divide em estáticos (não executam) e harnesses
(executam) — ninguém ordena por custo nem coloca o julgamento semântico (onde as
skills de fato falham) como estágio central e barato antes do eval caro.

## 4. Como a nova skill trata os 6 eixos vs o mercado

| Eixo | Mercado | `auditing-skills` |
|---|---|---|
| Eficiência | ECG (SkillAudit) | Tier 3 delta tokens/tempo + regra "monolito = 0" |
| Diretividade | Só guias | Dimensão de 1ª classe, rubrica 0–2, Tier 2 |
| Scripts | Regras da Anthropic | Herdadas na rubrica (solve-don't-defer) + próprio script mecânico |
| Templates | Pattern da Anthropic | `report-template.md` + slot de contrato |
| **Subagents** | Lacuna | Checklist dedicado: self-contained, tool-scoped, contrato de retorno, isolamento |
| **Contratos** | Só effector-spec | Checklist: inputs/outputs/allowed-tools/critério verificável, ancorado em `ReportFindings`/`gsd-*` |

## 5. Onde pode melhorar (auto-auditoria — a skill se audita)

Aplicando a própria skill a si mesma, honestamente:

| Dimensão | Score | Nota crítica |
|---|---|---|
| Diretividade | 2/2 | SKILL.md ~100 linhas, refs sob demanda. |
| Routing | 2/2 | Description "Use when…", 3ª pessoa, sem resumo de workflow. |
| Contratos | 2/2 | Saída = template fixo; script tem exit codes definidos. |
| Subagent quality | 2/2 | Agora dispara (fan-out): prompt self-contained, tool-scoped (sem Edit/Write), contrato de retorno — **mas nunca rodado end-to-end** (ver gap b). |
| Eficiência | 1/2 | Progressive disclosure ✅, mas ganho de detecção medido é modesto (PRG outcome ≈ +0,08) e **ECG −0,66** (custa ~32% mais tokens, gaps a/e). Honestamente 1, não 2. |
| Segurança | 2/2 | Sem fetch-execute, script só lê arquivos; `security-patterns.md` com cadência de revisão. |

**Total: 11/12** (banda A). Mas um self-audit é **enviesado** (autor = revisor), então
o número importa menos que os gaps residuais honestos abaixo. Tratar como "A de design
com lastro empírico parcial", não "A validada por terceiros".

### 5.1 Baseline TDD — o resultado (RED → GREEN)

Rodei o eval pareado real (fixture `pdf-rag-helper` plantada com 6 defeitos; 3 reps
por braço, subagents; score = fração dos 6 `expected_behavior`). Dados em
`eval/results.json`, métrica via `scripts/paired_eval.py`:

**Cuidado com a métrica — dois PRGs, não um.** Dos 6 bullets, os bullets **1 e 2**
(tierar; score /12 + banda) são o **formato prescrito pela própria skill**, não um
resultado — o baseline *não tem como* passá-los (não sabe que a skill inventou escala
/12 e 5 tiers). Medir isso é medir conformidade a template, não detecção. Então:

| Braço | PRG completo (6 bullets) | PRG **outcome** (bullets 3–6: pega os defeitos?) |
|---|---|---|
| sem skill (baseline) | 0,61 | **0,92** |
| com skill | 1,00 | 1,00 |
| **PRG** | **+0,39** (conformidade de formato) | **≈ +0,08** (detecção real) |

**A leitura honesta é o número outcome: ≈ +0,08, não +0,39.** No Opus, o baseline
**já acha** os defeitos graves (curl|bash, `allowed-tools:*`, hand-waving) e **já
rankeia** fixes — os 3 deram "reject". O que ele **não faz**: tierar barato→caro e
dar score/banda calibrados. Ou seja, o valor demonstrado da skill **não é achar
problema** — é **estrutura, score comparável, reprodutibilidade e consciência de
segurança**: os 3 braços com skill pularam o Tier 3 *por segurança* (rodar o eval
executaria o próprio `curl|bash`) — insight não-circular que **nenhum baseline teve**.
O +0,39 é real, mas é ganho de *formato*; num doc sobre rigor de auditoria, liderar
com ele seria a mesma classe de overclaim que o "9/11 B+" que corrigi antes.

**ECG = −0,66** (custa mais — ver gaps a, e).

### 5.2 Gaps residuais (o que um self-audit enviesado ainda deixa)

a. **ECG negativo (−0,66).** A skill troca ~32% mais tokens por auditoria calibrada.
   Bom trade como *gate de inventário*; trade ruim para um one-off. A própria rubrica
   **não penaliza custo de token o bastante** — meta-finding a corrigir.
b. **Fan-out nunca rodado ponta-a-ponta.** Só o audit de 1 skill foi testado; o
   `inventory-fanout.md` é padrão documentado, não exercício real.
c. **Dataset de eval com n=1 task.** PRG +0,39 vem de 1 cenário × 3 reps. Precisa de
   mais fixtures (skill boa, skill média, reference skill) p/ claim robusto.
d. **Score dos 6 bullets foi feito à mão pelo autor.** Viés de grader; falta um juiz
   independente. Além disso 2 dos 6 bullets eram conformidade-de-formato, não outcome
   (corrigido em §5.1 com PRG duplo).
e. **Braços não pareados no uso de advisor.** Os 3 subagents *com skill* chamaram o
   `advisor` por conta própria ("advisor concurs/confirmed"); os baseline não. Isso
   contamina duas coisas: a variância-zero do braço com-skill pode ser o advisor
   forçando convergência (não a skill sendo vinculante), e o custo de token (+32%,
   ECG −0,66) **superestima** o custo da própria skill. O eval não isola o efeito da
   skill; um re-run pareado precisa proibir advisor nos dois braços.

### 5.3 As 5 melhorias — status: **aplicadas**

1. ✅ **Baseline TDD** — rodado (§5.1). RED/GREEN documentado; PRG outcome ≈ +0,08
   (formato +0,39), com confounds honestos em §5.2.
2. ✅ **Runner Tier 3** — `scripts/paired_eval.py` (prompts + PRG/ECG; sem API própria,
   não fabrica score) + `eval/dataset.json`. Rodado com dados reais.
3. ✅ **Fan-out** — `references/inventory-fanout.md` + seção no SKILL.md (1 subagent/skill,
   tools escopados, contrato de retorno, ranking pior-nota-primeiro).
4. ✅ **Cadência de segurança** — marcador de dono + revisão a cada 90 dias em
   `security-patterns.md`; lista velha vira flag, não "pass limpo".
5. ✅ **Âncoras na rubrica** — tabela de calibração 0/1/2 ancorada no fixture.

## 6. Próximos passos sugeridos (Skynet)

1. Fechar gaps b–d antes de tratar `auditing-skills` como validada por terceiros:
   rodar um fan-out real e ampliar o dataset p/ ≥3 fixtures com juiz independente.
2. Aplicar a skill ao shortlist de promoção do inventário (ver
   `2026-07-20-funil-promocao-inventario.md`) — Tier 0→2 em lote é barato e já filtra.
3. Ligar `audit_structure.py` no CI de skills como gate mecânico.

---

## 7. v2 (2026-07-23) — orquestrador + auditores especializados + novos eixos

Reescrita a pedido do Thiago. Mudanças:

**Arquitetura:** `SKILL.md` virou **orquestrador enxuto** (103 linhas). Roda tiers
baratos inline (Tier 0 + scripts) com early-exit; os tiers caros são **auditores
especializados**, cada um com responsabilidade única e contrato de retorno
(finding-block), em `references/auditors/`. Knob **lite** (auditores inline, default)
vs **deep** (fan-out por dimensão, só p/ audit profundo de 1 skill — nunca aninhado no
fan-out de inventário).

**Dimensões: 6 → 7** (score % do máx aplicável, não mais /12 fixo):
Directness · **Clarity & interpretation-safety** (ambiguidade, gaps, error-induction) ·
Routing · **Contracts & subagent-prompt** (funde contratos + auditoria do prompt que a
skill passa ao subagente) · **Scope & refactorability** (responsabilidades demais? o
que deveria ser script/template/contrato?) · Efficiency · Security.

**Novos artefatos:** `scripts/audit_writing.py` (sinais mecânicos: token count, ratio
instrução/ruído, hedge-words, fork-sem-join, placeholders — case-sensitive p/ não
falso-positivar `<dir>`/`<brief>`); 4 briefs de auditor; `security-patterns.md` e
`subagent-and-contract-review.md` migrados p/ `auditors/`. Report ganhou blocos
**Responsibilities** e **Refactor suggestions**.

**Do research (pasteado pelo Thiago):** verifiquei que **NVIDIA/SkillSpector** (68
padrões, SARIF, OWASP Agentic Skills Top 10) e **skill-validator** são reais — mas por
decisão do usuário a skill é **self-contained**: essas ferramentas entram só como
*referência* p/ expandir padrões, não como dependência. Adotado barato: executor/grader
separation (AEVAL) no `behavioral-eval.md`. Rejeitado/deferido: onchain/World ID,
MCP-server-as-req, domain-correctness 91-rules, drift-vs-repo.

**Verificação v2:** `audit_structure.py` + `audit_writing.py` passam limpos na própria
skill (0 err); orquestrador <500 linhas; scripts rodam em skills reais do repo
(`mem-consolidate`, `mem-resume`); audit lite ponta-a-ponta de `mem-consolidate`
produziu report completo (A, denominador 12 c/ Efficiency N/A).

**Baseline pareado v2 (rodado 2026-07-23) — confounds da §5 corrigidos.** Fixture v2
(com Slack scope-creep + validação em prosa); 3 reps/braço; **advisor proibido nos dois
braços**; pontuação por **juiz independente** (braços intercalados+sem rótulo), não pelo
autor. Dados em `eval/results-v2.json`.

| Braço | outcome (C3–C8) | full (C1–C8) |
|---|---|---|
| sem skill | 0,61 (juiz full: 4/3/5) | 0,50 |
| com skill | 1,00 (juiz full: 8/8/8) | 1,00 |
| **PRG** | **+0,39** | +0,50 |

- **Ganho de detecção agora é real (+0,39), não só formato** — contraste com o v1
  (+0,08). Por quê: os eixos NOVOS que o Thiago pediu são onde a estrutura agrega. Os
  baselines *viram* o Slack mas o trataram como "default inseguro, remova"; só o braço
  com-skill o classificou como **scope creep → split** (C6: baseline 0/3, com-skill 3/3).
  Idem "subagent = falha de contrato" (C4) e "description = workflow-summary + 1ª pessoa,
  os dois" (C3): baseline 1/3, com-skill 3/3.
- **Convergência sem advisor:** com-skill 8/8/8 idêntico nos 3 reps sem nenhuma chamada
  de advisor — mata o confound v1 (a convergência era da skill, não do advisor).
- **Custo honesto:** ECG −0,52 (~48% mais tokens, ~55% mais tempo), sem advisor inflando.
  Trade defensável como **gate de inventário**; caro p/ one-off. Gaps residuais: dataset
  ainda n=1 task; 3 reps.

## 8. Refinamentos de precisão/eficiência (2026-07-23)

Após a v2, 4 melhorias pedidas pelo Thiago:

1. **Double-count corrigido.** `allowed-tools: "*"` era flagado em Security E Contracts
   — um único defeito zerava duas dimensões e disparava o cap 2×. Agora é **scored só
   em Contracts**; Security apenas reporta. (rubric + os dois briefs.)
2. **Leituras escopadas por tier** + consolidação do rubric (2 seções "Grade bands"
   duplicadas → 1). O auditor não puxa mais `inventory-fanout.md`/`behavioral-eval.md`
   num audit único. Honestidade: ~metade dos +48% de token é intrínseco (ler rubrica +
   emitir report), lazy-load só ajuda a minoria que morre antes do Tier 2.
3. **Dedup cross-skill** (pré-passe no `inventory-fanout.md`): indexa name+description de
   todas as skills e clusteriza duplicatas/overlap antes do fan-out — o Tier 0
   "é duplicata?" é estruturalmente impossível dentro do fan-out (cada subagente vê 1).
4. **Medição de falso-positivo (o gate).** Fixture de skill *excelente*
   (`writing-commit-messages`); 3 audits com-skill (lite, sem advisor). Resultado:
   **A / A / A (12–13/14), zero achado inventado.** Os 3 confirmaram que o WARN mecânico
   "fork-sem-join" era falso-positivo (leram e descartaram). **FP no nível de julgamento
   ≈ 0.** Dados em `eval/results-fp.json`.

O gate surfou 2 gaps reais, já corrigidos: (a) variância inter-revisor em Efficiency p/
skills pequenas (rep1=1 vs rep2/3=2) → âncora do rubric desambiguada; (b)
`audit_structure.py` não checava name-vs-diretório → check adicionado (dispara em
mismatch, verificado). **Residual:** FP medido em 1 skill limpa; falta fixture
*borderline* p/ medir a variância 1↔2 onde skills reais se concentram.

### Fontes

- SkillAudit — arXiv 2606.22613 (utilidade/eficiência/segurança, eval 2 estágios)
- SkillCorpus / SkillsBench — arXiv 2607.15557 (6,2/12; corpus)
- Agent Skills Ecosystem Report 2026 — agentman.ai (36% injeção; +18,6 vs −2,9 p.p.)
- Skill authoring best practices — docs oficiais Anthropic/Claude
- agent-skill-linter — github.com/William-Yeh/agent-skill-linter
- skill-eval — github.com/effectorHQ/skill-eval
- skill-eval-harness — github.com/adewale/skill-eval-harness
- agent-skills-eval — github.com/darkrishabh/agent-skills-eval
- superpowers:writing-skills (interno, TDD para skills)
