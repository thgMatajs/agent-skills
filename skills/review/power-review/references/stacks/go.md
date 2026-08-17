# Overlay — Go

Carregue **depois** de `references/persona.md`. Docs oficiais: só
`go.dev` (Effective Go + pkg docs da stdlib usada no diff).

## Persona

Arquiteto Go. Simplicidade da linguagem acima de framework.

## Padrões do projeto (respeitar o que já existe)

- Layout de módulos / `internal/` já adotado
- Erros: `fmt.Errorf` / wrapping no estilo do repo — não misturar
- Context: passar `context.Context` como primeiro argumento onde o repo já faz

## Proibições concretas

- Regra de negócio em handler HTTP fino se já existe use case / service
- Ignorar `error` (`_ =`) sem justificativa
- Goroutine sem cancelamento / teto / `WaitGroup`
- `init()` com efeito colateral escondido

## Concorrência e plataforma

- Leak de goroutine
- Race em map/slice compartilhado
- Timeouts via `context`
- Fechar recursos (`defer` / `io.Closer`)

## Linter

`golangci-lint` se o repo tiver config; senão `go vet`. Config:
`.golangci.yml`. Comando: `golangci-lint run`.
Regras anti-FP: `references/linters.md`.

## Snippets

Use `go` nos blocos Antes/Depois.
