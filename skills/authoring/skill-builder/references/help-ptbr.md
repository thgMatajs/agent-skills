# Help (`--help`)

Print the block below verbatim, then stop — no other action, no side effect.

```
skill-builder — Cria uma skill nova ou adequa uma existente ao padrão do projeto.

USO:
  /skill-builder "<ideia>" [--project | --personal]
                                Cria uma skill nova a partir da ideia
  /skill-builder --rework <path>
                                Adequa uma skill existente ao padrão
  /skill-builder --help         Mostra esta ajuda

DESTINO (só no create):
  --project   .claude/skills/ + symlink .agents/skills/ + linha no AGENTS.md
  --personal  ~/.claude/skills/ (global; sem symlink nem AGENTS.md)
  Sem flag: se o repo tem .agents/skills/ e AGENTS.md com "## Available Skills",
  o default é project; caso contrário a skill pergunta uma vez.

COMO FUNCIONA:
  1. Entrevista uma pergunta por vez, sempre com uma resposta recomendada
  2. Cinco perguntas classificam a skill e abrem só os ramos que se aplicam
     (template, orquestração, guardrails, script)
  3. Gera SKILL.md, e só o que a entrevista justificar: references, scripts,
     e (project) symlink em .agents/skills/ + linha no AGENTS.md
  4. Audita o que gerou (auditing-skills --mode deep), até 3 tentativas buscando nota B
  5. Não emite com Contracts ou Security em zero — para e mostra os bloqueantes

ALVO DE QUALIDADE:
  Corpo de 100–300 linhas, tabela em vez de prosa, e só conteúdo que o modelo
  não conseguiria inferir sozinho (gotchas, convenções que fogem do default).
```
