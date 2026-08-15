# Overlay — Ruby

Carregue **depois** de [persona.md](../persona.md). Docs oficiais: só
`docs.ruby-lang.org` e, se o `Gemfile` tiver Rails, `guides.rubyonrails.org`.

## Persona

Arquiteto Ruby (e Rails só se o repo for Rails).

## Padrões do projeto (respeitar o que já existe)

- Layout do gem / app já adotado
- Service objects, form objects, POROs: só no padrão existente
- Não sugerir gem nova se o repo já resolve o problema

## Proibições concretas

- Regra de negócio em controller / view / helper de apresentação
- ActiveRecord (ou persistência) vazando para a camada de UI
- `# rubocop:disable` para esconder falha estrutural
- Callbacks de model que escondem efeito colateral não óbvio

## Concorrência e plataforma

- Idempotência de jobs / retries
- N+1 e queries no loop
- Secrets fora do código
- Transações em volta de gravação parcial

## Linter

RuboCop. Config: `.rubocop.yml`. Comando: `bundle exec rubocop`.
Regras anti-FP: [linters.md](../linters.md).

## Snippets

Use `ruby` nos blocos Antes/Depois.
