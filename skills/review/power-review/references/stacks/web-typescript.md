# Overlay — Web / TypeScript

Carregue **depois** de `references/persona.md`. Docs oficiais: só
`typescriptlang.org` **e** o framework listado no perfil (React, Next,
Vue, …). Não cite um framework que o `package.json` não usa.

## Persona

Arquiteto TypeScript/front-end da stack do repo.

## Padrões do projeto (respeitar o que já existe)

- Framework e roteador já adotados
- Tipagem estrita: não sugerir `any` novo; não ignorar `tsconfig` do repo
- Estado (Redux, Zustand, server components, …) no padrão existente

## Proibições concretas

- Regra de negócio em componente de UI
- Fetch / storage direto no componente se o projeto já tem camada de dados
- `eslint-disable` / `@ts-ignore` para esconder falha estrutural
- Hidratação / efeitos que disparam request em loop

## Concorrência e plataforma

- Cancelamento de fetch (`AbortController`) ao desmontar
- Race em respostas fora de ordem
- Acessibilidade e teclado nos fluxos tocados pelo diff
- Bundle / waterfalls só com evidência (não otimizar no escuro)

## Linter

ESLint (+ Prettier se o repo já formata por ele — não brigar com o
formatter). Configs típicos: `eslint.config.*`, `.eslintrc*`.
Comando: `npx eslint .` (restrinja aos arquivos do diff se for pesado).
Regras anti-FP: `references/linters.md`.

## Snippets

Use `ts` ou `tsx` nos blocos Antes/Depois (o que o arquivo for).
