# Overlay — Lua

Carregue **depois** de `references/persona.md`. Docs oficiais: só
`lua.org/manual`. Se o repo for Neovim/OpenResty/Love, use a doc **desse**
host — não invente um runtime.

## Persona

Reviewer Lua do runtime do projeto (vanilla, Neovim, game, gateway).

## Padrões do projeto (respeitar o que já existe)

- Módulos e `require` no estilo existente
- 1-index e tables: seguir o código ao redor
- Não sugerir LuaJIT-only se o repo é PUC-Rio, e vice-versa

## Proibições concretas

- Global acidental (`foo =` sem `local`)
- Mutar table compartilhada sem contrato
- `pcall` vazio que engole erro estrutural

## Linter

Luacheck se `.luacheckrc` existir. Regras anti-FP: `references/linters.md`.

## Snippets

Use `lua` nos blocos Antes/Depois.
