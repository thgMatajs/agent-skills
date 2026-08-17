# Workflow MR/PR + Jira (side-effects)

**Não rode nesta skill.** Labels/Jira pertencem à skill `power-review-workflow`.

Só se o usuário pediu, **depois da aprovação do preview**, GitLab/GitHub,
MR/PR aberto. Bitbucket / Azure / `local`: nunca.

O script continua em `scripts/apply_review_workflow.py` (chamado pela skill
irmã, não por este fluxo).
