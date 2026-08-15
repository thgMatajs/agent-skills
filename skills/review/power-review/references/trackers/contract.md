# Contrato — Context Pack (agnóstico)

Saída do `fetch_context_pack.py`. Campos desconhecidos = `N/A`. **Nunca inventar.**

`source`: `api_token` | `mcp` | `none` (`none` = sem pack; o script não imprime
pack — o agente anota e o review segue).

```markdown
## Context Pack — <KEY>

### Meta
- profile: review
- tracker: <jira | linear | asana | shortcut | github_issues>
- source: api_token | mcp | none
- figma_source: <none | blocked | api | error | mcp>
- blockers: <lista | none>

### Ticket
- Type / Summary / Status / Parent / Siblings

#### Escopo
- Objective, business rules, acceptance criteria, out of scope

#### Comments / decisions
#### Risks / gaps / ambiguities
#### Links
- Figma / Tracking / Others
#### Checklist de aderência

### Figma   # ausente se figma_source=none
- URL: <url do ticket>
- origem do link: ticket
- figma_source: <blocked | api | error | mcp>
- file_key / node_id: <parse da URL; node-id hífen → dois-pontos>
- file_name / frames / states: <só se REST/MCP devolveu; senão N/A>
- tokens/variables: N/A
- blockers: <sem token | HTTP NNN | none>
```

`frames` e `states` vêm só da API ou do MCP (`id`, `name`, `type`). Sem token,
com erro HTTP, ou MCP sem nós: **não inventar**. O link permanece.

O caller (power-review) usa ACs + checklist + bloco Figma. Sem pack
(`source: none`): seguir o review só com o diff.
