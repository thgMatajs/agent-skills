# Linter do projeto — base para smell / estilo

Para **estilo**, **naming**, **complexidade** e **code smell** genérico, a fonte
de verdade é o linter **do repositório sob review** — não o gosto do reviewer.

O perfil em `.power-review/stack.json` diz o nome, os configs encontrados e o
comando sugerido. Consultar `linter.configs` (se existirem) é **obrigatório**
antes de abrir achado de estilo. Rodar `linter.command` é opcional (use a
saída como evidência se for barato). Sem config: **não** abrir achado só
de estilo.

## Onde ler

1. Use `linter.configs` do perfil (paths relativos à raiz do repo).
2. Se a lista estiver vazia: registre “sem linter” e **não** abra achado só
   de estilo.
3. O overlay da stack (`persona_ref`) pode citar o comando típico
   (`./gradlew :mod:detekt`, `swiftlint`, `dart analyze`, `npx eslint`,
   `ruff check`).

## Regras anti falso-positivo (obrigatórias)

1. **Regra desligada** (`active: false`, `off`, `warning` só informativo,
   `disabled_rules`, `exclude`) → **não** abrir achado só por esse critério.
2. **Thresholds do projeto** → só apontar complexidade/tamanho se o código
   **estourar** o limite configurado. Abaixo: não comentar como smell.
3. **Excludes** (test/, generated/, `*.kts`, …) → não aplicar a regra a
   arquivo excluído pelo próprio linter.
4. **Baseline** (Detekt baseline, ESLint `--max-warnings` herdado, etc.) →
   se o finding já estava aceito e o MR não piora o trecho, não reabrir
   como estilo novo. Bugs reais ainda podem ser apontados.
5. **Severidade** de puro estilo: `BAIXO` ou `MÉDIO`. `ALTO`/`CRÍTICO` só
   com impacto de bug, segurança ou contrato de camada.

## O que o linter **não** substitui

Aponte com tolerância zero, independente do linter:

- Bugs, corridas, null-safety real, efeitos colaterais
- Regra de negócio na UI / persistência na presentation
- Supressão para esconder falha estrutural
- Aderência ao ticket / Figma
- Testes ausentes no fluxo crítico

## Como validar

Se o comando do perfil for barato o bastante, rode nos módulos/arquivos do
diff e use a saída como evidência — não como substituto da leitura.

Se falhar ou for lento: analise contra o config e declare na nota
“linter não executado; ruleset lido de `<path>`”.

## Como citar

Em **Por quê** ou **Referência**: nome da regra, threshold/trecho do config,
link da doc da regra (se existir). **Não** diga “viola boa prática de
estilo” se a regra correspondente estiver off no projeto.

## Checklist

- [ ] Consultei o config do linter (e baseline, se houver)?
- [ ] A regra está ativa (ou é bug/arquitetura fora do linter)?
- [ ] O threshold do projeto foi estourado?
- [ ] O arquivo não está em exclude?
- [ ] Não estou reabrindo só baseline sem regressão?
