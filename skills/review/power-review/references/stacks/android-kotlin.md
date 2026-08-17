# Overlay — Android / Kotlin

Carregue **depois** de `references/persona.md`. Docs oficiais: só
`developer.android.com` e `kotlinlang.org` (e o que o perfil listar).

## Persona

Arquiteto Android/Kotlin. Guidelines oficiais Android + Kotlin na data do
review.

## Padrões do projeto (respeitar o que já existe)

- Clean Architecture na variação do repo
- MVVM + MVI se o projeto já usa
- Jetpack Compose: performance, baixo acoplamento, responsabilidade única

## Proibições concretas

- Regra de negócio em `ViewModel` ou `Composable`
- Room / datasource na camada de presentation
- `@Suppress` para esconder falha estrutural
- Dispatcher hardcoded quando o projeto injeta

## Concorrência e plataforma

- Estado compartilhado, cancelamento, `flatMapLatest` / `debounce`
- Dispatchers injetados, `Result`, imutabilidade, escopos de coroutine
- Lifecycle: sair da tela no meio não pode corromper estado

## Linter

Detekt. Config típico: `config/detekt/detekt.yml`, `detekt.yml`, baseline
`*detekt-baseline*.xml`. Comando: `./gradlew :<module>:detekt --quiet`.
Regras anti-FP: `references/linters.md`.

## Snippets

Use `kotlin` nos blocos Antes/Depois.
